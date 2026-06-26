"""Terminal and notebook display helpers (tables, summaries, charts)."""

from typing import Any, Optional

import pandas as pd


def _fmt_int(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show_profile_summary(profile: dict, date_range: Optional[dict] = None) -> None:
    """Print profile metadata and optional date span."""
    print_section("Profile Summary")
    print(f"  Username:   {profile.get('username')}")
    print(f"  Full name:  {profile.get('full_name')}")
    print(f"  Followers:  {_fmt_int(profile.get('followers'))}")
    print(f"  Following:  {_fmt_int(profile.get('following'))}")
    print(f"  Posts:      {_fmt_int(profile.get('posts'))}")
    print(f"  Private:    {profile.get('is_private')}")
    if date_range and date_range.get("count"):
        print(f"  Reel span:  {date_range.get('oldest_date')} → {date_range.get('newest_date')}")
        print(f"  Span days:  {date_range.get('span_days')}")
        print(f"  Reels:      {date_range.get('count')}")


def reels_to_dataframe(reels: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from reel metric dicts."""
    rows = []
    for r in reels:
        rows.append({
            "shortcode": r.get("shortcode"),
            "owner": r.get("owner"),
            "date": r.get("date"),
            "views": r.get("views"),
            "likes": r.get("likes"),
            "comments": r.get("comments"),
            "shares": r.get("shares"),
            "saves": r.get("saves"),
            "reposts": r.get("reposts"),
            "status": r.get("status"),
            "url": r.get("url") or r.get("reel_url"),
        })
    return pd.DataFrame(rows)


def show_reels_table(reels: list[dict], title: str = "Reel Metrics") -> pd.DataFrame:
    """Print a formatted table of reel metrics and return the DataFrame."""
    df = reels_to_dataframe(reels)
    print_section(title)
    if df.empty:
        print("  No reels to display.")
        return df
    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        "display.width", 120,
        "display.max_colwidth", 40,
    ):
        print(df.to_string(index=True))
    return df


def show_single_reel_metrics(metrics: dict) -> None:
    """Print metrics for one reel as a key-value table."""
    print_section("Single Reel Metrics")
    fields = [
        ("Shortcode", metrics.get("shortcode")),
        ("Owner", metrics.get("owner")),
        ("Date", metrics.get("date")),
        ("Views", _fmt_int(metrics.get("views"))),
        ("IG views", _fmt_int(metrics.get("ig_views"))),
        ("Likes", _fmt_int(metrics.get("likes"))),
        ("Comments", _fmt_int(metrics.get("comments"))),
        ("Shares", _fmt_int(metrics.get("shares"))),
        ("Saves", _fmt_int(metrics.get("saves"))),
        ("Reposts", _fmt_int(metrics.get("reposts"))),
        ("Video", metrics.get("is_video")),
    ]
    for label, value in fields:
        print(f"  {label:12} {value}")
    caption = (metrics.get("caption") or "").strip()
    if caption:
        preview = caption[:300] + ("…" if len(caption) > 300 else "")
        print(f"  Caption:      {preview}")


def comments_to_dataframe(comments: list[dict]) -> pd.DataFrame:
    rows = []
    for c in comments:
        rows.append({
            "username": c.get("username"),
            "text": c.get("text"),
            "likes": c.get("likes"),
            "date": c.get("date"),
            "is_reply": c.get("is_reply"),
            "parent_pk": c.get("parent_pk"),
        })
    return pd.DataFrame(rows)


def show_comments_table(
    comments: list[dict],
    title: str = "Comments",
    max_rows: int = 50,
) -> pd.DataFrame:
    """Print comments (truncated) and return the full DataFrame."""
    df = comments_to_dataframe(comments)
    print_section(title)
    print(f"  Total comments fetched: {len(df)}")
    if df.empty:
        print("  No comments.")
        return df
    display_df = df.head(max_rows)
    with pd.option_context(
        "display.max_rows", max_rows,
        "display.max_columns", None,
        "display.width", 120,
        "display.max_colwidth", 60,
    ):
        print(display_df.to_string(index=True))
    if len(df) > max_rows:
        print(f"  … showing first {max_rows} of {len(df)} comments")
    return df


def show_bulk_summary(summary: dict) -> None:
    print_section("Bulk Fetch Summary")
    print(f"  Total:      {summary.get('total')}")
    print(f"  Successful: {summary.get('successful')}")
    print(f"  Failed:     {summary.get('failed')}")


def plot_reel_metrics(
    reels: list[dict],
    metrics: tuple[str, ...] = ("views", "likes", "comments"),
    title: str = "Reel Metrics Comparison",
) -> None:
    """
    Bar chart of numeric metrics per reel (matplotlib).

    Works in Google Colab and local terminals with a display backend.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping chart.")
        return

    df = reels_to_dataframe(reels)
    if df.empty:
        return

    labels = df["shortcode"].fillna(df.index.astype(str)).tolist()
    x = range(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.6), 5))
    offsets = [-width, 0, width]
    plotted = 0
    for i, metric in enumerate(metrics):
        if metric not in df.columns:
            continue
        values = pd.to_numeric(df[metric], errors="coerce").fillna(0)
        ax.bar(
            [xi + offsets[plotted] for xi in x],
            values,
            width,
            label=metric,
        )
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Count")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    plt.show()
