#!/usr/bin/env python3
"""
WSDA SQL Viewer Adapter v2 — Production-ready with visual effects

This adapter drives the new viewer_v2.html with all visual features:
- Title cards for opening hooks
- Schema collapse/expand for clean visuals
- Row highlighting (blue/red/green) for emphasis
- Cell annotations (floating callouts) for punchline numbers
- Results zoom for emphasis moments
- Query color coding (correct=green, buggy=red)
- Smooth CSS transitions for all state changes
"""

import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path

from playwright.async_api import async_playwright

VIEWER_URL = "http://localhost:7010/viewer"


class SQLViewerAdapterV2:
    """Production-ready SQL viewer adapter with full visual effects support."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.page = None
        self.browser = None

    async def start(self):
        """Launch browser and open viewer."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 1920, "height": 1080})
        await self.page.goto(VIEWER_URL)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.5)

    async def stop(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ── Title Card ──
    async def show_title_card(self, badge: str = "SQL Lesson", headline: str = "",
                              sub: str = "", stakes: str = ""):
        """Display full-screen title card. Call this as FIRST event."""
        await self.page.evaluate(f"""
            showTitleCard({json.dumps(badge)}, {json.dumps(headline)},
                          {json.dumps(sub)}, {json.dumps(stakes)});
        """)
        await asyncio.sleep(0.6)  # Wait for CSS animation

    async def hide_title_card(self):
        """Dismiss title card overlay."""
        await self.page.evaluate("hideTitleCard();")
        await asyncio.sleep(0.6)

    # ── Schema Panel ──
    async def expand_schema(self):
        """Show schema sidebar."""
        await self.page.evaluate("expandSchema();")
        await asyncio.sleep(0.4)

    async def collapse_schema(self):
        """Hide schema sidebar to reduce clutter."""
        await self.page.evaluate("collapseSchema();")
        await asyncio.sleep(0.4)

    async def activate_table(self, table_name: str):
        """Expand a specific table in schema panel."""
        await self.page.evaluate(f"activateTable({json.dumps(table_name)});")
        await asyncio.sleep(0.3)

    # ── SQL Editor ──
    async def set_sql(self, content: str):
        """Set SQL editor content."""
        await self.page.evaluate(f"setSQL({json.dumps(content)});")
        await asyncio.sleep(0.2)

    async def highlight_section(self, section_name: str):
        """Highlight a named SQL section."""
        await self.page.evaluate(f"highlightSection({json.dumps(section_name)});")
        await asyncio.sleep(0.3)

    # ── Query Execution ──
    async def run_query(self):
        """Execute current SQL."""
        await self.page.evaluate("runQuery();")
        await asyncio.sleep(0.5)

    async def show_results(self, columns: list, rows: list, query_name: str = ""):
        """Display query results."""
        await self.page.evaluate(f"""
            showResults({json.dumps(columns)}, {json.dumps(rows)}, {json.dumps(query_name)});
        """)
        await asyncio.sleep(0.3)

    # ── Visual Effects ──
    async def highlight_row(self, row_index: int, color: str = "blue"):
        """Emphasize a specific row. Use 'red' for wrong, 'green' for correct."""
        await self.page.evaluate(f"highlightRow(null, {row_index}, {json.dumps(color)});")
        await asyncio.sleep(0.3)

    async def clear_row_highlights(self):
        """Remove all row highlighting."""
        await self.page.evaluate("clearHighlights(null);")
        await asyncio.sleep(0.2)

    async def annotate_cell(self, row_index: int, col_index: int, text: str):
        """Add floating callout on a cell."""
        await self.page.evaluate(f"""
            annotateCell(null, {row_index}, {col_index}, {json.dumps(text)});
        """)
        await asyncio.sleep(0.4)

    async def clear_annotations(self):
        """Remove all cell callouts."""
        await self.page.evaluate("clearAnnotations(null);")
        await asyncio.sleep(0.2)

    async def zoom_results(self):
        """Expand results panel to 65% for emphasis."""
        await self.page.evaluate("zoomResults();")
        await asyncio.sleep(0.4)

    async def reset_zoom(self):
        """Restore default panel heights."""
        await self.page.evaluate("resetZoom();")
        await asyncio.sleep(0.3)

    async def set_query_color(self, start_line: int, end_line: int, label_type: str):
        """Color-code query block as 'correct' or 'buggy'."""
        await self.page.evaluate(f"""
            setQueryColor({start_line}, {end_line}, {json.dumps(label_type)});
        """)
        await asyncio.sleep(0.2)

    # ── Database ──
    async def open_database(self, db_path: str):
        """Load SQLite database."""
        # Copy DB to viewer accessible location
        await self.page.evaluate(f"loadDatabase({json.dumps(Path(db_path).name)});")
        await asyncio.sleep(0.5)

    async def show_schema(self):
        """Display database schema."""
        await self.page.evaluate("showSchema();")
        await asyncio.sleep(0.3)

    # ── Cursor ──
    async def move_cursor(self, x: int, y: int):
        """Move cursor ring to position."""
        await self.page.evaluate(f"moveCursorRing({x}, {y});")
        await asyncio.sleep(0.15)

    async def hide_cursor(self):
        """Hide cursor ring."""
        await self.page.evaluate("hideCursorRing();")
        await asyncio.sleep(0.1)

    # ── Transitions ──
    async def fade_out(self):
        """Fade to black."""
        await self.page.evaluate("fadeOut();")
        await asyncio.sleep(1.5)

    async def pause(self, seconds: float):
        """Wait for specified duration."""
        await asyncio.sleep(seconds)

    # ── Screenshot ──
    async def screenshot(self, path: str):
        """Capture current frame."""
        await self.page.screenshot(path=path)

    # ── Event Router ──
    async def handle_event(self, event: dict):
        """Route a production card event to the appropriate handler."""
        etype = event.get("type")
        handlers = {
            "show_title_card": lambda e: self.show_title_card(
                e.get("badge", "SQL Lesson"), e.get("headline", ""),
                e.get("sub", ""), e.get("stakes", "")
            ),
            "hide_title_card": lambda e: self.hide_title_card(),
            "open_database": lambda e: self.open_database(e.get("asset", "")),
            "show_schema": lambda e: self.show_schema(),
            "expand_schema": lambda e: self.expand_schema(),
            "collapse_schema": lambda e: self.collapse_schema(),
            "activate_table": lambda e: self.activate_table(e.get("table", "")),
            "open_file": lambda e: self.set_sql(Path(e.get("asset", "")).read_text()),
            "highlight_section": lambda e: self.highlight_section(e.get("section", "")),
            "run_query": lambda e: self.run_query(),
            "show_result": lambda e: self.show_results(
                e.get("columns", []), e.get("rows", []), e.get("query_name", "")
            ),
            "highlight_row": lambda e: self.highlight_row(e.get("row_index", 0), e.get("color", "blue")),
            "clear_highlights": lambda e: self.clear_row_highlights(),
            "annotate_cell": lambda e: self.annotate_cell(
                e.get("row_index", 0), e.get("col_index", 0), e.get("text", "")
            ),
            "clear_annotations": lambda e: self.clear_annotations(),
            "zoom_results": lambda e: self.zoom_results(),
            "reset_zoom": lambda e: self.reset_zoom(),
            "set_query_color": lambda e: self.set_query_color(
                e.get("start_line", 0), e.get("end_line", 0), e.get("label_type", "")
            ),
            "pause": lambda e: self.pause(float(e.get("duration", 1.0))),
            "fade_out": lambda e: self.fade_out(),
        }
        handler = handlers.get(etype)
        if handler:
            await handler(event)
        else:
            print(f"[AdapterV2] Unknown event type: {etype}")


# ── Backwards Compatibility ──
class SQLViewerAdapter(SQLViewerAdapterV2):
    """Backwards-compatible wrapper that extends v2 with v1 method names."""
    pass
