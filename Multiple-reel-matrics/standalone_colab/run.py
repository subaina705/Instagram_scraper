#!/usr/bin/env python3
"""
Command-line entry point for standalone Instagram Reel Metrics.

Examples:
    python run.py login --username my_ig_account
    python run.py single --username my_ig_account --url "https://www.instagram.com/reel/ABC123/"
    python run.py profile --username my_ig_account --target atiazuhair --limit 20
    python run.py bulk --username my_ig_account --csv urls.csv
"""

import argparse
import getpass
import os
import sys
from typing import Optional

# Allow running from standalone_colab/ without installing the package.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from reel_metrics import (
    bulk_fetch_reels,
    fetch_profile_reels,
    fetch_single_reel,
    get_client,
    parse_urls_from_csv_path,
    plot_reel_metrics,
    show_bulk_summary,
    show_comments_table,
    show_profile_summary,
    show_reels_table,
    show_single_reel_metrics,
)


def _add_login_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--username", "-u",
        required=True,
        help="Instagram login username (the account used to authenticate).",
    )
    parser.add_argument(
        "--password", "-p",
        default=None,
        help="Instagram password (omit to use cached session or prompt securely).",
    )
    parser.add_argument(
        "--session-dir",
        default=None,
        help="Directory for cached session files (default: ./.ig_sessions).",
    )


def _resolve_password(password: Optional[str]) -> Optional[str]:
    if password:
        return password
    if sys.stdin.isatty():
        return getpass.getpass("Instagram password (leave empty if session cached): ")
    return None


def cmd_login(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password)
    try:
        get_client(args.username, password, session_dir=args.session_dir)
        print(f"Logged in as {args.username}. Session cached for reuse.")
        return 0
    except Exception as e:
        print(f"Login failed: {e}")
        return 1


def cmd_single(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password)
    try:
        cl = get_client(args.username, password, session_dir=args.session_dir)
        result = fetch_single_reel(
            cl,
            args.url,
            fetch_comments=not args.no_comments,
        )
        show_single_reel_metrics(result)
        if not args.no_comments and result.get("reel_comments"):
            show_comments_table(result["reel_comments"])
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_profile(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password)
    try:
        cl = get_client(args.username, password, session_dir=args.session_dir)

        def on_reel(i: int, reel: dict) -> None:
            print(f"  Fetched reel {i + 1}: {reel.get('shortcode')}")

        data = fetch_profile_reels(
            cl,
            args.target,
            limit=args.limit,
            on_reel=on_reel if args.verbose else None,
        )
        show_profile_summary(data["profile"], data.get("date_range"))
        df = show_reels_table(data["reels"], title=f"Profile Reels — @{data['resolved_target']}")
        if args.plot and not df.empty:
            plot_reel_metrics(data["reels"])
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_bulk(args: argparse.Namespace) -> int:
    password = _resolve_password(args.password)
    try:
        urls = parse_urls_from_csv_path(args.csv)
        if not urls:
            print("No URLs found in CSV.")
            return 1

        cl = get_client(args.username, password, session_dir=args.session_dir)

        def on_progress(current: int, total: int, row: dict) -> None:
            status = row.get("status")
            shortcode = row.get("shortcode") or row.get("url")
            print(f"  [{current}/{total}] {status}: {shortcode}")

        data = bulk_fetch_reels(
            cl,
            urls,
            fetch_comments=args.comments,
            on_progress=on_progress if args.verbose else None,
        )
        show_bulk_summary(data["summary"])
        df = show_reels_table(data["results"], title="Bulk Fetch Results")
        if args.plot and not df.empty:
            successful = [r for r in data["results"] if r.get("status") == "Success"]
            if successful:
                plot_reel_metrics(successful, title="Bulk Fetch — Successful Reels")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone Instagram Reel Metrics (no web UI).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    login_p = sub.add_parser("login", help="Authenticate and cache session.")
    _add_login_args(login_p)
    login_p.set_defaults(func=cmd_login)

    single_p = sub.add_parser("single", help="Fetch metrics for one reel.")
    _add_login_args(single_p)
    single_p.add_argument("--url", required=True, help="Reel URL or shortcode.")
    single_p.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip fetching comments.",
    )
    single_p.set_defaults(func=cmd_single)

    profile_p = sub.add_parser("profile", help="Fetch reels from a profile.")
    _add_login_args(profile_p)
    profile_p.add_argument(
        "--target", "-t",
        required=True,
        help="Target username, profile URL, or reel URL.",
    )
    profile_p.add_argument(
        "--limit", "-n",
        type=int,
        default=20,
        help="Max reels to fetch (0 = all). Default: 20.",
    )
    profile_p.add_argument("--plot", action="store_true", help="Show bar chart.")
    profile_p.add_argument("--verbose", "-v", action="store_true", help="Progress output.")
    profile_p.set_defaults(func=cmd_profile)

    bulk_p = sub.add_parser("bulk", help="Fetch metrics from a CSV of URLs.")
    _add_login_args(bulk_p)
    bulk_p.add_argument("--csv", required=True, help="Path to CSV file with reel URLs.")
    bulk_p.add_argument("--comments", action="store_true", help="Fetch comments per reel.")
    bulk_p.add_argument("--plot", action="store_true", help="Show bar chart.")
    bulk_p.add_argument("--verbose", "-v", action="store_true", help="Progress output.")
    bulk_p.set_defaults(func=cmd_bulk)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
