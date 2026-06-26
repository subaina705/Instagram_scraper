#!/usr/bin/env python3
"""Generate a self-contained Google Colab notebook with embedded reel_metrics package."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "reel_metrics"
OUT = ROOT / "Instagram_Reel_Metrics.ipynb"

MODULE_FILES = [
    "errors.py",
    "parsers.py",
    "session.py",
    "scraping.py",
    "csv_io.py",
    "display.py",
    "api.py",
    "__init__.py",
]


def read_modules() -> dict[str, str]:
    files = {}
    for name in MODULE_FILES:
        files[f"reel_metrics/{name}"] = (PKG / name).read_text(encoding="utf-8")
    return files


def bootstrap_cell_source(files: dict[str, str]) -> str:
    lines = [
        '"""Bootstrap reel_metrics package (runs automatically if not already present)."""',
        "import os",
        "import sys",
        "import importlib",
        "",
        "MODULES = " + repr(files),
        "",
        "def bootstrap_package():",
        "    if os.path.isdir('reel_metrics') and os.path.isfile('reel_metrics/__init__.py'):",
        "        return",
        "    for rel_path, content in MODULES.items():",
        "        os.makedirs(os.path.dirname(rel_path), exist_ok=True)",
        "        with open(rel_path, 'w', encoding='utf-8') as f:",
        "            f.write(content)",
        "    print(f'Created {len(MODULES)} module files in reel_metrics/')",
        "",
        "bootstrap_package()",
        "",
        "if '.' not in sys.path:",
        "    sys.path.insert(0, '.')",
        "elif sys.path[0] != '.':",
        "    sys.path.insert(0, '.')",
        "",
        "import reel_metrics",
        "importlib.reload(reel_metrics)",
        "print('reel_metrics ready.')",
    ]
    return "\n".join(lines)


def cell(typ: str, source: str) -> dict:
    return {
        "cell_type": typ,
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code(source: str) -> dict:
    c = cell("code", source)
    c["execution_count"] = None
    c["outputs"] = []
    return c


def markdown(source: str) -> dict:
    return cell("markdown", source)


def build_notebook() -> dict:
    files = read_modules()
    bootstrap = bootstrap_cell_source(files)

    cells = [
        markdown(
            "# Instagram Reel Metrics — Google Colab\n"
            "\n"
            "Fetch **real** Instagram Reel statistics (views, likes, comments, shares, saves, reposts) "
            "using Python only — no web browser UI required.\n"
            "\n"
            "## How to use\n"
            "\n"
            "1. **Run cells in order** (Runtime → Run all, or Shift+Enter through each cell).\n"
            "2. **Cell 1** installs dependencies.\n"
            "3. **Cell 2** creates the `reel_metrics` package automatically (self-contained — no extra uploads needed).\n"
            "4. **Cell 3** — enter your Instagram login.\n"
            "5. Pick a mode below: **Single Reel**, **Profile Reels**, or **Bulk CSV**.\n"
            "\n"
            "> **Note:** Use a real Instagram account. Sessions are cached in `.ig_sessions/` for the current Colab runtime.\n"
            "\n"
            "See `COLAB_GUIDE.md` in the repo for the full written guide."
        ),
        code(
            "# Step 1 — Install dependencies\n"
            "!pip install -q instagrapi==2.16.25 pandas matplotlib\n"
            "\n"
            "import IPython\n"
            "print('Dependencies installed. Python:', IPython.sys_info()['python_version'])"
        ),
        code(bootstrap),
        code(
            "from reel_metrics import (\n"
            "    bulk_fetch_reels,\n"
            "    fetch_profile_reels,\n"
            "    fetch_single_reel,\n"
            "    get_client,\n"
            "    parse_urls_from_csv,\n"
            "    plot_reel_metrics,\n"
            "    show_bulk_summary,\n"
            "    show_comments_table,\n"
            "    show_profile_summary,\n"
            "    show_reels_table,\n"
            "    show_single_reel_metrics,\n"
            ")\n"
            "\n"
            "print('All functions imported successfully.')"
        ),
        markdown(
            "## Step 2 — Login\n"
            "\n"
            "Set your Instagram credentials below. The password is only required on the first login "
            "in each Colab session (or when the session expires)."
        ),
        code(
            "from getpass import getpass\n"
            "\n"
            "# ── CONFIGURE HERE ──────────────────────────────────────────────\n"
            "IG_USERNAME = \"your_instagram_username\"  # login account (no @)\n"
            "\n"
            "# Option A: type password here (less secure if you share the notebook)\n"
            "IG_PASSWORD = \"\"\n"
            "\n"
            "# Option B: leave IG_PASSWORD empty and uncomment the next line\n"
            "# IG_PASSWORD = getpass(\"Instagram password: \")\n"
            "# ─────────────────────────────────────────────────────────────────\n"
            "\n"
            "try:\n"
            "    client = get_client(IG_USERNAME, IG_PASSWORD or None)\n"
            "    print(f\"Authenticated as @{IG_USERNAME}\")\n"
            "except Exception as e:\n"
            "    print(f\"Login failed: {e}\")\n"
            "    print(\"Tip: set IG_PASSWORD and re-run this cell.\")"
        ),
        markdown(
            "---\n"
            "## Mode 1 — Single Reel\n"
            "\n"
            "Full metrics for one reel: views, likes, comments, shares, saves, reposts, plus comments list.\n"
            "\n"
            "Accepted input: reel URL, post URL, or bare shortcode."
        ),
        code(
            "# ── CONFIGURE HERE ──────────────────────────────────────────────\n"
            "REEL_URL = \"https://www.instagram.com/reel/EXAMPLE_SHORTCODE/\"\n"
            "FETCH_COMMENTS = True  # set False to skip comments (faster)\n"
            "# ─────────────────────────────────────────────────────────────────\n"
            "\n"
            "try:\n"
            "    reel = fetch_single_reel(client, REEL_URL, fetch_comments=FETCH_COMMENTS)\n"
            "    show_single_reel_metrics(reel)\n"
            "    if FETCH_COMMENTS and reel.get('reel_comments'):\n"
            "        df_comments = show_comments_table(reel['reel_comments'])\n"
            "    else:\n"
            "        print(f\"\\nComments: {reel.get('comments_fetched', 0)} fetched\")\n"
            "except Exception as e:\n"
            "    print(f\"Error: {e}\")"
        ),
        markdown(
            "---\n"
            "## Mode 2 — Profile Reels\n"
            "\n"
            "Fetch reels from a public Instagram profile.\n"
            "\n"
            "| `LIMIT` | Behavior |\n"
            "|---------|----------|\n"
            "| `20` | First 20 reels (default) |\n"
            "| `0` | All reels (slow for large accounts) |"
        ),
        code(
            "# ── CONFIGURE HERE ──────────────────────────────────────────────\n"
            "TARGET = \"atiazuhair\"  # username, @username, profile URL, or reel URL\n"
            "LIMIT = 20             # 0 = fetch all reels\n"
            "SHOW_CHART = True\n"
            "# ─────────────────────────────────────────────────────────────────\n"
            "\n"
            "try:\n"
            "    profile_data = fetch_profile_reels(\n"
            "        client,\n"
            "        TARGET,\n"
            "        limit=LIMIT,\n"
            "        on_reel=lambda i, r: print(f\"  [{i + 1}] {r.get('shortcode')} — \"\n"
            "                                     f\"views={r.get('views')} likes={r.get('likes')}\"),\n"
            "    )\n"
            "\n"
            "    show_profile_summary(profile_data['profile'], profile_data['date_range'])\n"
            "    df_profile = show_reels_table(\n"
            "        profile_data['reels'],\n"
            "        title=f\"Profile Reels — @{profile_data['resolved_target']}\",\n"
            "    )\n"
            "\n"
            "    if SHOW_CHART and profile_data['reels']:\n"
            "        plot_reel_metrics(\n"
            "            profile_data['reels'],\n"
            "            title=f\"@{profile_data['resolved_target']} — Reel Metrics\",\n"
            "        )\n"
            "except Exception as e:\n"
            "    print(f\"Error: {e}\")"
        ),
        markdown(
            "---\n"
            "## Mode 3 — Bulk CSV\n"
            "\n"
            "Upload a CSV with reel URLs (one per row, or a column named `url` / `link` / `reel_url`).\n"
            "\n"
            "**Example CSV:**\n"
            "```\n"
            "url\n"
            "https://www.instagram.com/reel/ABC123/\n"
            "https://www.instagram.com/reel/XYZ789/\n"
            "```"
        ),
        code(
            "from google.colab import files\n"
            "\n"
            "print('Select your CSV file...')\n"
            "uploaded = files.upload()\n"
            "\n"
            "if not uploaded:\n"
            "    print('No file uploaded.')\n"
            "else:\n"
            "    csv_name = next(iter(uploaded))\n"
            "    urls = parse_urls_from_csv(uploaded[csv_name])\n"
            "    print(f'File: {csv_name}')\n"
            "    print(f'URLs found: {len(urls)}')\n"
            "    for i, u in enumerate(urls[:5], 1):\n"
            "        print(f'  {i}. {u}')\n"
            "    if len(urls) > 5:\n"
            "        print(f'  ... and {len(urls) - 5} more')"
        ),
        code(
            "# Run bulk fetch (requires URLs from the upload cell above)\n"
            "FETCH_BULK_COMMENTS = False  # True = much slower\n"
            "\n"
            "try:\n"
            "    _url_list = urls\n"
            "except NameError:\n"
            "    _url_list = []\n"
            "\n"
            "if not _url_list:\n"
            "    print('Upload a CSV first (run the cell above).')\n"
            "else:\n"
            "    try:\n"
            "        bulk = bulk_fetch_reels(\n"
            "            client,\n"
            "            _url_list,\n"
            "            fetch_comments=FETCH_BULK_COMMENTS,\n"
            "            on_progress=lambda c, t, row: print(\n"
            "                f\"[{c}/{t}] {row.get('status')}: \"\n"
            "                f\"{row.get('shortcode') or row.get('url')}\"\n"
            "                + (f\" — {row.get('error')}\" if row.get('error') else '')\n"
            "            ),\n"
            "        )\n"
            "\n"
            "        show_bulk_summary(bulk['summary'])\n"
            "        df_bulk = show_reels_table(bulk['results'], title='Bulk Fetch Results')\n"
            "\n"
            "        successful = [r for r in bulk['results'] if r.get('status') == 'Success']\n"
            "        if successful:\n"
            "            plot_reel_metrics(successful, title='Bulk Fetch — Successful Reels')\n"
            "    except Exception as e:\n"
            "        print(f'Error: {e}')"
        ),
        markdown(
            "---\n"
            "## Export Results\n"
            "\n"
            "Download the last profile or bulk results table as CSV."
        ),
        code(
            "from google.colab import files\n"
            "import os\n"
            "\n"
            "export_path = 'instagram_reels_export.csv'\n"
            "\n"
            "try:\n"
            "    _df_bulk = df_bulk\n"
            "except NameError:\n"
            "    _df_bulk = None\n"
            "try:\n"
            "    _df_profile = df_profile\n"
            "except NameError:\n"
            "    _df_profile = None\n"
            "\n"
            "if _df_bulk is not None and not _df_bulk.empty:\n"
            "    _df_bulk.to_csv(export_path, index=False)\n"
            "    print(f'Saved bulk results → {export_path} ({len(_df_bulk)} rows)')\n"
            "elif _df_profile is not None and not _df_profile.empty:\n"
            "    _df_profile.to_csv(export_path, index=False)\n"
            "    print(f'Saved profile reels → {export_path} ({len(_df_profile)} rows)')\n"
            "else:\n"
            "    print('Run Profile Reels or Bulk CSV mode first to generate data.')\n"
            "    export_path = None\n"
            "\n"
            "if export_path and os.path.isfile(export_path):\n"
            "    files.download(export_path)"
        ),
        markdown(
            "---\n"
            "## Troubleshooting\n"
            "\n"
            "| Problem | Fix |\n"
            "|---------|-----|\n"
            "| `Login failed` | Set `IG_PASSWORD` and re-run login cell |\n"
            "| `rate-limited` | Wait 10–15 min, reduce `LIMIT` or bulk size |\n"
            "| `ChallengeRequired` | Open Instagram app, confirm login, retry |\n"
            "| `Profile is private` | Log in with an account that follows that profile |\n"
            "| `ModuleNotFoundError` | Re-run Cell 2 (bootstrap) |\n"
            "| Runtime disconnected | Re-run from Cell 1 (install + bootstrap + login) |"
        ),
    ]

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
            "colab": {
                "provenance": [],
                "name": "Instagram_Reel_Metrics.ipynb",
            },
        },
        "cells": cells,
    }


def main() -> None:
    nb = build_notebook()
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
