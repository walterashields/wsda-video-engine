#!/usr/bin/env python3
"""
WSDA Silent Renderer — Record video from visual storyboard without audio

Reads a visual storyboard YAML and executes each event in the browser,
recording the screen to an MP4. No audio is generated — this is the
silent video that the narrator will later watch and describe.

Usage:
    from silent_renderer import SilentRenderer
    renderer = SilentRenderer()
    renderer.render("storyboard.yml", "silent.mp4")
"""

import asyncio
import json
import subprocess
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

VIEWER_URL = "http://localhost:7010/viewer"


class SilentRenderer:
    """Renders a visual storyboard to silent MP4 using Playwright."""

    def __init__(self, viewer_url: str = VIEWER_URL):
        self.viewer_url = viewer_url
        self.page = None
        self.browser = None
        self.playwright = None

    async def start(self):
        """Launch browser and open viewer."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 1920, "height": 1080})
        await self.page.goto(self.viewer_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.5)

    async def stop(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ── Event Handlers ──────────────────────────────────────────────────────
    async def handle_show_title_card(self, params: dict):
        await self.page.evaluate(f"""
            showTitleCard(
                {json.dumps(params.get('badge', 'SQL Lesson'))},
                {json.dumps(params.get('headline', ''))},
                {json.dumps(params.get('sub', ''))},
                {json.dumps(params.get('stakes', ''))}
            );
        """)
        await asyncio.sleep(0.6)

    async def handle_hide_title_card(self, params: dict):
        await self.page.evaluate("hideTitleCard();")
        await asyncio.sleep(0.6)

    async def handle_open_database(self, params: dict):
        await self.page.evaluate(f"loadDatabase({json.dumps(params.get('db_name', ''))});")
        await asyncio.sleep(0.5)

    async def handle_expand_schema(self, params: dict):
        await self.page.evaluate("expandSchema();")
        await asyncio.sleep(0.4)

    async def handle_collapse_schema(self, params: dict):
        await self.page.evaluate("collapseSchema();")
        await asyncio.sleep(0.4)

    async def handle_activate_table(self, params: dict):
        await self.page.evaluate(f"activateTable({json.dumps(params.get('table_name', ''))});")
        await asyncio.sleep(0.3)

    async def handle_set_sql(self, params: dict):
        await self.page.evaluate(f"setSQL({json.dumps(params.get('query_text', ''))});")
        label = params.get('label', '')
        if label:
            # Add color coding class
            await self.page.evaluate(f"setQueryColor(0, 999, {json.dumps(label)});")
        await asyncio.sleep(0.3)

    async def handle_highlight_section(self, params: dict):
        await self.page.evaluate(f"highlightSection({json.dumps(params.get('section_name', ''))});")
        await asyncio.sleep(0.3)

    async def handle_run_query(self, params: dict):
        await self.page.evaluate("runQuery();")
        await asyncio.sleep(0.5)

    async def handle_show_results(self, params: dict):
        await self.page.evaluate(f"""
            showResults(
                {json.dumps(params.get('columns', []))},
                {json.dumps(params.get('rows', []))},
                {json.dumps(params.get('query_name', ''))}
            );
        """)
        # Apply highlights and annotations
        highlight = params.get('highlight_row')
        if highlight is not None:
            color = params.get('highlight_color', 'blue')
            await self.page.evaluate(f"highlightRow(null, {highlight}, {json.dumps(color)});")

        annotate = params.get('annotate_cell')
        if annotate:
            await self.page.evaluate(f"""
                annotateCell(null, {annotate['row']}, {annotate['col']}, {json.dumps(annotate['text'])});
            """)
        await asyncio.sleep(0.4)

    async def handle_zoom_results(self, params: dict):
        await self.page.evaluate("zoomResults();")
        await asyncio.sleep(0.4)

    async def handle_reset_zoom(self, params: dict):
        await self.page.evaluate("resetZoom();")
        await asyncio.sleep(0.3)

    async def handle_highlight_row(self, params: dict):
        await self.page.evaluate(f"""
            highlightRow(null, {params.get('row_index', 0)}, {json.dumps(params.get('color', 'blue'))});
        """)
        await asyncio.sleep(0.3)

    async def handle_annotate_cell(self, params: dict):
        await self.page.evaluate(f"""
            annotateCell(null, {params['row_index']}, {params['col_index']}, {json.dumps(params['text'])});
        """)
        await asyncio.sleep(0.4)

    async def handle_clear_highlights(self, params: dict):
        await self.page.evaluate("clearHighlights(null);")
        await asyncio.sleep(0.2)

    async def handle_clear_annotations(self, params: dict):
        await self.page.evaluate("clearAnnotations(null);")
        await asyncio.sleep(0.2)

    async def handle_fade_out(self, params: dict):
        await self.page.evaluate("fadeOut();")
        await asyncio.sleep(1.5)

    async def handle_pause(self, params: dict):
        duration = float(params.get('duration', 2.0))
        await asyncio.sleep(duration)

    # ── Main Render Loop ────────────────────────────────────────────────────
    async def render_async(self, storyboard_path: Path, output_mp4: Path):
        """Render storyboard to silent MP4."""
        with open(storyboard_path) as f:
            storyboard = yaml.safe_load(f)

        events = storyboard.get("events", [])

        # Start browser
        await self.start()

        # Start ffmpeg recording
        # We'll use Playwright's built-in video recording instead
        # This is simpler and more reliable

        # Actually, let's use ffmpeg to record the browser viewport
        # First, we need to know the browser's CDP websocket URL
        cdp_ws = self.page.context.browser.ws_endpoint if hasattr(self.page.context.browser, 'ws_endpoint') else None

        # For now, use Playwright's video recording
        # Enable video recording on the context
        # We need to restart with video enabled
        await self.stop()

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

        # Create context with video recording
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(output_mp4.parent),
            record_video_size={"width": 1920, "height": 1080}
        )
        self.page = await context.new_page()
        await self.page.goto(self.viewer_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.5)

        # Execute events
        handlers = {
            "show_title_card": self.handle_show_title_card,
            "hide_title_card": self.handle_hide_title_card,
            "open_database": self.handle_open_database,
            "expand_schema": self.handle_expand_schema,
            "collapse_schema": self.handle_collapse_schema,
            "activate_table": self.handle_activate_table,
            "set_sql": self.handle_set_sql,
            "highlight_section": self.handle_highlight_section,
            "run_query": self.handle_run_query,
            "show_results": self.handle_show_results,
            "zoom_results": self.handle_zoom_results,
            "reset_zoom": self.handle_reset_zoom,
            "highlight_row": self.handle_highlight_row,
            "annotate_cell": self.handle_annotate_cell,
            "clear_highlights": self.handle_clear_highlights,
            "clear_annotations": self.handle_clear_annotations,
            "fade_out": self.handle_fade_out,
            "pause": self.handle_pause,
        }

        for event in events:
            etype = event.get("type")
            handler = handlers.get(etype)
            if handler:
                await handler(event)
            else:
                print(f"[SilentRenderer] Unknown event: {etype}")

        # Close context to save video
        await context.close()
        await self.browser.close()
        await self.playwright.stop()

        # Playwright saves video with a generated name, we need to rename it
        # Find the video file
        video_files = list(output_mp4.parent.glob("*.webm"))
        if video_files:
            # Convert webm to mp4 using ffmpeg
            webm_path = video_files[0]
            subprocess.run([
                "ffmpeg", "-y", "-i", str(webm_path),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", str(output_mp4)
            ], check=True, capture_output=True)
            webm_path.unlink()  # Clean up webm

        print(f"[SilentRenderer] Saved: {output_mp4}")

    def render(self, storyboard_path: Path, output_mp4: Path):
        """Synchronous wrapper for render_async."""
        asyncio.run(self.render_async(Path(storyboard_path), Path(output_mp4)))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 silent_renderer.py <storyboard.yml> <output.mp4>")
        sys.exit(1)

    renderer = SilentRenderer()
    renderer.render(sys.argv[1], sys.argv[2])
