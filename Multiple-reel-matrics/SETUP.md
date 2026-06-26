# Windows Setup

**Requires:** Windows 10/11, Python 3.12+ (`python --version`), project folder `Multiple-reel-matrics`.

---

## First-time setup

1. Open **Command Prompt** in `Multiple-reel-matrics`  
   (File Explorer → open folder → address bar → type `cmd` → Enter)

2. Run these commands:

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python test.py
```

3. Open in browser: **http://127.0.0.1:5000**

4. Enter Instagram **username** and **password** (first time only).  
   Next runs: password can be left blank.

Keep the Command Prompt window open while using the app. Stop with **Ctrl + C**.

---

## Every next time

```cmd
cd C:\path\to\Multiple-reel-matrics
.venv\Scripts\activate
python test.py
```

Then open **http://127.0.0.1:5000**

---

## Common fixes

| Problem | Fix |
|---------|-----|
| `python` not found | Use `py` instead, or install Python with **Add to PATH** |
| `pip` not found | `python -m pip install -r requirements.txt` |
| Port 5000 in use | Close other `python test.py` windows, try again |
| Page won’t load | Server must show `Running on http://127.0.0.1:5000` |
| Login failed | Re-enter password; confirm login in Instagram app if challenged |

**PowerShell:** use `.venv\Scripts\Activate.ps1` or switch to Command Prompt.

---

For how the app works, see [README.md](README.md).
