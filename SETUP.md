# Developer Setup Guide

Welcome! This guide helps you run the **Instagram Reel Metrics** project on your own machine after cloning the repo.

The app is a small local web tool. You log in with an Instagram account, paste reel links or profile names, and it fetches likes, comments, views, shares, saves, and reposts.

---

## What you need before starting

| Requirement | Minimum version | How to check |
|---|---|---|
| **Python** | 3.10 or newer (3.12 recommended) | `python --version` (Windows) or `python3 --version` (Linux / macOS) |
| **pip** | Comes with Python | `pip --version` |
| **Git** | Any recent version | `git --version` |
| **An Instagram account** | — | You need real login credentials the first time |

**On Windows?** Jump straight to the [Windows setup guide](#windows-setup-guide-step-by-step) below.

You also need a terminal:
- **Windows** — PowerShell (recommended), Command Prompt, or Git Bash
- **Linux / macOS** — any terminal app

---

## What is in Git vs what you create locally

Because of `.gitignore`, some important files are **not** pushed to Git. You must create them yourself after cloning.

| Item | In Git? | What you do |
|---|---|---|
| `test.py` | Yes | Backend code — already in the repo |
| `index.html` | Yes | Frontend UI — already in the repo |
| `requirements.txt` | Yes | Lists Python packages to install |
| `.venv/` | **No** | Create with `python3 -m venv .venv` |
| `.ig_sessions/` | **No** | Created automatically on first login |
| `__pycache__/` | **No** | Created automatically when Python runs |
| `*.xlsx`, `*.csv` exports | **No** | Created when you export data from the app |
| `.env` / secrets | **No** | Not required — login is done in the browser UI |

**Bottom line:** After `git clone`, you only get the source code. You still need to install Python packages and start the server yourself. That is normal and expected.

---

## Project folder layout

```
Instagram_scraper/
├── .gitignore              # Tells Git what NOT to upload
├── SETUP.md                # This file — read me first
└── Multiple-reel-matrics/
    ├── requirements.txt    # Python dependencies
    ├── test.py             # Flask backend (the "engine")
    ├── index.html          # Web UI (the "dashboard")
    ├── README.md           # Deep technical explanation of how the app works
    ├── .venv/              # ← you create this (not in Git)
    └── .ig_sessions/       # ← created on first login (not in Git)
```

---

## Windows setup guide (step-by-step)

This section is written for **Windows 10 / Windows 11**. Follow it from top to bottom if you are setting up on a PC.

### A. Install Python (one-time)

1. Download Python from [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Run the installer.
3. **Important:** On the first screen, check **"Add python.exe to PATH"** at the bottom, then click **Install Now**.
4. Close and reopen your terminal after installation.

Verify Python works:

```powershell
python --version
pip --version
```

You should see something like `Python 3.12.x`. If you get `'python' is not recognized`, Python was not added to PATH — reinstall and tick the checkbox, or use the Microsoft Store Python package.

### B. Install Git (one-time)

1. Download Git from [https://git-scm.com/download/win](https://git-scm.com/download/win)
2. Run the installer (default options are fine).
3. Verify:

```powershell
git --version
```

### C. Open a terminal

Press **Win + X** and choose **Terminal** or **PowerShell** (recommended).

You can also use **Command Prompt** or **Git Bash** — commands are slightly different for activation (see step E).

### D. Clone the project

Replace `<your-repo-url>` with the actual Git link:

```powershell
cd $HOME\Desktop
git clone <your-repo-url>
cd Instagram_scraper\Multiple-reel-matrics
```

If you cloned to a different folder, `cd` into that path instead. Example:

```powershell
cd C:\Users\YourName\Projects\Instagram_scraper\Multiple-reel-matrics
```

### E. Create and activate a virtual environment

A virtual environment keeps this project's packages separate from other Python projects on your PC.

**PowerShell (recommended):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Command Prompt (cmd.exe):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Git Bash:**

```bash
python -m venv .venv
source .venv/Scripts/activate
```

When activation works, your prompt shows `(.venv)` at the beginning.

#### Fix: "running scripts is disabled on this system" (PowerShell only)

If `.venv\Scripts\Activate.ps1` fails with an execution policy error, run this **once** in PowerShell (as your normal user):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again:

```powershell
.venv\Scripts\Activate.ps1
```

### F. Install dependencies

With `(.venv)` active in your terminal:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Wait until installation finishes without errors.

| Package | Purpose |
|---|---|
| **flask** | Runs the local web server and API routes |
| **instagrapi** | Talks to Instagram's mobile API to fetch reel metrics |

`pip` will also install helper libraries (requests, pydantic, Pillow, etc.) automatically.

### G. Start the server

```powershell
python test.py
```

You should see:

```
Open http://127.0.0.1:5000 in your browser.
```

**Keep this terminal window open** while you use the app. Closing it stops the server.

### H. Open the app in your browser

Open **Chrome**, **Edge**, or **Firefox** and go to:

**http://127.0.0.1:5000**

The app runs only on your computer. Nothing is uploaded to a public server.

### I. Log in and fetch data

1. Enter your **Instagram username** and **password**.
2. Pick a tab:
   - **Single Reel** — paste one reel URL or shortcode.
   - **Profile Reels** — enter a profile username.
3. Click **Fetch**.

On first login, a `.ig_sessions` folder is created next to `test.py`. Later runs may work without re-entering your password if the session is still valid.

### J. Stop the server

In the terminal where `python test.py` is running, press **Ctrl + C**.

---

## Linux / macOS setup (step-by-step)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Instagram_scraper/Multiple-reel-matrics
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When active, your terminal prompt usually shows `(.venv)` at the start.

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Start the server

```bash
python test.py
```

### 5. Open the app

Go to **http://127.0.0.1:5000** in your browser.

### 6. Log in and fetch data

Same as the Windows guide (step I above).

---

## Running the server again (after the first setup)

**Windows (PowerShell):**

```powershell
cd C:\path\to\Instagram_scraper\Multiple-reel-matrics
.venv\Scripts\Activate.ps1
python test.py
```

**Windows (Command Prompt):**

```cmd
cd C:\path\to\Instagram_scraper\Multiple-reel-matrics
.venv\Scripts\activate.bat
python test.py
```

**Linux / macOS:**

```bash
cd Instagram_scraper/Multiple-reel-matrics
source .venv/bin/activate
python test.py
```

Then open **http://127.0.0.1:5000** in your browser.

To stop the server, press **Ctrl + C** in the terminal.

---

## Quick reference — common commands

**Windows (PowerShell):**

```powershell
cd Multiple-reel-matrics
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python test.py
# Stop: Ctrl + C
```

**Linux / macOS:**

```bash
cd Multiple-reel-matrics
source .venv/bin/activate
pip install -r requirements.txt
python test.py
# Stop: Ctrl + C
```

---

## API endpoints (for developers)

The backend exposes these routes (all called by `index.html`):

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Serves the web UI |
| `/api/fetch` | POST | Fetch metrics for one reel |
| `/api/bulk_fetch` | POST | Fetch metrics from a CSV upload |
| `/api/bulk_fetch_stream` | POST | Same as bulk, with live progress (SSE) |
| `/api/profile_reels` | POST | List reels for a profile |
| `/api/debug_node` | POST | Raw Instagram API fields (debugging) |

The server listens on **127.0.0.1:5000** by default (see the bottom of `test.py` to change host/port).

---

## Troubleshooting

### Windows: `'python' is not recognized`

Python is not installed or not on your PATH.

1. Reinstall Python from [python.org](https://www.python.org/downloads/) and check **"Add python.exe to PATH"**.
2. Close **all** terminal windows and open a new one.
3. Try `python --version` again.

If it still fails, try `py --version` and use `py` instead of `python` in all commands (e.g. `py -m venv .venv`).

### Windows: PowerShell won't activate `.venv`

Error: *running scripts is disabled on this system*

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

Or use **Command Prompt** instead and run `.venv\Scripts\activate.bat`.

### Windows: `ModuleNotFoundError: No module named 'flask'`

The virtual environment is not active, or packages were not installed:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Make sure you see `(.venv)` in your prompt before running `python test.py`.

### Windows: Recreate a broken virtual environment

```powershell
deactivate
Remove-Item -Recurse -Force .venv
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Command Prompt alternative:**

```cmd
rmdir /s /q .venv
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

### Linux / macOS: `Permission denied` when running `.venv/bin/python`

The virtual environment was not created correctly. Delete it and recreate:

```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Linux / macOS: `ModuleNotFoundError: No module named 'flask'` (or `instagrapi`)

The virtual environment is not active, or packages were not installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### `No valid cached session... Provide a password`

Your saved session expired. Enter your Instagram password again in the UI.

### `ChallengeRequired`

Instagram wants extra verification. Open the official Instagram app or website, confirm it is you, then retry.

### `PleaseWaitFewMinutes`

You hit Instagram's rate limit. Wait 5–10 minutes and try again with fewer requests.

### Port 5000 already in use

Another program is using port 5000. Either stop that program, or edit the last lines of `test.py` to use a different port (e.g. `5001`).

### Browser shows "connection refused"

Make sure `python test.py` is still running in the terminal and you are visiting the correct URL: `http://127.0.0.1:5000`.

---

## Security reminders

- **Never commit** `.ig_sessions/` — it contains login cookies.
- **Never commit** `.venv/` — it is large and machine-specific.
- **Never commit** passwords or `.env` files with secrets.
- This tool is for **local use**. Do not expose port 5000 to the public internet without proper security.

---

## Want more technical detail?

Read `Multiple-reel-matrics/README.md` for a full explanation of:

- Why we use `instagrapi` instead of `instaloader`
- How Instagram's web API vs mobile API differ
- How sessions, scraping, and each API route work

---

## Checklist for a new developer

**All platforms:**

- [ ] Python 3.10+ installed
- [ ] Git installed
- [ ] Repo cloned
- [ ] `cd Multiple-reel-matrics`
- [ ] Virtual environment created (`.venv/`)
- [ ] Virtual environment activated — prompt shows `(.venv)`
- [ ] `pip install -r requirements.txt` completed
- [ ] `python test.py` running
- [ ] Browser open at http://127.0.0.1:5000
- [ ] Instagram login works

**Windows only (extra checks):**

- [ ] Python installer had **"Add python.exe to PATH"** checked
- [ ] `python --version` works in a **new** PowerShell window
- [ ] PowerShell execution policy allows `.venv\Scripts\Activate.ps1` (or using cmd + `activate.bat`)

Once all boxes are checked, you are ready to develop or use the app.
