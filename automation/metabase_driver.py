#!/usr/bin/env python3
"""
Metabase automation driver.

Phase 2 proof of concept: drives a real Metabase instance (not the custom
sql_viewer.html the main renderer/timeline_runner pipeline controls) through
Playwright, recording the session and writing an audit log shaped to match
engine/schemas.py's AuditLog, so narration/audit_narrator.py can mix in
ElevenLabs narration afterward without modification.

Architecture note: this is intentionally a separate, standalone driver, not
an extension of engine/timeline_runner.py. That runner drives a
self-authored, pixel-controlled SQL viewer; Metabase is a real third-party
web app with its own DOM that can change on any upstream release. Selectors
below were captured live against Metabase v0.63.13 (2026-08-14) and favor
stable anchors (data-testid, exact visible text) over structural CSS,
but a Metabase UI update could still break them, unlike the custom
viewer.html the rest of this repo controls.

Lesson scripts are YAML (see courses/metabase_poc/*.yml for the format):
  lesson_id: string
  target: {base_url, admin_email, admin_password, admin_first_name,
            admin_last_name, site_name}
  events: [{id, type, ...type-specific fields, narration?}]

Event types implemented: setup_or_login, click_new_question,
select_database, select_table, add_filter, visualize, highlight_section,
show_result, save_question, add_to_dashboard, pause.

Narration convention (matches AGENTS.md's "Common Pitfalls" for the main
pipeline): only highlight_section and show_result events carry narration
text; every other event is a silent action. Show first, then explain.

Usage:
    python3 automation/metabase_driver.py courses/metabase_poc/video_1_1/lesson_script.yml
"""

import argparse
import asyncio
import glob
import json
import subprocess
import time
from pathlib import Path

import requests
import yaml
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "output"
VIEWPORT = {"width": 1920, "height": 1080}
HIGHLIGHT_STYLE = "outline: 4px solid #fbbf24; outline-offset: 2px; transition: outline 0.15s;"


class Clock:
    """Real wall-clock elapsed time, not a simulated/virtual clock, since
    Metabase's real network and render latency is itself worth capturing
    accurately rather than assuming a fixed synthetic duration per event."""

    def __init__(self):
        self._start = time.monotonic()

    def now_ms(self):
        return int((time.monotonic() - self._start) * 1000)


async def _highlight(page, text, seconds):
    try:
        locator = page.get_by_text(text, exact=True).first
        await locator.evaluate(f"el => {{ el.style.cssText += '{HIGHLIGHT_STYLE}'; }}")
        await page.wait_for_timeout(int(seconds * 1000))
        await locator.evaluate("el => { el.style.outline = ''; el.style.outlineOffset = ''; el.style.transition = ''; }")
    except Exception as exc:
        print(f"[metabase_driver] highlight skipped ({text!r}): {exc}")
        await page.wait_for_timeout(int(seconds * 1000))


async def _ensure_account(page, target):
    base_url = target["base_url"]
    response = requests.get(f"{base_url}/api/session/properties", timeout=10)
    response.raise_for_status()
    already_set_up = response.json().get("has-user-setup", False)

    if not already_set_up:
        await page.goto(f"{base_url}/setup")
        await page.wait_for_load_state("networkidle")
        await page.get_by_role("button", name="Let's get started").click()
        await page.wait_for_timeout(500)
        await page.locator("input[name=first_name]").fill(target["admin_first_name"])
        await page.locator("input[name=last_name]").fill(target["admin_last_name"])
        await page.locator("input[name=email]").fill(target["admin_email"])
        await page.locator("input[name=site_name]").fill(target.get("site_name", "WSDA Metabase Demo"))
        await page.locator("input[name=password]").fill(target["admin_password"])
        await page.locator("input[name=password_confirm]").fill(target["admin_password"])
        await page.get_by_role("button", name="Next").click()
        await page.wait_for_timeout(1200)
        # Metabase creates the account here (subsequent /setup visits
        # redirect to /auth/login), but this click does NOT establish a
        # logged-in session in the browser, confirmed live: reloading
        # /setup right after this step lands on the login page, not the
        # app. The remaining wizard steps (usage reason, "add your data")
        # aren't needed either, the bundled Sample Database is already
        # there. Whether this also establishes a logged-in session turned
        # out to be inconsistent run-to-run against an identical fresh
        # container (confirmed live: one run needed the explicit login
        # below, the next was already authenticated and got redirected
        # straight past /auth/login to the app). The count() check below
        # avoids a long timeout waiting on a login form that may not
        # actually be there.

    await page.goto(f"{base_url}/auth/login")
    await page.wait_for_load_state("networkidle")
    username_input = page.locator("input[name=username]")
    if await username_input.count() > 0:
        await username_input.fill(target["admin_email"])
        await page.locator("input[name=password]").fill(target["admin_password"])
        await page.get_by_role("button", name="Sign in").click()
        await page.wait_for_timeout(1200)


# --- event actions ------------------------------------------------------

async def action_setup_or_login(page, event, target):
    await _ensure_account(page, target)


async def action_click_new_question(page, event, target):
    await page.get_by_test_id("app-bar").get_by_role("button", name="New").click()
    await page.wait_for_timeout(400)
    await page.get_by_text("Question", exact=True).click()
    await page.wait_for_timeout(800)


async def action_select_database(page, event, target):
    await page.get_by_text(event["database"], exact=True).click()
    await page.wait_for_timeout(400)


async def action_select_table(page, event, target):
    await page.get_by_text(event["table"], exact=True).click()
    await page.wait_for_timeout(800)


async def action_add_filter(page, event, target):
    await page.get_by_text("Add filters to narrow your answer", exact=True).click()
    await page.wait_for_timeout(400)
    await page.get_by_text(event["field"], exact=True).click()
    await page.wait_for_timeout(400)
    if "min" in event:
        await page.get_by_placeholder("Min").fill(str(event["min"]))
    if "max" in event:
        await page.get_by_placeholder("Max").fill(str(event["max"]))
    await page.get_by_role("button", name="Add filter").click()
    await page.wait_for_timeout(400)


async def action_visualize(page, event, target):
    await page.get_by_role("button", name="Visualize").click()
    await page.wait_for_timeout(1200)


async def action_highlight_section(page, event, target):
    # the sibling pause event carries the full narration-length wait; this
    # is just how long the visible highlight glow stays on screen
    await _highlight(page, event["selector_text"], seconds=2.5)


async def action_show_result(page, event, target):
    await page.wait_for_timeout(500)


async def action_save_question(page, event, target):
    await page.get_by_test_id("qb-save-button").click()
    await page.wait_for_timeout(500)
    await page.get_by_label("Name").fill(event["question_name"])
    save_button = page.get_by_test_id("save-question-button")
    await save_button.click()
    # wait for the actual save round-trip to finish (dialog closes) rather
    # than a fixed sleep: a fixed 1200ms sometimes wasn't enough margin for
    # the "Saved" toast add_to_dashboard depends on to reliably appear,
    # confirmed live (intermittent failures on the very next event).
    await save_button.wait_for(state="detached", timeout=15000)
    await page.wait_for_timeout(500)


async def action_add_to_dashboard(page, event, target):
    await page.get_by_text("Add this to a dashboard", exact=True).click()
    await page.wait_for_timeout(500)
    await page.get_by_text("New dashboard", exact=True).click()
    await page.wait_for_timeout(500)
    await page.get_by_placeholder("My new dashboard").fill(event["dashboard_name"])
    await page.get_by_role("button", name="Create", exact=True).click()
    await page.wait_for_timeout(1200)
    await page.get_by_role("button", name="Select", exact=True).click()
    await page.wait_for_timeout(1200)
    await page.get_by_role("button", name="Save", exact=True).click()
    await page.wait_for_timeout(1200)


async def action_pause(page, event, target):
    await page.wait_for_timeout(int(event["duration"] * 1000))


ACTIONS = {
    "setup_or_login": action_setup_or_login,
    "click_new_question": action_click_new_question,
    "select_database": action_select_database,
    "select_table": action_select_table,
    "add_filter": action_add_filter,
    "visualize": action_visualize,
    "highlight_section": action_highlight_section,
    "show_result": action_show_result,
    "save_question": action_save_question,
    "add_to_dashboard": action_add_to_dashboard,
    "pause": action_pause,
}


# --- recording orchestration --------------------------------------------

def _transcode(raw_webm, out_mp4):
    """Matches engine/timeline_runner.py's convert_video(): raw Playwright
    webm -> H.264/yuv420p mp4, faststart. audit_narrator.py ffprobes this
    file's duration directly, so it must already be a finished mp4."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw_webm),
            "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out_mp4),
        ],
        check=True, capture_output=True,
    )


async def run_lesson(card_path, output_dir):
    card = yaml.safe_load(Path(card_path).read_text())
    lesson_id = card["lesson_id"]
    target = card["target"]
    events = card["events"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir / f"{lesson_id}_raw"
    video_dir.mkdir(parents=True, exist_ok=True)

    clock = Clock()
    audit_events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(video_dir),
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()

        for event in events:
            event_id = event["id"]
            event_type = event["type"]
            action = ACTIONS.get(event_type)

            started_at_ms = clock.now_ms()
            success, error = True, None
            try:
                if action is None:
                    raise ValueError(f"unknown event type {event_type!r}")
                await action(page, event, target)
            except Exception as exc:
                success = False
                error = str(exc)
                print(f"[metabase_driver] event {event_id} ({event_type}) failed: {exc}")
            completed_at_ms = clock.now_ms()

            audit_events.append({
                "event_id": event_id,
                "event_type": event_type,
                "started_at_ms": started_at_ms,
                "completed_at_ms": completed_at_ms,
                "success": success,
                "error": error,
            })

        await context.close()
        await browser.close()

    raw_files = glob.glob(str(video_dir / "*.webm"))
    if not raw_files:
        raise RuntimeError(f"no recorded video found in {video_dir}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    mp4_path = output_dir / f"{lesson_id}_{timestamp}.mp4"
    _transcode(raw_files[0], mp4_path)

    audit_log = {
        "lesson_id": lesson_id,
        "events": audit_events,
        "mp4_path": str(mp4_path),
        "total_events": len(audit_events),
        "successful_events": sum(1 for e in audit_events if e["success"]),
    }
    audit_path = output_dir / f"{lesson_id}_{timestamp}_audit.json"
    audit_path.write_text(json.dumps(audit_log, indent=2))

    print(f"[metabase_driver] recorded {mp4_path}")
    print(f"[metabase_driver] audit log {audit_path}")
    print(f"[metabase_driver] {audit_log['successful_events']}/{audit_log['total_events']} events succeeded")

    return mp4_path, audit_path


def main():
    parser = argparse.ArgumentParser(description="Drive a Metabase lesson script and record it.")
    parser.add_argument("card_path", help="Path to a Metabase lesson YAML script")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    asyncio.run(run_lesson(args.card_path, args.output_dir))


if __name__ == "__main__":
    main()
