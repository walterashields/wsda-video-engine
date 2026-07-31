#!/usr/bin/env python3
"""
silent_renderer.py — WSDA Silent Renderer v2.3

Executes storyboard events through SQLViewerAdapterV2 while recording
via Playwright.

FIXES:
  - Auto-hides title card after dwell so SQL editor is visible
  - Resolves actual .db file path for open_database
  - Logs adapter errors with full traceback
  - Takes debug screenshots after each event
"""

import asyncio
import http.server
import socketserver
import threading
import traceback
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

import sys
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from adapters.sql_viewer_adapter import SQLViewerAdapterV2

VIEWER_HTML = ROOT / "web" / "templates" / "viewer.html"


def find_db_file() -> str:
    """Find the most recently created .db file in the project."""
    db_files = []
    for db in ROOT.rglob("*.db"):
        db_files.append((db.stat().st_mtime, db))
    if not db_files:
        return ""
    db_files.sort(reverse=True)
    return str(db_files[0][1].absolute())


class ViewerServer:
    def __init__(self, port: int = 0):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        viewer_dir = VIEWER_HTML.parent
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(viewer_dir), **kwargs)
            def log_message(self, format, *args):
                pass
        self.server = socketserver.TCPServer(("127.0.0.1", self.port), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.port}/viewer.html"

    def stop(self):
        if self.server:
            self.server.shutdown()


class SilentRenderer:
    def __init__(self):
        self.server = ViewerServer()
        self.browser = None
        self.playwright = None
        self.adapter = None
        self.page = None

    async def start(self):
        self.viewer_url = self.server.start()
        await asyncio.sleep(0.3)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.server.stop()

    async def render_async(self, storyboard_path: Path, output_mp4: Path):
        with open(storyboard_path) as f:
            storyboard = yaml.safe_load(f)

        visual = storyboard.get("visual_storyboard", storyboard)
        events = visual.get("events", [])

        if not events:
            print("[Renderer] WARNING: No events in storyboard")
            return

        print(f"[Renderer] Rendering {len(events)} events...")

        await self.start()

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(output_mp4.parent),
            record_video_size={"width": 1920, "height": 1080}
        )

        self.page = await context.new_page()
        await self.page.goto(self.viewer_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.5)

        self.adapter = SQLViewerAdapterV2(output_dir=output_mp4.parent)
        self.adapter.page = self.page
        self.adapter.browser = self.browser

        total_pause = 0
        for i, event in enumerate(events):
            etype = event.get("type", "")
            pause = event.get("pause", 1.0)
            params = event.get("params", {})

            print(f"[Renderer] Event {i+1}/{len(events)}: {etype} (pause: {pause}s)")

            try:
                await self._execute_event(etype, params)
            except Exception as e:
                print(f"[Renderer] ✗ Event {etype} failed: {e}")
                traceback.print_exc()

            # Debug screenshot
            screenshot_path = output_mp4.parent / f"debug_{i:02d}_{etype}.png"
            try:
                await self.page.screenshot(path=str(screenshot_path))
            except Exception:
                pass

            await asyncio.sleep(pause)
            total_pause += pause

            # CRITICAL FIX: Auto-hide title card so next events are visible
            if etype == "show_title_card":
                try:
                    print("[Renderer]   → Auto-hiding title card")
                    await self.adapter.hide_title_card()
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print(f"[Renderer]   → hide_title_card failed: {e}")

        print(f"[Renderer] Events complete. Total dwell time: {total_pause:.1f}s")
        await asyncio.sleep(1.0)

        await context.close()
        await self.stop()

        # Convert webm to mp4
        import subprocess
        webm_files = sorted(output_mp4.parent.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
        if webm_files:
            webm_path = webm_files[0]
            subprocess.run([
                "ffmpeg", "-y", "-i", str(webm_path),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output_mp4)
            ], capture_output=True)
            webm_path.unlink()
            print(f"[Renderer] Saved: {output_mp4}")
        else:
            print("[Renderer] WARNING: No video file generated")

    async def _execute_event(self, etype: str, params: dict):
        adapter = self.adapter

        if etype == "show_title_card":
            await adapter.show_title_card(
                badge=params.get("badge", "SQL Lesson"),
                headline=params.get("headline", ""),
                sub=params.get("sub", ""),
                stakes=params.get("stakes", "")
            )

        elif etype == "hide_title_card":
            await adapter.hide_title_card()

        elif etype == "open_database":
            db_name = params.get("db_name", params.get("asset", ""))
            db_path = db_name
            if not db_path or not Path(db_path).exists():
                db_path = find_db_file()
            if db_path:
                print(f"[Renderer]   → Loading DB: {db_path}")
                await adapter.open_database(db_path)
            else:
                print("[Renderer]   → WARNING: No .db file found")

        elif etype == "show_schema":
            await adapter.show_schema()

        elif etype == "expand_schema":
            await adapter.expand_schema()

        elif etype == "collapse_schema":
            await adapter.collapse_schema()

        elif etype == "activate_table":
            await adapter.activate_table(params.get("table_name", params.get("table", "")))

        elif etype == "set_sql":
            content = params.get("query_text", params.get("content", ""))
            print(f"[Renderer]   → SQL: {content[:60]}...")
            await adapter.set_sql(content)

        elif etype == "highlight_section":
            await adapter.highlight_section(params.get("section", ""))

        elif etype == "run_query":
            await adapter.run_query()

        elif etype in ("show_results", "show_result"):
            columns = params.get("columns", [])
            rows = params.get("rows", [])
            print(f"[Renderer]   → Results: {len(rows)} rows, {len(columns)} cols")
            await adapter.show_results(
                columns=columns,
                rows=rows,
                query_name=params.get("query_name", "")
            )

        elif etype == "highlight_row":
            await adapter.highlight_row(
                row_index=params.get("row_index", 0),
                color=params.get("color", "blue")
            )

        elif etype == "clear_highlights":
            await adapter.clear_row_highlights()

        elif etype == "annotate_cell":
            await adapter.annotate_cell(
                row_index=params.get("row_index", 0),
                col_index=params.get("col_index", 0),
                text=params.get("text", "")
            )

        elif etype == "clear_annotations":
            await adapter.clear_annotations()

        elif etype == "zoom_results":
            await adapter.zoom_results()

        elif etype == "reset_zoom":
            await adapter.reset_zoom()

        elif etype == "set_query_color":
            await adapter.set_query_color(
                start_line=params.get("start_line", 0),
                end_line=params.get("end_line", 0),
                label_type=params.get("label_type", "")
            )

        elif etype == "fade_out":
            await adapter.fade_out()

        elif etype == "pause":
            await adapter.pause(params.get("duration", 1.0))

        else:
            print(f"[Renderer] Unknown event type: {etype}")

    def render(self, storyboard_path: Path, output_mp4: Path):
        asyncio.run(self.render_async(Path(storyboard_path), Path(output_mp4)))

    def render_sync(self, storyboard_path: Path, output_mp4: Path):
        self.render(storyboard_path, output_mp4)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 silent_renderer.py <storyboard.yml> <output.mp4>")
        sys.exit(1)
    renderer = SilentRenderer()
    renderer.render(sys.argv[1], sys.argv[2])
