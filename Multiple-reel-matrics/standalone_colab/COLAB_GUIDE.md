# Google Colab Guide — Instagram Reel Metrics

This guide is for the **standalone** version in `standalone_colab/`. It does not use the web UI (`index.html`, Flask, etc.).

> **Quick start:** Upload only `Instagram_Reel_Metrics.ipynb` to [Google Colab](https://colab.research.google.com/), then **Runtime → Run all**. The notebook installs dependencies and creates the `reel_metrics` package automatically — no zip upload required.

---

## What You Need

| Item | Details |
|------|---------|
| **Google account** | To run Colab |
| **Instagram account** | A real IG login (used to authenticate with Instagram's mobile API) |
| **Target content** | Public reel URLs, profile usernames, or a CSV of URLs |
| **Files** | The whole `standalone_colab` folder (not just the notebook) |

---

## Step 1 — Get the Code into Colab

### Option A — Upload notebook only (recommended)

1. Open [Google Colab](https://colab.research.google.com/).
2. **File → Upload notebook** → choose `Instagram_Reel_Metrics.ipynb`.
3. **Runtime → Run all** (or run cells top to bottom).

The notebook is **self-contained**: Cell 2 automatically writes the full `reel_metrics` Python package. You do **not** need to upload any other files.

### Option B — Upload the full folder

If you cloned or downloaded the repo, you can upload the whole `standalone_colab` folder. Cell 2 detects existing `reel_metrics/` and skips bootstrap.

### Option C — Clone from GitHub

If the repo is on GitHub:

```python
!git clone https://github.com/YOUR_USER/Instagram_scraper.git
%cd Instagram_scraper/Multiple-reel-matrics/standalone_colab
```

### Option D — Upload files manually (legacy)

Upload these into the same Colab directory:

- `Instagram_Reel_Metrics.ipynb`
- `reel_metrics/` (entire folder with all `.py` files inside)

---

## Step 2 — Run the Notebook (Top to Bottom)

Open `Instagram_Reel_Metrics.ipynb` and run cells in order.

### Cell 1 — Install dependencies

```python
!pip install -q instagrapi==2.16.25 pandas matplotlib
```

Run this **once per Colab session**. Colab resets when the runtime disconnects.

### Cell 2 — Import the package

This cell finds `reel_metrics/` automatically whether you're in `standalone_colab/` or the repo root. If imports fail, make sure `reel_metrics/` is in your current working directory:

```python
import os
print(os.getcwd())
print(os.listdir())
# You should see reel_metrics/ in the list
```

### Cell 3–4 — Login

```python
IG_USERNAME = "your_instagram_username"
IG_PASSWORD = "your_password"   # only needed the first time per session

client = get_client(IG_USERNAME, IG_PASSWORD or None)
print(f"Authenticated as {IG_USERNAME}")
```

**Notes:**

- Use the Instagram account you log in with (not necessarily the profile you're scraping).
- Sessions are cached in `.ig_sessions/` in the Colab runtime. After the first successful login, you can often leave `IG_PASSWORD` empty for the rest of that session.
- Colab runtimes are temporary — when the session ends, you'll need to log in again.

**Security tip:** Don't share a notebook with your password saved in it. For a slightly safer approach in Colab:

```python
from getpass import getpass
IG_PASSWORD = getpass("Instagram password: ")
```

---

## Step 3 — Choose a Mode

### Mode 1 — Single Reel

Best for one reel with full metrics (views, likes, comments, shares, saves, reposts) plus comments.

```python
REEL_URL = "https://www.instagram.com/reel/ABC123xyz/"

reel = fetch_single_reel(client, REEL_URL, fetch_comments=True)
show_single_reel_metrics(reel)
show_comments_table(reel["reel_comments"])
```

**Accepted input formats:**

- Full URL: `https://www.instagram.com/reel/SHORTCODE/`
- Post URL: `https://www.instagram.com/p/SHORTCODE/`
- Bare shortcode: `ABC123xyz`

**Output:**

- Printed summary table (metrics + caption preview)
- Comments table (first 50 shown; full list is in `reel["reel_comments"]`)

---

### Mode 2 — Profile Reels

Fetches reels from a public profile.

```python
TARGET = "atiazuhair"   # or "@atiazuhair" or profile URL
LIMIT = 20              # use 0 to fetch ALL reels (slower)

profile_data = fetch_profile_reels(
    client,
    TARGET,
    limit=LIMIT,
    on_reel=lambda i, r: print(f"  reel {i + 1}: {r.get('shortcode')}"),
)

show_profile_summary(profile_data["profile"], profile_data["date_range"])
df_profile = show_reels_table(profile_data["reels"])
plot_reel_metrics(profile_data["reels"])
```

**Output:**

- Profile info (followers, following, post count)
- Date range of fetched reels
- Pandas table of all reels
- Bar chart comparing views / likes / comments

**Limit guide:**

| `LIMIT` | Behavior |
|---------|----------|
| `20` | First 20 reels (default, fast) |
| `0` | All reels (can take a long time for large accounts) |

---

### Mode 3 — Bulk CSV

Process many reel URLs at once.

**Step A — Prepare your CSV**

Any of these formats work:

```csv
url
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/reel/XYZ789/
```

Or one URL per row with no header:

```csv
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/reel/XYZ789/
```

Recognized column names: `url`, `link`, `reel_url`, `instagram_url`, etc.

**Step B — Upload and run**

```python
from google.colab import files

uploaded = files.upload()
csv_name = next(iter(uploaded))
urls = parse_urls_from_csv(uploaded[csv_name])
print(f"Found {len(urls)} URLs")
```

```python
bulk = bulk_fetch_reels(
    client,
    urls,
    fetch_comments=False,  # set True to fetch comments (much slower)
    on_progress=lambda c, t, row: print(
        f"[{c}/{t}] {row.get('status')}: {row.get('shortcode') or row.get('url')}"
    ),
)

show_bulk_summary(bulk["summary"])
df_bulk = show_reels_table(bulk["results"])
```

**Output:**

- Progress lines like `[3/10] Success: ABC123`
- Summary: total / successful / failed
- Full results table

---

## Step 4 — Export Results

After profile or bulk fetch, save and download:

```python
export_path = "results.csv"
df_profile.to_csv(export_path, index=False)  # or df_bulk

from google.colab import files
files.download(export_path)
```

---

## Quick Reference — Main Functions

| Function | Purpose |
|----------|---------|
| `get_client(username, password)` | Log in and return an authenticated client |
| `fetch_single_reel(client, url)` | One reel with full metrics |
| `fetch_profile_reels(client, target, limit)` | All reels from a profile |
| `bulk_fetch_reels(client, urls)` | Many URLs from a list |
| `parse_urls_from_csv(bytes)` | Extract URLs from uploaded CSV |
| `show_single_reel_metrics(data)` | Print single-reel summary |
| `show_reels_table(reels)` | Print pandas table |
| `show_comments_table(comments)` | Print comments table |
| `plot_reel_metrics(reels)` | Matplotlib bar chart |

---

## Common Errors and Fixes

| Error | What to do |
|-------|------------|
| `ModuleNotFoundError: reel_metrics` | Upload the `reel_metrics/` folder or `%cd` into `standalone_colab` |
| `No valid cached session... Provide a password` | Set `IG_PASSWORD` and re-run login |
| `Bad password` | Check username/password; try logging in on instagram.com first |
| `Two-factor authentication required` | Approve login in the Instagram app, then retry |
| `ChallengeRequired` | Open Instagram app/site, complete security check, retry |
| `Instagram rate-limited` | Wait 5–15 minutes; reduce `LIMIT` or bulk size |
| `Profile is private` | Log in with an account that follows that profile |
| `Reel not found` | Check URL; reel may be deleted or restricted |

---

## Tips for Colab

1. **Keep the runtime alive** — Long profile/bulk jobs stop if Colab disconnects. Use smaller batches or `LIMIT` first.
2. **Don't fetch comments in bulk** unless you need them — it's much slower (one extra API call per reel).
3. **Re-run install cell** after every new runtime session.
4. **Check working directory** — `!pwd` and `!ls` if imports fail.
5. **Same metrics as the web app** — This uses Instagram's mobile API (via `instagrapi`), same as your local Flask app.

---

## Minimal Copy-Paste Workflow

If you just want the fastest path:

```python
# 1. Install
!pip install -q instagrapi==2.16.25 pandas matplotlib

# 2. Setup path (after uploading standalone_colab)
%cd standalone_colab
from reel_metrics import get_client, fetch_single_reel, show_single_reel_metrics

# 3. Login
client = get_client("YOUR_IG_USERNAME", "YOUR_PASSWORD")

# 4. Fetch
reel = fetch_single_reel(client, "https://www.instagram.com/reel/YOUR_SHORTCODE/")
show_single_reel_metrics(reel)
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `Instagram_Reel_Metrics.ipynb` | Main Colab notebook |
| `COLAB_GUIDE.md` | This guide |
| `run.py` | Command-line version (local use) |
| `requirements.txt` | Python dependencies |
| `reel_metrics/` | Core Python package (scraping, display, API) |
