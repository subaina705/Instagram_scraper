"""
Standalone Instagram Reel Metrics — no web UI.

Fetch real Instagram Reel statistics (views, likes, comments, shares,
saves, reposts) using instagrapi's mobile API. Designed for scripts,
terminals, and Google Colab.
"""

from .api import bulk_fetch_reels, fetch_profile_reels, fetch_single_reel, process_reel_url
from .csv_io import parse_urls_from_csv, parse_urls_from_csv_path
from .display import (
    plot_reel_metrics,
    show_bulk_summary,
    show_comments_table,
    show_profile_summary,
    show_reels_table,
    show_single_reel_metrics,
)
from .session import get_client, new_client, session_path
from .scraping import fetch_media_comments, fetch_single_media

__all__ = [
    "bulk_fetch_reels",
    "fetch_media_comments",
    "fetch_profile_reels",
    "fetch_single_media",
    "fetch_single_reel",
    "get_client",
    "new_client",
    "parse_urls_from_csv",
    "parse_urls_from_csv_path",
    "plot_reel_metrics",
    "process_reel_url",
    "session_path",
    "show_bulk_summary",
    "show_comments_table",
    "show_profile_summary",
    "show_reels_table",
    "show_single_reel_metrics",
]
