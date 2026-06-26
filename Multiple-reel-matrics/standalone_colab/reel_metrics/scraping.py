"""Media metrics, comments, and profile reel fetching."""

from datetime import datetime, timezone
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import ClientError, CommentUnavailable, CommentsDisabled
from instagrapi.extractors import extract_comment


def media_to_dict(media) -> dict:
    """Light-weight extraction from an instagrapi Media object."""
    taken_at = getattr(media, "taken_at", None)
    views = getattr(media, "play_count", None) or getattr(media, "view_count", None)

    return {
        "shortcode": getattr(media, "code", None),
        "owner": media.user.username if getattr(media, "user", None) else None,
        "views": int(views) if views else None,
        "likes": int(getattr(media, "like_count", 0) or 0),
        "comments": int(getattr(media, "comment_count", 0) or 0),
        "date": taken_at.strftime("%Y-%m-%d %H:%M:%S") if taken_at else None,
        "is_video": getattr(media, "media_type", 0) == 2,
        "caption": getattr(media, "caption_text", "") or "",
    }


def _as_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_repost_count(item: dict) -> Optional[int]:
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
    """Shared metric subset for single-reel and bulk responses."""
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
    """Full extraction via the mobile API (shares, saves, reposts included)."""
    raw = cl.private_request(f"media/{media_pk}/info/")
    if not isinstance(raw, dict) or not raw.get("items"):
        raise RuntimeError("Media not found in response")

    item = raw["items"][0]
    user_obj = item.get("user") or {}
    caption_obj = item.get("caption") or {}
    caption_text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else ""

    date_str = None
    if (ts := item.get("taken_at")):
        try:
            date_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    views = (
        item.get("play_count")
        or item.get("ig_play_count")
        or item.get("view_count")
    )

    return {
        "shortcode": item.get("code"),
        "owner": user_obj.get("username"),
        "likes": _as_int(item.get("like_count")),
        "comments": _as_int(item.get("comment_count")),
        "views": _as_int(views),
        "ig_views": _as_int(item.get("ig_play_count")),
        "shares": _as_int(item.get("reshare_count")),
        "saves": _as_int(item.get("save_count")),
        "reposts": _extract_repost_count(item),
        "date": date_str,
        "is_video": item.get("media_type") == 2,
        "caption": caption_text,
    }


def comment_to_dict(comment, *, is_reply: bool = False, parent_pk=None) -> dict:
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
    """Fetch every comment on a media item (top-level + replies)."""
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
        for _ in range(500):
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
    out = dict(reel_dict)
    out["reel_comments"] = []
    out["comments_fetched"] = 0
    out["comments_note"] = None
    return out


def iter_user_clips_v1(cl: Client, user_id, limit: int = 0, page_size: int = 12):
    """Yield profile reels page-by-page from Instagram."""
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


def compute_reel_date_range(reels_raw) -> dict:
    """Compute oldest / newest / span across a list of Media objects."""
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
