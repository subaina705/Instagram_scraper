"""High-level API for fetching Instagram reel metrics."""

from typing import Callable, Optional

from instagrapi import Client

from .errors import error_message_from_exception
from .parsers import extract_shortcode, is_valid_media_input, resolve_target_username
from .scraping import (
    compute_reel_date_range,
    fetch_media_comments,
    fetch_single_media,
    iter_user_clips_v1,
    media_metric_fields,
    media_to_dict,
    media_to_reel_metrics,
    reel_dict_without_comments,
)


def process_reel_url(
    cl: Client,
    raw_code: str,
    *,
    fetch_comments: bool = True,
) -> dict:
    """Fetch metrics for one reel URL. Always returns a result dict with status."""
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
        return result
    except Exception as e:
        base["reel_comments"] = []
        base["comments_fetched"] = 0
        base["comments_note"] = None
        base["error"] = error_message_from_exception(e)
        return base


def fetch_single_reel(
    cl: Client,
    reel_input: str,
    *,
    fetch_comments: bool = True,
) -> dict:
    """
    Fetch full metrics for a single reel.

    Returns a dict with metrics, comments (optional), and status fields.
    Raises on login/network errors before scraping starts.
    """
    result = process_reel_url(cl, reel_input, fetch_comments=fetch_comments)
    if result["status"] != "Success":
        raise RuntimeError(result.get("error") or "Failed to fetch reel.")
    return result


def fetch_profile_reels(
    cl: Client,
    target_raw: str,
    limit: int = 20,
    *,
    on_reel: Optional[Callable[[int, dict], None]] = None,
) -> dict:
    """
    List reels for a profile with per-reel metrics.

    ``on_reel`` is called with (index, reel_dict) as each reel is fetched
    (useful for progressive display in notebooks).
    """
    target = resolve_target_username(cl, target_raw)
    if not target:
        raise ValueError(
            "Could not parse a username from the target. "
            "Enter a plain username or profile URL."
        )

    user = cl.user_info_by_username_v1(target)
    reels: list[dict] = []
    reels_raw: list = []

    if on_reel is not None:
        for i, media in enumerate(iter_user_clips_v1(cl, user.pk, limit)):
            reels_raw.append(media)
            reel = media_to_reel_metrics(media)
            reels.append(reel)
            on_reel(i, reel)
    else:
        if limit > 0:
            medias = cl.user_clips_v1(user.pk, amount=limit)
        else:
            medias = list(iter_user_clips_v1(cl, user.pk, limit=0))
        reels_raw = medias
        for media in medias:
            try:
                reels.append(reel_dict_without_comments(media_to_dict(media)))
            except Exception as inner:
                reels.append({
                    "shortcode": getattr(media, "code", "?"),
                    "date": None,
                    "views": None,
                    "likes": None,
                    "comments": None,
                    "caption": f"[error reading post: {inner}]",
                    "is_video": None,
                    "reel_comments": [],
                    "comments_fetched": 0,
                    "comments_note": "partial",
                })

    profile = {
        "username": user.username,
        "full_name": user.full_name,
        "followers": user.follower_count,
        "following": user.following_count,
        "posts": user.media_count,
        "is_private": user.is_private,
    }

    return {
        "resolved_target": target,
        "profile": profile,
        "date_range": compute_reel_date_range(reels_raw),
        "reels": reels,
    }


def bulk_fetch_reels(
    cl: Client,
    urls: list[str],
    *,
    fetch_comments: bool = False,
    on_progress: Optional[Callable[[int, int, dict], None]] = None,
) -> dict:
    """
    Process multiple reel URLs.

    ``on_progress`` receives (current, total, row_dict) after each URL.
    """
    results = []
    successful = 0
    failed = 0
    total = len(urls)

    for i, raw_url in enumerate(urls, start=1):
        row = process_reel_url(cl, raw_url, fetch_comments=fetch_comments)
        results.append(row)
        if row["status"] == "Success":
            successful += 1
        else:
            failed += 1
        if on_progress:
            on_progress(i, total, row)

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "successful": successful,
            "failed": failed,
        },
    }
