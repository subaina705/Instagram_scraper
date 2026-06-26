"""
Local web app to fetch Instagram Reel / Post metrics using instagrapi.

Project layout
--------------
    test.py              -> Flask backend, login, scraping logic
    index.html           -> frontend markup
    static/css/styles.css
    static/js/app.js

Why instagrapi (and not instaloader)?
-------------------------------------
Instagram exposes two surfaces:

  * The "web" / GraphQL API  -> what your browser uses. Returns viewer-filtered
                                counts that are usually LOWER than what the UI shows.
                                (instaloader uses this, hence the wrong numbers.)
  * The "mobile" / private    -> what the Instagram app uses. Returns the real
    API (i.instagram.com)       like_count / comment_count / play_count, plus
                                shares, saves, reposts. (instagrapi uses this.)

instagrapi logs in as a real mobile device, so we get the same numbers the
Instagram app itself sees.

Run
---
    pip install flask instagrapi
    python test.py
    # then open http://127.0.0.1:5000

Table of contents (sections below)
----------------------------------
    1. Imports & module setup
    2. Session management (login + reuse cached session)
    3. URL / shortcode / username parsers
    4. Scraping primitives (single reel, profile, date range)
    5. Error mapping (instagrapi exceptions -> JSON)
    6. HTTP routes  (/ , /api/fetch , /api/reel_comments , /api/bulk_fetch , /api/bulk_fetch_stream , /api/profile_reels , /api/profile_reels_stream , /api/debug_node)
    7. Entry point
"""

# =============================================================================
# 1. IMPORTS & MODULE SETUP
# =============================================================================

import csv
import io
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, request, send_from_directory, jsonify, Response, stream_with_context

from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    ClientError,
    CommentUnavailable,
    CommentsDisabled,
    LoginRequired,
    PleaseWaitFewMinutes,
    PrivateAccount,
    TwoFactorRequired,
    UserNotFound,
)
from instagrapi.extractors import extract_comment

# Project paths (computed once at import time).
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(PROJECT_DIR, ".ig_sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

app = Flask(
    __name__,
    static_folder=os.path.join(PROJECT_DIR, "static"),
    static_url_path="/static",
)

# In-memory cache of logged-in clients. One Client per Instagram username.
# We keep these alive between requests so we don't re-login every time the
# browser sends a fetch — that would burn through rate limits very quickly.
# A threading.Lock makes the get-or-create flow safe across concurrent requests.
_clients: dict[str, Client] = {}
_clients_lock = threading.Lock()

# Request pacing — override via env, e.g. IG_FAST_DELAY_RANGE=0.3,0.8
def _parse_delay_range(env_key: str, default: tuple[float, float]) -> list[float]:
    raw = os.environ.get(env_key, "").strip()
    if raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 2:
            try:
                lo, hi = float(parts[0]), float(parts[1])
                if 0 <= lo <= hi:
                    return [lo, hi]
            except ValueError:
                pass
    return list(default)


_DEFAULT_DELAY = _parse_delay_range("IG_DELAY_RANGE", (1, 3))
_FAST_DELAY = _parse_delay_range("IG_FAST_DELAY_RANGE", (0.4, 1.0))


def _profile_clips_page_size() -> int:
    try:
        return max(12, int(os.environ.get("IG_PROFILE_PAGE_SIZE", "50").strip() or 50))
    except ValueError:
        return 50


_PROFILE_CLIPS_PAGE_SIZE = _profile_clips_page_size()


@contextmanager
def _scrape_delay(cl: Client, *, fast: bool = False):
    """Temporarily tune instagrapi's per-request sleep (bulk/profile vs single-reel)."""
    previous = cl.delay_range
    cl.delay_range = _FAST_DELAY if fast else _DEFAULT_DELAY
    try:
        yield
    finally:
        cl.delay_range = previous


# =============================================================================
# 2. SESSION MANAGEMENT
# =============================================================================
#
# Sessions are persisted to .ig_sessions/instagrapi-<username>.json so the user
# only has to type their password once. The file holds the cookies, device UUIDs,
# and user-agent that instagrapi randomly generated — re-using these makes the
# session look like the same device, which Instagram flags less.


def _session_path(username: str) -> str:
    """Where on disk we keep the saved session for `username`."""
    return os.path.join(SESSION_DIR, f"instagrapi-{username}.json")


def _new_client() -> Client:
    """Create a fresh instagrapi Client with sensible defaults."""
    cl = Client()
    # Built-in throttle between private requests (tunable via IG_DELAY_RANGE).
    cl.delay_range = _DEFAULT_DELAY
    return cl


def get_client(username: str, password: Optional[str]) -> Client:
    """
    Return a logged-in Client for `username`. The flow is:

        1. If we already have a live Client for this user in memory, reuse it.
        2. Else, try to load a previously-saved session from disk and verify it
           by hitting an authenticated endpoint (get_timeline_feed). If that
           succeeds the session is good — cache and return it.
        3. If there's no session OR it's expired, do a fresh password login,
           save the resulting session to disk for next time, and cache it.

    `password` is only required at step 3; on subsequent runs it can be empty.
    """
    with _clients_lock:
        # -- Step 1: in-memory cache hit -------------------------------------
        cached = _clients.get(username)
        if cached is not None:
            return cached

        sess_file = _session_path(username)
        cl = _new_client()

        # -- Step 2: try the disk-cached session -----------------------------
        if os.path.exists(sess_file):
            try:
                cl.load_settings(sess_file)
                cl.get_timeline_feed()  # cheap auth check
                _clients[username] = cl
                return cl
            except Exception:
                # Session expired or otherwise unusable. We'll fall through to
                # password login, but first reload the device fingerprint so
                # we look like the same device to Instagram (less suspicious).
                cl = _new_client()
                try:
                    cl.load_settings(sess_file)
                except Exception:
                    pass  # corrupted file — just proceed with a new device

        # -- Step 3: fresh password login ------------------------------------
        if not password:
            raise RuntimeError(
                "No valid cached session for this username. Provide a password to log in."
            )

        cl.login(username, password)
        try:
            cl.dump_settings(sess_file)
        except Exception:
            pass  # non-fatal: session won't be cached but the app still works

        _clients[username] = cl
        return cl


# =============================================================================
# 3. URL / SHORTCODE / USERNAME PARSERS
# =============================================================================
#
# Users paste all sorts of input. We accept:
#   * raw shortcodes      "DXXIFFyDHIs"
#   * reel URLs           "https://www.instagram.com/reel/DXXIFFyDHIs/?igsh=..."
#   * @usernames          "@atiazuhair"
#   * profile URLs        "https://www.instagram.com/atiazuhair/"
# ...and normalize them into a (shortcode | username) we can pass to instagrapi.

# Path segments under instagram.com that are NOT usernames. Used to avoid
# misinterpreting e.g. "instagram.com/reel/XYZ" as a profile named "reel".
_RESERVED_IG_PATHS = {
    "reel", "reels", "p", "tv", "stories", "explore", "accounts",
    "direct", "about", "developer", "legal", "press", "api",
}

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
_PROFILE_PATH_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")
_IG_MEDIA_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+",
    re.I,
)

_URL_COLUMN_NAMES = frozenset({
    "url", "link", "links", "reel", "reels", "reel_url", "reel_link",
    "instagram_url", "instagram", "ig_url", "post_url", "media_url",
})


def extract_shortcode(value: str) -> str:
    """Accept a raw shortcode OR a full reel/post URL; return just the shortcode."""
    value = value.strip()
    m = _SHORTCODE_RE.search(value)
    return m.group(1) if m else value


def extract_username(value: str) -> Optional[str]:
    """
    Accept a username or profile URL; return just the username.
    Returns None if the input is a reel/post URL — caller should resolve
    that via `resolve_target_username` instead.
    """
    value = value.strip().lstrip("@")

    # If it looks like a reel/post URL, bail out — we can't infer a username
    # from the URL alone; the caller needs to fetch the post first.
    if _SHORTCODE_RE.search(value):
        return None

    m = _PROFILE_PATH_RE.search(value)
    if m:
        candidate = m.group(1)
        if candidate.lower() in _RESERVED_IG_PATHS:
            return None
        return candidate

    # Plain username (maybe with a trailing slash)
    return value.rstrip("/")


def resolve_target_username(cl: Client, value: str) -> str:
    """
    Always return a username, even if the user pasted a reel URL.
    For reel URLs we fetch the post and read its `owner_username`.
    """
    direct = extract_username(value)
    if direct:
        return direct

    shortcode = extract_shortcode(value)
    media_pk = cl.media_pk_from_code(shortcode)
    return cl.media_info(media_pk).user.username


# =============================================================================
# 4. SCRAPING PRIMITIVES
# =============================================================================
#
# Two paths exist for fetching media:
#
#   * fetch_single_media() — hits i.instagram.com/api/v1/media/<pk>/info/
#       directly via private_request(). Returns the FULL count set, including
#       shares / saves / reposts. Used for /api/fetch (single reel).
#
#   * media_to_dict()      — extracts a lighter subset from an instagrapi Media
#       object (which is already in memory from user_clips_v1). Used for
#       /api/profile_reels — making a private_request per reel for a 100-reel
#       profile would 1) be slow and 2) get us rate-limited fast.
#
# We deliberately call the *_v1 variants of instagrapi methods to force the
# mobile API. The non-_v1 versions try GraphQL first, which returns the
# truncated viewer-filtered counts we want to avoid.


def media_to_dict(media) -> dict:
    """
    Light-weight extraction for the profile-reels table.
    Source: instagrapi Media object (already populated by user_clips_v1).
    """
    taken_at = getattr(media, "taken_at", None)
    views = getattr(media, "play_count", None) or getattr(media, "view_count", None)

    return {
        "shortcode": getattr(media, "code", None),
        "owner": media.user.username if getattr(media, "user", None) else None,
        "views": int(views) if views else None,
        "likes": int(getattr(media, "like_count", 0) or 0),
        "comments": int(getattr(media, "comment_count", 0) or 0),
        "date": taken_at.strftime("%Y-%m-%d %H:%M:%S") if taken_at else None,
        "is_video": getattr(media, "media_type", 0) == 2,  # 1=photo 2=video 8=album
        "caption": getattr(media, "caption_text", "") or "",
    }


def _as_int(value) -> Optional[int]:
    """Coerce API count values to int; return None when missing or invalid."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_repost_count(item: dict) -> Optional[int]:
    """Read repost count from known Instagram mobile-API field names."""
    for key in (
        "media_repost_count",
        "repost_count",
        "organic_media_repost_count",
        "reposts_count",
    ):
        if key in item:
            val = _as_int(item.get(key))
            if val is not None:
                return val
    for key, value in item.items():
        if isinstance(value, (dict, list)):
            continue
        kl = key.lower()
        if "repost" in kl and "count" in kl:
            val = _as_int(value)
            if val is not None:
                return val
    return None


def media_metric_fields(m: dict) -> dict:
    """Shared metric subset for single-reel and bulk CSV responses."""
    return {
        "views": m.get("views"),
        "likes": m.get("likes"),
        "comments": m.get("comments"),
        "shares": m.get("shares"),
        "saves": m.get("saves"),
        "reposts": m.get("reposts"),
        "date": m.get("date"),
    }


def fetch_single_media(cl: Client, media_pk) -> dict:
    """
    Full extraction for a single reel — hits the mobile API directly so we
    get the rich count set: shares, saves, reposts in addition to views/likes/comments.

    Why bypass cl.media_info()? Because instagrapi.media_info() tries the GraphQL
    endpoint FIRST and only falls back to the mobile API on failure. GraphQL
    returns viewer-filtered counts (way lower than the real numbers). By calling
    private_request() ourselves we always hit the mobile endpoint.
    """
    raw = cl.private_request(f"media/{media_pk}/info/")
    if not isinstance(raw, dict) or not raw.get("items"):
        raise RuntimeError("Media not found in response")

    item = raw["items"][0]
    user_obj = item.get("user") or {}
    caption_obj = item.get("caption") or {}
    caption_text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else ""

    # taken_at comes in as a Unix epoch integer.
    date_str = None
    if (ts := item.get("taken_at")):
        try:
            date_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    # Views: prefer total play_count (IG + FB), then IG-only, then unique-views.
    views = (
        item.get("play_count")
        or item.get("ig_play_count")
        or item.get("view_count")
    )

    return {
        "shortcode": item.get("code"),
        "owner":     user_obj.get("username"),
        "likes":     _as_int(item.get("like_count")),
        "comments":  _as_int(item.get("comment_count")),
        "views":     _as_int(views),
        "ig_views":  _as_int(item.get("ig_play_count")),
        "shares":    _as_int(item.get("reshare_count")),
        "saves":     _as_int(item.get("save_count")),
        "reposts":   _extract_repost_count(item),
        "date":      date_str,
        "is_video":  item.get("media_type") == 2,
        "caption":   caption_text,
    }


def comment_to_dict(comment, *, is_reply: bool = False, parent_pk=None) -> dict:
    """Serialize an instagrapi Comment for the single-reel UI."""
    user = getattr(comment, "user", None)
    created = getattr(comment, "created_at_utc", None)
    return {
        "pk": str(comment.pk),
        "username": user.username if user else None,
        "full_name": getattr(user, "full_name", None) if user else None,
        "text": comment.text or "",
        "likes": comment.like_count,
        "date": created.strftime("%Y-%m-%d %H:%M:%S") if created else None,
        "is_reply": is_reply,
        "parent_pk": str(parent_pk) if parent_pk else None,
    }


def fetch_media_comments(cl: Client, media_pk) -> tuple[list[dict], Optional[str]]:
    """
    Fetch every comment on a media item (top-level + replies).

    Uses the same dual-cursor pagination as instagrapi's media_comments_v1_chunk:
    pass both min_id and max_id on every page after the first, and keep going until
    Instagram returns an empty comments array.
    """
    media_id = cl.media_id(str(media_pk))
    comments: list[dict] = []
    note: Optional[str] = None
    min_id = ""
    max_id = ""
    seen_pks: set[str] = set()

    def append_replies(parent_pk: str, child_count: int) -> None:
        if not child_count:
            return
        try:
            replies = cl.media_comment_replies(media_id, parent_pk, amount=0)
        except Exception:
            return
        for reply in replies:
            comments.append(comment_to_dict(reply, is_reply=True, parent_pk=parent_pk))

    try:
        for _ in range(500):  # safety cap — 500 pages × ~15 = 7500 comments max
            params: dict = {
                "can_support_threading": "true",
                "permalink_enabled": "false",
            }
            if min_id:
                params["min_id"] = min_id
            if max_id:
                params["max_id"] = max_id

            result = cl.private_request(f"media/{media_id}/comments/", params)
            page = result.get("comments") or []
            if not page:
                break

            new_on_page = 0
            for raw in page:
                pk = str(raw.get("pk", ""))
                if not pk or pk in seen_pks:
                    continue
                seen_pks.add(pk)
                new_on_page += 1
                comment = extract_comment(raw)
                comments.append(comment_to_dict(comment))
                append_replies(str(comment.pk), int(raw.get("child_comment_count") or 0))

            if new_on_page == 0:
                break

            min_id = result.get("next_min_id") or result.get("min_id") or ""
            max_id = result.get("next_max_id") or result.get("max_id") or ""

    except CommentsDisabled:
        return [], "comments_disabled"
    except CommentUnavailable:
        return [], "comments_unavailable"
    except ClientError:
        note = "partial" if comments else None
        if not comments:
            return [], "partial"

    return comments, note


def reel_dict_without_comments(reel_dict: dict) -> dict:
    """Return a reel dict with empty comment fields (metrics-only row)."""
    out = dict(reel_dict)
    out["reel_comments"] = []
    out["comments_fetched"] = 0
    out["comments_note"] = None
    return out


def iter_user_clips_v1(cl: Client, user_id, limit: int = 0, page_size: int = _PROFILE_CLIPS_PAGE_SIZE):
    """
    Yield profile reels page-by-page from Instagram (progressive fetch).

    Uses user_clips_paginated_v1 so callers can process each page as it arrives
    instead of waiting for user_clips_v1 to download every page first.
    Default page_size matches the Instagram app (~50 reels per request).
    """
    next_cursor = ""
    yielded = 0
    while True:
        remaining = None if limit <= 0 else limit - yielded
        if remaining is not None and remaining <= 0:
            break

        fetch_amount = page_size if remaining is None else min(page_size, remaining)
        medias_page, next_cursor = cl.user_clips_paginated_v1(
            user_id, amount=fetch_amount, end_cursor=next_cursor
        )
        if not medias_page:
            break

        for media in medias_page:
            yield media
            yielded += 1
            if limit > 0 and yielded >= limit:
                return

        if not next_cursor:
            break


def media_to_reel_metrics(media) -> dict:
    """Convert a Media object to a metrics-only reel dict for streaming."""
    try:
        return reel_dict_without_comments(media_to_dict(media))
    except Exception as inner:
        return reel_dict_without_comments({
            "shortcode": getattr(media, "code", "?"),
            "date": None,
            "views": None,
            "likes": None,
            "comments": None,
            "caption": f"[error reading post: {inner}]",
            "is_video": None,
        })


def attach_reel_comments(cl: Client, media, reel_dict: dict) -> dict:
    """Fetch all Instagram comments for one profile reel and attach them to its dict."""
    out = dict(reel_dict)
    out["reel_comments"] = []
    out["comments_fetched"] = 0
    out["comments_note"] = None

    media_pk = getattr(media, "pk", None) or getattr(media, "id", None)
    if not media_pk:
        out["comments_note"] = "unavailable"
        return out

    try:
        comments, note = fetch_media_comments(cl, media_pk)
        out["reel_comments"] = comments
        out["comments_fetched"] = len(comments)
        out["comments_note"] = note
    except Exception:
        out["comments_note"] = "partial"

    return out


def compute_reel_date_range(reels_raw) -> dict:
    """
    Compute oldest / newest / span across a list of Media objects.

    Output is timezone-safe: any naive datetimes from instagrapi are assumed
    to be UTC, and both displays are normalised to UTC so the user can never
    be misled about the timezone.

    Returns counts of zero / None values when the input list is empty.
    """
    dates = []
    for m in reels_raw or []:
        t = getattr(m, "taken_at", None)
        if isinstance(t, datetime):
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            dates.append(t)

    if not dates:
        return {
            "oldest_iso": None, "newest_iso": None,
            "oldest_display": None, "newest_display": None,
            "oldest_date": None, "newest_date": None,
            "span_days": 0, "count": 0,
        }

    oldest = min(dates).astimezone(timezone.utc)
    newest = max(dates).astimezone(timezone.utc)
    return {
        "oldest_iso": oldest.isoformat(),
        "newest_iso": newest.isoformat(),
        "oldest_display": oldest.strftime("%b %d, %Y %H:%M UTC"),
        "newest_display": newest.strftime("%b %d, %Y %H:%M UTC"),
        "oldest_date": oldest.strftime("%b %d, %Y"),
        "newest_date": newest.strftime("%b %d, %Y"),
        "span_days": (newest.date() - oldest.date()).days,
        "count": len(dates),
    }


# =============================================================================
# 5. ERROR MAPPING (instagrapi exceptions -> clean JSON)
# =============================================================================
#
# Centralised so every route handles errors the same way. We map the specific
# exceptions to human-readable messages and meaningful HTTP status codes.


def error_message_from_exception(e: Exception, what: str = "Reel") -> str:
    """Human-readable error string for per-URL bulk failures (no HTTP response)."""
    if isinstance(e, UserNotFound):
        return f"{what} not found."
    if isinstance(e, PrivateAccount):
        return f"{what} is private and the logged-in account does not follow it."
    if isinstance(e, BadPassword):
        return "Bad password."
    if isinstance(e, TwoFactorRequired):
        return "Two-factor authentication required."
    if isinstance(e, ChallengeRequired):
        return "Instagram security challenge required — confirm in the app, then retry."
    if isinstance(e, LoginRequired):
        return "Login required (session expired). Provide your password."
    if isinstance(e, PleaseWaitFewMinutes):
        return "Instagram rate-limited this account. Wait a few minutes."
    if isinstance(e, ClientError):
        return f"Instagram refused the request: {e}"
    return f"{type(e).__name__}: {e}"


def is_valid_media_input(value: str) -> bool:
    """True when value is an Instagram reel/post URL or a bare shortcode."""
    value = value.strip()
    if _IG_MEDIA_URL_RE.search(value) or _SHORTCODE_RE.search(value):
        return True
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return not value.isdigit() and len(value) >= 6
    return False


def _row_is_header(row: list[str]) -> bool:
    """Detect a header row (column names, not reel data)."""
    if any(_IG_MEDIA_URL_RE.search(c) or _SHORTCODE_RE.search(c) for c in row):
        return False
    return any(c.strip().lower() in _URL_COLUMN_NAMES for c in row)


def _find_url_in_row(row: list[str]) -> Optional[str]:
    """Pick the Instagram reel/post URL from a CSV row, ignoring IDs and other columns."""
    for cell in row:
        val = cell.strip()
        if val and (_IG_MEDIA_URL_RE.search(val) or _SHORTCODE_RE.search(val)):
            return val
    non_empty = [c.strip() for c in row if c.strip()]
    if len(non_empty) == 1 and is_valid_media_input(non_empty[0]):
        return non_empty[0]
    return None


def parse_urls_from_csv(file_bytes: bytes) -> list[str]:
    """
    Extract reel URLs from an uploaded CSV.

    Priority:
      1. A named URL column (``url``, ``link``, ``reel_url``, etc.)
      2. Any cell in the row that contains an Instagram reel/post URL
      3. A single bare shortcode in the row

  Never uses numeric IDs or other non-URL columns.
    """
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    url_col_idx = next(
        (i for i, h in enumerate(header) if h in _URL_COLUMN_NAMES),
        None,
    )

    if url_col_idx is not None and _row_is_header(rows[0]):
        urls: list[str] = []
        for row in rows[1:]:
            if url_col_idx < len(row):
                val = row[url_col_idx].strip()
                if val:
                    urls.append(val)
        if urls:
            return urls

    data_start = 1 if _row_is_header(rows[0]) else 0
    urls = []
    for row in rows[data_start:]:
        found = _find_url_in_row(row)
        if found:
            urls.append(found)
    return urls


def process_reel_url(
    cl: Client,
    raw_code: str,
    *,
    fetch_comments: bool = True,
    reel_cache: Optional[dict[str, dict]] = None,
) -> dict:
    """
    Fetch metrics for one reel URL. Always returns a result dict with
    ``status`` of ``Success`` or ``Failed`` so bulk processing can continue.
    """
    raw_code = raw_code.strip()
    original_url = raw_code
    base = {
        "url": original_url,
        "reel_url": original_url,
        "views": None,
        "likes": None,
        "comments": None,
        "shares": None,
        "saves": None,
        "reposts": None,
        "date": None,
        "status": "Failed",
        "error": None,
        "shortcode": None,
        "caption": None,
        "reel_comments": [],
        "comments_fetched": 0,
        "comments_note": None,
    }
    if not raw_code:
        base["error"] = "Empty URL."
        return base
    if not is_valid_media_input(raw_code):
        base["error"] = "Not a valid Instagram reel/post URL or shortcode."
        return base

    try:
        shortcode = extract_shortcode(raw_code)
        if reel_cache is not None and shortcode in reel_cache:
            cached = dict(reel_cache[shortcode])
            cached["url"] = original_url
            cached["reel_url"] = original_url
            return cached

        with _scrape_delay(cl, fast=not fetch_comments):
            media_pk = cl.media_pk_from_code(shortcode)
            m = fetch_single_media(cl, media_pk)
            result = {
                "url": original_url,
                "reel_url": original_url,
                "shortcode": m.get("shortcode") or shortcode,
                "caption": m.get("caption") or "",
                **media_metric_fields(m),
                "reel_comments": [],
                "comments_fetched": 0,
                "comments_note": None,
                "status": "Success",
                "error": None,
            }
            if fetch_comments:
                comments, comments_note = fetch_media_comments(cl, media_pk)
                result["reel_comments"] = comments
                result["comments_fetched"] = len(comments)
                result["comments_note"] = comments_note
        if reel_cache is not None and result["status"] == "Success":
            reel_cache[shortcode] = dict(result)
        return result
    except Exception as e:
        base["reel_comments"] = []
        base["comments_fetched"] = 0
        base["comments_note"] = None
        base["error"] = error_message_from_exception(e)
        return base


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _parse_bulk_upload():
    """
    Validate a bulk CSV upload request.
    Returns (username, password, urls) or (None, None, None, error_response).
    """
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    csv_file = request.files.get("csv")

    if not username:
        return None, None, None, (jsonify(ok=False, error="Username is required."), 400)
    if not csv_file or not csv_file.filename:
        return None, None, None, (jsonify(ok=False, error="CSV file is required."), 400)

    try:
        urls = parse_urls_from_csv(csv_file.read())
    except UnicodeDecodeError:
        return None, None, None, (jsonify(ok=False, error="CSV must be UTF-8 encoded."), 400)
    except Exception as e:
        return None, None, None, (jsonify(ok=False, error=f"Could not read CSV: {e}"), 400)

    if not urls:
        return None, None, None, (
            jsonify(
                ok=False,
                error="No URLs found in CSV. Add one URL per row or a dedicated 'url' column.",
            ),
            400,
        )

    return username, password, urls, None


def handle_ig_error(e: Exception, what: str = "Resource"):
    """
    Convert any exception thrown by our scraping path into a (json, status)
    response tuple. `what` is the noun for "not found" / "private" messages
    (e.g. "Reel", "Profile").
    """
    if isinstance(e, UserNotFound):
        return jsonify(ok=False, error=f"{what} not found."), 404

    if isinstance(e, PrivateAccount):
        return jsonify(
            ok=False,
            error=f"{what} is private and the logged-in account does not follow it.",
        ), 403

    if isinstance(e, BadPassword):
        return jsonify(ok=False, error="Bad password."), 401

    if isinstance(e, TwoFactorRequired):
        return jsonify(
            ok=False,
            error="Two-factor authentication required. 2FA isn't wired into this UI yet; "
                  "log in once on the official Instagram app, then retry.",
        ), 401

    if isinstance(e, ChallengeRequired):
        return jsonify(
            ok=False,
            error="Instagram is asking for a security challenge (verification email/SMS). "
                  "Open instagram.com or the app, confirm it's really you, then retry here.",
        ), 401

    if isinstance(e, LoginRequired):
        return jsonify(ok=False, error="Login required (session expired). Provide your password."), 401

    if isinstance(e, PleaseWaitFewMinutes):
        return jsonify(ok=False, error="Instagram rate-limited this account. Wait a few minutes."), 429

    if isinstance(e, ClientError):
        return jsonify(ok=False, error=f"Instagram refused the request: {e}"), 502

    # Catch-all
    return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 500


# =============================================================================
# 6. HTTP ROUTES
# =============================================================================
#
# Each API route follows the same shape:
#   1. Parse + validate the JSON body.
#   2. Call get_client() to ensure we're logged in.
#   3. Do the scrape.
#   4. Return JSON. Any exception is funnelled into handle_ig_error().


@app.route("/")
def index():
    """Serve the frontend (index.html lives next to this file)."""
    return send_from_directory(PROJECT_DIR, "index.html")


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    """Fetch full metrics for a single reel (the Single Reel tab in the UI)."""
    body = request.get_json(silent=True) or {}
    username  = (body.get("username")  or "").strip()
    password  = (body.get("password")  or "")
    raw_code  = (body.get("shortcode") or "").strip()

    if not username:
        return jsonify(ok=False, error="Username is required."), 400
    if not raw_code:
        return jsonify(ok=False, error="Reel URL or shortcode is required."), 400

    try:
        cl = get_client(username, password or None)
        shortcode = extract_shortcode(raw_code)
        media_pk = cl.media_pk_from_code(shortcode)
        m = fetch_single_media(cl, media_pk)
        comments, comments_note = fetch_media_comments(cl, media_pk)

        return jsonify(
            ok=True,
            shortcode=m["shortcode"] or shortcode,
            ig_views=m["ig_views"],
            owner=m["owner"],
            is_video=m["is_video"],
            caption=(m["caption"] or "")[:500],
            reel_comments=comments,
            comments_fetched=len(comments),
            comments_note=comments_note,
            **media_metric_fields(m),
        )
    except Exception as e:
        return handle_ig_error(e, what="Reel")


@app.route("/api/reel_comments", methods=["POST"])
def api_reel_comments():
    """Fetch comments for a single reel on demand (profile / bulk rows)."""
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "")
    raw_code = (body.get("shortcode") or body.get("url") or "").strip()

    if not username:
        return jsonify(ok=False, error="Username is required."), 400
    if not raw_code:
        return jsonify(ok=False, error="Reel shortcode or URL is required."), 400
    if not is_valid_media_input(raw_code):
        return jsonify(ok=False, error="Not a valid Instagram reel/post URL or shortcode."), 400

    try:
        cl = get_client(username, password or None)
        shortcode = extract_shortcode(raw_code)
        media_pk = cl.media_pk_from_code(shortcode)
        comments, comments_note = fetch_media_comments(cl, media_pk)
        return jsonify(
            ok=True,
            shortcode=shortcode,
            reel_comments=comments,
            comments_fetched=len(comments),
            comments_note=comments_note,
        )
    except Exception as e:
        return handle_ig_error(e, what="Reel")


@app.route("/api/bulk_fetch", methods=["POST"])
def api_bulk_fetch():
    """Process multiple reel URLs from an uploaded CSV (Single Reel bulk mode)."""
    username, password, urls, err = _parse_bulk_upload()
    if err:
        return err

    try:
        cl = get_client(username, password or None)
    except Exception as e:
        return handle_ig_error(e, what="Login")

    results = []
    successful = 0
    failed = 0
    reel_cache: dict[str, dict] = {}
    for raw_url in urls:
        row = process_reel_url(cl, raw_url, fetch_comments=False, reel_cache=reel_cache)
        results.append(row)
        if row["status"] == "Success":
            successful += 1
        else:
            failed += 1

    return jsonify(
        ok=True,
        results=results,
        summary={
            "total": len(results),
            "successful": successful,
            "failed": failed,
        },
    )


@app.route("/api/bulk_fetch_stream", methods=["POST"])
def api_bulk_fetch_stream():
    """Stream per-URL progress while processing an uploaded CSV."""
    username, password, urls, err = _parse_bulk_upload()
    if err:
        return err

    total = len(urls)

    @stream_with_context
    def generate():
        yield _sse("start", {"total": total, "current": 0, "percent": 0})

        try:
            cl = get_client(username, password or None)
        except Exception as e:
            yield _sse("error", {"error": error_message_from_exception(e, what="Login")})
            return

        results = []
        successful = 0
        failed = 0
        reel_cache: dict[str, dict] = {}
        for i, raw_url in enumerate(urls, start=1):
            row = process_reel_url(cl, raw_url, fetch_comments=False, reel_cache=reel_cache)
            results.append(row)
            if row["status"] == "Success":
                successful += 1
            else:
                failed += 1
            yield _sse(
                "progress",
                {
                    "current": i,
                    "total": total,
                    "percent": round(i * 100 / total),
                    "row": row,
                    "successful": successful,
                    "failed": failed,
                },
            )

        yield _sse(
            "complete",
            {
                "ok": True,
                "results": results,
                "summary": {
                    "total": total,
                    "successful": successful,
                    "failed": failed,
                },
            },
        )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/profile_reels", methods=["POST"])
def api_profile_reels():
    """List a profile's reels with per-reel metrics (the Profile Reels tab)."""
    body = request.get_json(silent=True) or {}
    username    = (body.get("username") or "").strip()
    password    = (body.get("password") or "")
    target_raw  = (body.get("target")   or "").strip()

    if not username:
        return jsonify(ok=False, error="Login username is required."), 400
    if not target_raw:
        return jsonify(ok=False, error="Target username is required."), 400

    # `limit` controls how many reels to fetch. 0 = all.
    try:
        limit = max(0, int(body.get("limit", 20)))
    except (TypeError, ValueError):
        limit = 20

    target: Optional[str] = None
    try:
        cl = get_client(username, password or None)

        target = resolve_target_username(cl, target_raw)
        if not target:
            return jsonify(
                ok=False,
                error="Could not parse a username from the target field. "
                      "Enter a plain username (e.g. 'atiazuhair') or a profile URL.",
            ), 400

        # *_v1 endpoints force the mobile API (full counts; bypasses GraphQL).
        with _scrape_delay(cl, fast=True):
            user = cl.user_info_by_username_v1(target)
            reels_raw = cl.user_clips_v1(user.pk, amount=limit)

        # Convert each Media object to a plain dict for the JSON response.
        # We don't make a private_request per reel — that would be 1+N calls
        # for an N-reel profile, which Instagram rate-limits aggressively.
        reels = []
        for media in reels_raw:
            try:
                d = reel_dict_without_comments(media_to_dict(media))
                reels.append(d)
            except Exception as inner:
                # One bad reel shouldn't sink the whole fetch.
                reels.append({
                    "shortcode": getattr(media, "code", "?"),
                    "date": None, "views": None, "likes": None, "comments": None,
                    "caption": f"[error reading post: {inner}]",
                    "is_video": None,
                    "reel_comments": [],
                    "comments_fetched": 0,
                    "comments_note": "partial",
                })

        return jsonify(
            ok=True,
            resolved_target=target,
            profile={
                "username": user.username,
                "full_name": user.full_name,
                "followers": user.follower_count,
                "following": user.following_count,
                "posts":     user.media_count,
                "is_private": user.is_private,
            },
            date_range=compute_reel_date_range(reels_raw),
            reels=reels,
        )
    except Exception as e:
        return handle_ig_error(e, what=f"Profile '{target or target_raw}'")


@app.route("/api/profile_reels_stream", methods=["POST"])
def api_profile_reels_stream():
    """Stream profile reels incrementally (metrics only; comments on demand)."""
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "")
    target_raw = (body.get("target") or "").strip()

    if not username:
        return jsonify(ok=False, error="Login username is required."), 400
    if not target_raw:
        return jsonify(ok=False, error="Target username is required."), 400

    try:
        limit = max(0, int(body.get("limit", 20)))
    except (TypeError, ValueError):
        limit = 20

    @stream_with_context
    def generate():
        try:
            cl = get_client(username, password or None)
            target = resolve_target_username(cl, target_raw)
            if not target:
                yield _sse(
                    "error",
                    {
                        "error": "Could not parse a username from the target field. "
                        "Enter a plain username (e.g. 'atiazuhair') or a profile URL.",
                    },
                )
                return

            with _scrape_delay(cl, fast=True):
                user = cl.user_info_by_username_v1(target)

            yield _sse(
                "start",
                {
                    "resolved_target": target,
                    "profile": {
                        "username": user.username,
                        "full_name": user.full_name,
                        "followers": user.follower_count,
                        "following": user.following_count,
                        "posts": user.media_count,
                        "is_private": user.is_private,
                    },
                    "expected": limit if limit > 0 else None,
                    "total": None,
                },
            )

            reels_raw = []
            with _scrape_delay(cl, fast=True):
                for i, media in enumerate(iter_user_clips_v1(cl, user.pk, limit)):
                    reels_raw.append(media)
                    reel_metrics = media_to_reel_metrics(media)
                    current = i + 1
                    yield _sse(
                        "reel",
                        {
                            "index": i,
                            "current": current,
                            "total": limit if limit > 0 else None,
                            "expected": limit if limit > 0 else None,
                            "reel": reel_metrics,
                        },
                    )

            total = len(reels_raw)
            yield _sse(
                "complete",
                {
                    "ok": True,
                    "total": total,
                    "date_range": compute_reel_date_range(reels_raw),
                },
            )
        except Exception as e:
            yield _sse("error", {"error": error_message_from_exception(e, what="Profile")})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/debug_node", methods=["POST"])
def api_debug_node():
    """
    Diagnostic endpoint — returns every count-ish field Instagram sends back
    for a single reel. Used by the 'Debug Raw Node' button in the UI to
    sanity-check what fields exist (e.g. is `ig_play_count` present? is
    `reshare_count` populated?).
    """
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "")
    raw_code = (body.get("shortcode") or "").strip()

    if not username or not raw_code:
        return jsonify(ok=False, error="username and shortcode are required."), 400

    try:
        cl = get_client(username, password or None)
        shortcode = extract_shortcode(raw_code)
        media_pk = cl.media_pk_from_code(shortcode)

        raw = cl.private_request(f"media/{media_pk}/info/")
        item = (raw.get("items") or [{}])[0] if isinstance(raw, dict) else {}

        # Walk the mobile-API response and collect every scalar value whose
        # key mentions count/like/comment/view/play — i.e. anything that
        # might be a metric.
        def _collect(d, prefix=""):
            out = {}
            if not isinstance(d, dict):
                return out
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                kl = k.lower()
                if any(x in kl for x in ("count", "like", "comment", "view", "play")):
                    if not isinstance(v, (dict, list)):
                        out[full] = v
                if isinstance(v, dict):
                    out.update(_collect(v, full))
            return out

        iphone_fields = _collect(item)
        m = fetch_single_media(cl, media_pk)

        return jsonify(
            ok=True,
            shortcode=shortcode,
            owner=m["owner"],
            chosen_likes=m["likes"],
            chosen_comments=m["comments"],
            chosen_views=m["views"],
            graphql_fields={},  # we don't query GraphQL anymore — kept for UI compat
            iphone_fields=iphone_fields,
            iphone_available=bool(iphone_fields),
            iphone_error=None if iphone_fields else "mobile API returned no countable fields",
        )
    except Exception as e:
        return jsonify(ok=False, error=f"{type(e).__name__}: {e}"), 500


# =============================================================================
# 7. ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host="127.0.0.1", port=5000, debug=False)
