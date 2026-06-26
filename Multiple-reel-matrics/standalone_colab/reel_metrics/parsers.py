"""URL, shortcode, and username parsing."""

import re
from typing import Optional

from instagrapi import Client

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
    """Accept a raw shortcode or full reel/post URL; return the shortcode."""
    value = value.strip()
    match = _SHORTCODE_RE.search(value)
    return match.group(1) if match else value


def extract_username(value: str) -> Optional[str]:
    """Accept a username or profile URL; return the username."""
    value = value.strip().lstrip("@")

    if _SHORTCODE_RE.search(value):
        return None

    match = _PROFILE_PATH_RE.search(value)
    if match:
        candidate = match.group(1)
        if candidate.lower() in _RESERVED_IG_PATHS:
            return None
        return candidate

    return value.rstrip("/")


def resolve_target_username(cl: Client, value: str) -> str:
    """Return a username even when the user pasted a reel URL."""
    direct = extract_username(value)
    if direct:
        return direct

    shortcode = extract_shortcode(value)
    media_pk = cl.media_pk_from_code(shortcode)
    return cl.media_info(media_pk).user.username


def is_valid_media_input(value: str) -> bool:
    """True when value is an Instagram reel/post URL or a bare shortcode."""
    value = value.strip()
    if _IG_MEDIA_URL_RE.search(value) or _SHORTCODE_RE.search(value):
        return True
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return not value.isdigit() and len(value) >= 6
    return False


def row_is_header(row: list[str]) -> bool:
    """Detect a header row (column names, not reel data)."""
    if any(_IG_MEDIA_URL_RE.search(c) or _SHORTCODE_RE.search(c) for c in row):
        return False
    return any(c.strip().lower() in _URL_COLUMN_NAMES for c in row)


def find_url_in_row(row: list[str]) -> Optional[str]:
    """Pick the Instagram reel/post URL from a CSV row."""
    for cell in row:
        val = cell.strip()
        if val and (_IG_MEDIA_URL_RE.search(val) or _SHORTCODE_RE.search(val)):
            return val
    non_empty = [c.strip() for c in row if c.strip()]
    if len(non_empty) == 1 and is_valid_media_input(non_empty[0]):
        return non_empty[0]
    return None
