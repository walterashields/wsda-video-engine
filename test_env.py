#!/usr/bin/env python3
"""
WSDA Video Engine — Environment Check
Run this before rehearse.py or run.py.
Tells you exactly what's ready and what's missing.

Usage: python3 test_env.py
"""

import sys
import subprocess
import importlib
import urllib.request
import json
import time
from pathlib import Path

# ── Helpers ────────────────────────────────────────────────────

PASS = "✓"
FAIL = "✗"
WARN = "⚠"

results = []

def check(label, passed, detail="", fix=""):
    symbol = PASS if passed else FAIL
    results.append((passed, label, detail, fix))
    print(f"  {symbol}  {label}" + (f"  [{detail}]" if detail else ""))
    if not passed and fix:
        print(f"       → {fix}")


def section(title):
    print(f"\n── {title}")


# ── Checks ─────────────────────────────────────────────────────

print("\nWSDA Video Engine — Environment Check")
print("──────────────────────────────────────")

# Python version
section("Python")
major, minor = sys.version_info.major, sys.version_info.minor
check(
    f"Python {major}.{minor}",
    major == 3 and minor >= 11,
    sys.executable,
    "Install Python 3.11+: brew install python@3.11"
)

# Required packages
section("Python packages")
required = [
    ("playwright", "playwright"),
    ("pydantic", "pydantic"),
    ("yaml", "pyyaml"),
    ("flask", "flask"),
    ("rich", "rich"),
    ("click", "click"),
]
for import_name, pip_name in required:
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "ok")
        check(pip_name, True, version)
    except ImportError:
        check(pip_name, False, fix=f"pip3 install {pip_name}")

# Playwright browser
section("Playwright browser")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        version = browser.version
        browser.close()
    check("Chromium", True, version)
except Exception as e:
    check("Chromium", False, fix="playwright install chromium")

# FFmpeg
section("FFmpeg")
try:
    result = subprocess.run(
        ["ffmpeg", "-version"],
        capture_output=True, text=True, timeout=5
    )
    version_line = result.stdout.splitlines()[0] if result.stdout else "found"
    check("ffmpeg", True, version_line[:40])
except FileNotFoundError:
    check("ffmpeg", False, fix="brew install ffmpeg")

# macOS screen recording permission
section("macOS permissions")
print(f"  {WARN}  Screen recording permission")
print(f"       → Must be granted manually in:")
print(f"         System Settings → Privacy & Security → Screen Recording")
print(f"         Add Terminal (or iTerm) to the list")
print(f"       → Only needed for run.py (not rehearse.py)")

# Project files
section("Project files")
files_to_check = [
    ("courses/novabridge/video_1_1/production_card.yml", "Production card"),
    ("courses/novabridge/video_1_1/assets/novabridge.db", "NovaBridge database"),
    ("courses/novabridge/video_1_1/assets/ambiguity_demo_queries.sql", "SQL queries"),
    ("web/app.py", "Flask viewer"),
    ("web/templates/viewer.html", "Viewer template"),
    ("engine/compiler.py", "Timeline compiler"),
    ("engine/timeline_runner.py", "Playback engine"),
    ("adapters/sql_viewer_adapter.py", "SQL adapter"),
    ("config/settings.yml", "Settings"),
]
for path, label in files_to_check:
    exists = Path(path).exists()
    check(label, exists, path if exists else "", fix=f"Missing: {path}")

# Flask API test
section("Flask SQL viewer")
web_app = Path("web/app.py")
if web_app.exists():
    proc = subprocess.Popen(
        [sys.executable, str(web_app)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    try:
        r = urllib.request.urlopen("http://127.0.0.1:5050/api/health", timeout=3)
        data = json.loads(r.read())
        check("Flask starts and responds", data.get("status") == "ok")
    except Exception as e:
        check("Flask starts and responds", False, fix=f"Error: {e}")
    finally:
        proc.terminate()
else:
    check("Flask viewer", False, fix="web/app.py missing")

# Database smoke test
section("Database")
db_path = Path("courses/novabridge/video_1_1/assets/novabridge.db")
if db_path.exists():
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        expected = {"orders", "order_details", "order_summary"}
        has_all = expected.issubset(set(tables))
        check("Tables present", has_all, ", ".join(sorted(tables)),
              fix="Run: python3 create_db.py")
    except Exception as e:
        check("Database readable", False, fix=str(e))
else:
    check("Database exists", False, fix="Run: python3 create_db.py")

# ── Summary ────────────────────────────────────────────────────

total = len(results)
passed = sum(1 for r in results if r[0])
failed = total - passed

print(f"\n──────────────────────────────────────")
print(f"  {passed}/{total} checks passed")

if failed == 0:
    print(f"\n  {PASS}  All good. You're ready to run:")
    print(f"\n     Rehearse (no recording):")
    print(f"     python3 rehearse.py courses/novabridge/video_1_1/production_card.yml")
    print(f"\n     Record:")
    print(f"     python3 run.py courses/novabridge/video_1_1/production_card.yml")
else:
    print(f"\n  {FAIL}  Fix the items above, then re-run: python3 test_env.py")

print()
