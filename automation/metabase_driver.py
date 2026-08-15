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

Event types implemented: highlight_target, click_new_question,
select_database, select_table, add_filter, visualize, highlight_section,
clear_highlight, show_result, save_question, add_to_dashboard, narrate,
pause. `narrate` is a pure no-op (no click, no highlight) for narration
beats with nothing to anchor to on screen -- currently just the
lesson-opening scenario/outcome statement required by
LESSON_CONTENT_STANDARD.md, which has to play before the first action
fires.
Login/account setup is handled separately, before recording starts (see
run_lesson): it's pure demo-environment provisioning, not a teaching
moment, and a first cut of this lesson showed 20+ seconds of dead
login-screen time before anything instructional happened. Login now runs
in an unrecorded browser context; its authenticated session
(storage_state) is carried over into the recorded context, so the video
opens already logged in.

Narration convention (updated 2026-08-14, matches AGENTS.md): two tiers.
Short "here's what I'm doing" lines (a sentence or less) on most action
events, longer "why this matters" narration on highlight_section/
show_result, each sized with its own pause buffer so narration never
leaves dead air after it finishes.

Highlight-then-act sequencing (added 2026-08-14, second fix pass): a
notable click-driven step is no longer one event that narrates and acts
at once. It's two: a `highlight_target` event that locates the real
element via Playwright's bounding_box(), draws a pixel-accurate overlay
around it, and carries the narration; then a plain commit event
(click_new_question / select_table / add_filter / save_question /
add_to_dashboard, unchanged internally) that performs the actual
click(s) once the highlight's narrated pause has played out, and clears
the highlight itself right after. This exists because
narration/audit_narrator.py schedules a narrated event's audio to start
at the beginning of the PAUSE that follows it, never before, so the only
way to get "highlight shows, narration plays, then the click fires" (not
highlight-and-click-then-narrate, which is what a single combined event
would produce) is to split the two into separate events with the pause
in between. highlight_section (the longer "why this matters" narration,
already showing something rather than driving a click) uses the same
overlay mechanism but leaves it up through its own full narrated pause,
cleared by a following clear_highlight event instead of a commit action.

Usage:
    python3 automation/metabase_driver.py courses/metabase_poc/video_1_1/lesson_script.yml
"""

import argparse
import asyncio
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
HIGHLIGHT_COLOR = "#06c015"  # WSDA brand green
HIGHLIGHT_OVERLAY_ID = "__wsda_highlight__"
# how long the highlight sits alone on screen before its narrated pause
# starts, so the eye finds it before anything else happens. Raised from
# 700ms (2026-08-14, fix pass 3): a first-time-learner pacing pass found
# 700ms was not enough time to visually locate the highlighted element
# before narration started talking about it. This is the delay before the
# PAUSE begins, and the commit action's click doesn't fire until that
# pause (which carries the narration) completes, so this constant pushes
# back the actual click, not just the highlight's own onscreen time --
# confirmed against real audit.json timestamps after changing it, not
# just trusted as configured (see courses/metabase_poc/video_1_1's
# lesson_script.yml changelog for the verification numbers).
HIGHLIGHT_LEAD_MS = 1500
# how long the highlight stays up after a commit action's click(s), so the
# result of the click is visible before the highlight disappears
POST_ACTION_HOLD_MS = 700


class Clock:
    """Real wall-clock elapsed time, not a simulated/virtual clock, since
    Metabase's real network and render latency is itself worth capturing
    accurately rather than assuming a fixed synthetic duration per event."""

    def __init__(self):
        self._start = time.monotonic()

    def now_ms(self):
        return int((time.monotonic() - self._start) * 1000)


def _resolve_locator(page, spec):
    """Builds a Playwright locator from a YAML locator spec:
      {"kind": "app_bar_button", "name": "New"}
      {"kind": "text", "value": "Orders"}
      {"kind": "test_id", "value": "qb-save-button"}
    Kept as a small, explicit dispatch rather than a generic selector
    string so lesson scripts stay readable and each kind can pick the
    most stable anchor available (data-testid, role, or exact text)."""
    kind = spec["kind"]
    if kind == "app_bar_button":
        return page.get_by_test_id("app-bar").get_by_role("button", name=spec["name"])
    if kind == "text":
        return page.get_by_text(spec["value"], exact=True).first
    if kind == "test_id":
        return page.get_by_test_id(spec["value"])
    raise ValueError(f"unknown locator kind {kind!r}")


async def _draw_highlight_box(page, locator):
    """Injects a positioned overlay div sized to the element's real
    bounding_box(), rather than outlining the element in place: an
    outline can be clipped by a parent's overflow:hidden, and an overlay
    guarantees visibility and z-index regardless of the target's own
    stacking context. Pixel-accurate to what's actually being clicked,
    not an approximate or hardcoded region."""
    box = await locator.bounding_box()
    if box is None:
        print("[metabase_driver] highlight target not visible, skipping overlay")
        return None
    await page.evaluate(
        """({box, color, id}) => {
            const existing = document.getElementById(id);
            if (existing) existing.remove();
            const el = document.createElement('div');
            el.id = id;
            el.style.position = 'fixed';
            el.style.left = box.x + 'px';
            el.style.top = box.y + 'px';
            el.style.width = box.width + 'px';
            el.style.height = box.height + 'px';
            el.style.border = '3px solid ' + color;
            el.style.borderRadius = '4px';
            el.style.boxShadow = '0 0 0 9999px rgba(0,0,0,0.15)';
            el.style.zIndex = '2147483647';
            el.style.pointerEvents = 'none';
            document.body.appendChild(el);
        }""",
        {"box": box, "color": HIGHLIGHT_COLOR, "id": HIGHLIGHT_OVERLAY_ID},
    )
    return box


async def _clear_highlight(page):
    try:
        await page.evaluate(
            """(id) => { const el = document.getElementById(id); if (el) el.remove(); }""",
            HIGHLIGHT_OVERLAY_ID,
        )
    except Exception as exc:
        # page may have navigated between draw and clear; nothing to clean up
        print(f"[metabase_driver] highlight clear skipped: {exc}")


async def _wait_for_setup_complete(base_url, timeout_ms=20000, poll_interval_ms=500):
    """Polls the real API for has-user-setup instead of guessing a fixed
    delay after clicking Next. A fixed ~1.2s wait was not reliably enough
    for a truly fresh container's first account-creation write, confirmed
    live: the unrecorded setup context captured storage_state before the
    account had actually finished being created server-side, and the
    stale in-progress setup-wizard state (including localStorage form
    progress) rode along into the recorded context, so the recording
    opened on a half-submitted setup form instead of the logged-in app."""
    elapsed_ms = 0
    while elapsed_ms < timeout_ms:
        response = requests.get(f"{base_url}/api/session/properties", timeout=10)
        response.raise_for_status()
        if response.json().get("has-user-setup", False):
            return
        await asyncio.sleep(poll_interval_ms / 1000)
        elapsed_ms += poll_interval_ms
    raise RuntimeError(f"Metabase setup did not report complete within {timeout_ms}ms")


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
        await _wait_for_setup_complete(base_url)
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

    # Confirm we're actually on a stable, authenticated page before this
    # context's storage_state gets captured and handed to the recorded
    # context, rather than assuming the fixed wait above was enough.
    await page.get_by_test_id("app-bar").wait_for(state="visible", timeout=15000)
    await page.wait_for_load_state("networkidle")


# --- event actions ------------------------------------------------------
# (account setup/login is not an event; see run_lesson's unrecorded phase)

async def action_highlight_target(page, event, target):
    """Locates the real element (no click), draws a pixel-accurate overlay
    around it, and holds briefly before returning. Does NOT remove the
    overlay, it stays up through this event's narrated pause, cleared by
    the commit event that follows (see module docstring)."""
    locator = _resolve_locator(page, event["locator"])
    await _draw_highlight_box(page, locator)
    await page.wait_for_timeout(HIGHLIGHT_LEAD_MS)


async def action_clear_highlight(page, event, target):
    await _clear_highlight(page)


async def action_click_new_question(page, event, target):
    await page.get_by_test_id("app-bar").get_by_role("button", name="New").click()
    await page.wait_for_timeout(400)
    await page.get_by_text("Question", exact=True).click()
    await page.wait_for_timeout(800)
    await page.wait_for_timeout(POST_ACTION_HOLD_MS)
    await _clear_highlight(page)


async def action_select_database(page, event, target):
    await page.get_by_text(event["database"], exact=True).click()
    await page.wait_for_timeout(400)


async def action_select_table(page, event, target):
    await page.get_by_text(event["table"], exact=True).click()
    await page.wait_for_timeout(800)
    await page.wait_for_timeout(POST_ACTION_HOLD_MS)
    await _clear_highlight(page)


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
    await page.wait_for_timeout(POST_ACTION_HOLD_MS)
    await _clear_highlight(page)


async def action_visualize(page, event, target):
    await page.get_by_role("button", name="Visualize").click()
    await page.wait_for_timeout(1200)


async def action_highlight_section(page, event, target):
    """Same overlay mechanism as highlight_target, but for a "why this
    matters" narration over something already visible, no click involved.
    Leaves the overlay up through this event's own narrated pause; a
    following clear_highlight event removes it (no commit action to
    piggyback the removal onto, unlike the click-driven events)."""
    locator = page.get_by_text(event["selector_text"], exact=True).first
    await _draw_highlight_box(page, locator)
    await page.wait_for_timeout(HIGHLIGHT_LEAD_MS)


async def action_show_result(page, event, target):
    await page.wait_for_timeout(500)


async def action_save_question(page, event, target):
    await page.get_by_test_id("qb-save-button").click()
    await page.wait_for_timeout(500)
    await page.get_by_label("Name").fill(event["question_name"])
    save_button = page.get_by_test_id("save-question-button")
    await save_button.click()
    # wait for the actual save round-trip to finish (dialog closes) rather
    # than a fixed sleep, confirmed live this matters for reliability.
    await save_button.wait_for(state="detached", timeout=15000)

    # Click the post-save "Add this to a dashboard" toast immediately, with
    # no pause in between: it auto-dismisses on its own timer, and a first
    # re-cut of this lesson put a narrated pause (needed for the "let's
    # save this" line) between save completing and this click, so the
    # toast was reliably gone by the time add_to_dashboard's own action ran.
    # Clicking it here, inside the same action and before any pause, means
    # the picker dialog it opens is a stable modal (not time-limited) by
    # the time the pause/narration for this event plays.
    await page.get_by_text("Add this to a dashboard", exact=True).click()
    await page.wait_for_timeout(500)

    # only now, after the toast click and its own settle wait, hold and
    # clear the Save-button highlight drawn by the preceding
    # highlight_target event, this does not touch the toast-click timing
    # above (still zero delay between save-dialog-close and the toast).
    await page.wait_for_timeout(POST_ACTION_HOLD_MS)
    await _clear_highlight(page)


async def action_add_to_dashboard(page, event, target):
    # picks up from the dashboard picker dialog opened at the end of
    # action_save_question (see the comment there for why)
    await page.get_by_text("New dashboard", exact=True).click()
    await page.wait_for_timeout(500)
    await page.get_by_placeholder("My new dashboard").fill(event["dashboard_name"])
    await page.get_by_role("button", name="Create", exact=True).click()
    await page.wait_for_timeout(1200)
    await page.get_by_role("button", name="Select", exact=True).click()
    await page.wait_for_timeout(1200)
    await page.get_by_role("button", name="Save", exact=True).click()
    await page.wait_for_timeout(1200)
    await page.wait_for_timeout(POST_ACTION_HOLD_MS)
    await _clear_highlight(page)


async def action_pause(page, event, target):
    await page.wait_for_timeout(int(event["duration"] * 1000))


async def action_narrate(page, event, target):
    """Pure narration beat: no click, no highlight, nothing changes on
    screen. Exists for lesson-opening scenario/outcome statements (see
    LESSON_CONTENT_STANDARD.md) that need to play before the first action
    fires, over whatever is already on screen. A short settle wait only,
    same as action_show_result."""
    await page.wait_for_timeout(500)


ACTIONS = {
    "highlight_target": action_highlight_target,
    "clear_highlight": action_clear_highlight,
    "click_new_question": action_click_new_question,
    "select_database": action_select_database,
    "select_table": action_select_table,
    "add_filter": action_add_filter,
    "visualize": action_visualize,
    "highlight_section": action_highlight_section,
    "show_result": action_show_result,
    "save_question": action_save_question,
    "add_to_dashboard": action_add_to_dashboard,
    "narrate": action_narrate,
    "pause": action_pause,
}


# --- recording orchestration --------------------------------------------

def _ffprobe_duration(path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def _transcode(raw_webm, out_mp4, expected_duration_s):
    """Matches engine/timeline_runner.py's convert_video(): raw Playwright
    webm -> H.264/yuv420p mp4, faststart. audit_narrator.py ffprobes this
    file's duration directly, so it must already be a finished mp4.

    Root cause of an earlier "no audio in final render" bug traced here
    (2026-08-14, fix pass 3): this used to receive whichever file
    glob.glob(video_dir/"*.webm")[0] happened to return, and video_dir
    accumulates a .webm from every past run of this lesson script,
    forever, uncleaned. glob's order is filesystem traversal order, not
    creation order, and it kept returning the SAME leftover ~111s file
    from an early session run on every single subsequent run, regardless
    of what had just actually been recorded, or how long it really ran.
    No amount of waiting or retrying the transcode ever fixed that,
    because the file being read was never wrong due to timing, it was
    simply the wrong file. run_lesson now gets the exact path for the
    page just recorded from Playwright's own page.video().path(), which
    is unambiguous and only resolves once that file is fully written.
    The check below is a cheap safety net against that class of bug
    recurring, not the primary fix.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw_webm),
            "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out_mp4),
        ],
        check=True, capture_output=True,
    )
    out_duration = _ffprobe_duration(out_mp4)
    if abs(out_duration - expected_duration_s) > 3.0:
        raise RuntimeError(
            f"transcoded mp4 is {out_duration:.1f}s but the recording "
            f"actually ran {expected_duration_s:.1f}s. Not returning a "
            f"silently-truncated video -- check that raw_webm points at "
            f"the correct source file for this run."
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

    audit_events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Unrecorded setup/login phase: pure demo-environment provisioning,
        # not instructional content. Runs in its own context so none of it
        # ends up in the video; its authenticated cookies are exported via
        # storage_state and carried into the recorded context below, so the
        # video opens already logged in rather than showing the login screen.
        setup_context = await browser.new_context(viewport=VIEWPORT)
        setup_page = await setup_context.new_page()
        await _ensure_account(setup_page, target)
        storage_state = await setup_context.storage_state()
        await setup_context.close()

        context = await browser.new_context(
            viewport=VIEWPORT,
            storage_state=storage_state,
            record_video_dir=str(video_dir),
            record_video_size=VIEWPORT,
        )
        # Recording starts at context creation, so the clock's zero-point
        # must start here too, not any earlier. Starting it before the
        # unrecorded login phase (a real bug in the first re-cut attempt)
        # offset every audit timestamp by however long login took relative
        # to the actual video, which would have scheduled every narration
        # clip that many seconds late against what's on screen.
        clock = Clock()
        page = await context.new_page()
        # Captured now, resolved to a real path only after context.close()
        # below. This is the actual fix for the "truncated video" bug (see
        # _transcode's docstring): video_dir accumulates a .webm from
        # every past run of this lesson, never cleaned up, and the
        # previous code picked glob.glob(video_dir/"*.webm")[0] -- glob's
        # order is filesystem traversal order, not creation order, and it
        # kept returning the SAME early leftover ~111s file on every run
        # regardless of what had just been recorded. Every earlier
        # "confirmed" render in this fix pass was actually re-transcoding
        # that one stale file. page.video() ties this call directly to
        # the page just created, with no directory-scan ambiguity, and
        # Playwright's own path() only resolves once the file is fully
        # written, which is also what several rounds of manual polling in
        # _transcode were trying (and failing) to approximate by hand.
        video = page.video
        await page.goto(target["base_url"])
        await page.wait_for_load_state("networkidle")

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

        # Ground truth for _transcode()'s truncation check: the real
        # wall-clock time the recording ran, from this script's own
        # Clock, not anything re-derived from the webm file after the
        # fact (see _transcode's docstring for why that's unreliable).
        expected_duration_s = clock.now_ms() / 1000
        await context.close()
        raw_webm = await video.path()
        await browser.close()

    if not raw_webm or not Path(raw_webm).exists():
        raise RuntimeError(f"no recorded video found for this run's page in {video_dir}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    mp4_path = output_dir / f"{lesson_id}_{timestamp}.mp4"
    _transcode(raw_webm, mp4_path, expected_duration_s)

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
