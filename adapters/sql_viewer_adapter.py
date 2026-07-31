#!/usr/bin/env python3
"""
WSDA Video Engine — SQL Viewer Adapter v3.1

Implements BaseAdapter for the WSDA web SQL viewer.

Key features:
- Cursor glow ring (visible in recordings)
- Three-phase execution: approach → focus → action
- Screen state management via clear()
- Semantic targets (no coordinates in production cards)
- Natural bezier mouse movement
- Transition-aware pause model
- SCHEMA FIX: reads actual SQLite schema and renders it in viewer
"""

from __future__ import annotations
import asyncio
import json
import math
import random
import sqlite3
from pathlib import Path
from playwright.async_api import Page
from rich.console import Console

from adapters.base_adapter import BaseAdapter
from engine.schemas import EVENT_ACTION_OFFSET, EVENT_APPROACH_LEAD

console = Console()


# ── Semantic target registry ───────────────────────────────────
# Named positions in the 1280x720 viewport.
# Updated when layout changes.

class TargetRegistry:
    """
    Maps semantic names to viewport coordinates.
    Updates when layout mode changes.
    """

    _SINGLE = {
        "schema_panel":      (100, 300),
        "schema_orders":     (100, 183),
        "schema_summary":    (100, 233),
        "schema_details":    (100, 133),
        "sql_query_1":       (740, 115),
        "sql_query_2":       (740, 195),
        "sql_query_3":       (740, 278),
        "results_area":      (740, 510),
        "results_top":       (740, 430),
        "results_center":    (740, 540),
        "topbar":            (640,  22),
        "neutral":           (640, 360),
        "status_bar":        (400, 710),
    }

    _COMPARE = {
        **_SINGLE,
        "results_area":      (740, 580),
        "compare_panel_1":   (370, 580),
        "compare_panel_2":   (740, 580),
        "compare_panel_3":  (1100, 580),
        "sql_query_1":       (740,  95),
        "sql_query_2":       (740, 145),
        "sql_query_3":       (740, 195),
    }

    def __init__(self):
        self._mode = "single"
        self._map = dict(self._SINGLE)

    def set_mode(self, mode: str):
        self._mode = mode
        if mode == "compare":
            self._map = dict(self._COMPARE)
        else:
            self._map = dict(self._SINGLE)

    def get(self, name: str) -> tuple[float, float]:
        return self._map.get(name, self._map["neutral"])


# ── Natural mouse movement ─────────────────────────────────────

async def bezier_move(page: Page, x: float, y: float, duration_ms: int = 500):
    """
    Move mouse along a quadratic bezier curve.
    Reads current position from JS tracker.
    Applies ease-in-out cubic timing.
    """
    current = await page.evaluate(
        "() => ({ x: window._mx || 640, y: window._my || 360 })"
    )
    cx, cy = current["x"], current["y"]

    # Skip if already close
    dist = math.sqrt((x - cx)**2 + (y - cy)**2)
    if dist < 5:
        return

    # Bezier control point (natural arc)
    ctrl_x = (cx + x) / 2 + random.uniform(-25, 25)
    ctrl_y = (cy + y) / 2 + random.uniform(-15, 15)

    steps = max(8, duration_ms // 16)

    for i in range(steps + 1):
        t = i / steps
        # Ease in-out cubic
        t_e = t * t * (3 - 2 * t)
        # Quadratic bezier
        bx = (1 - t_e)**2 * cx + 2*(1-t_e)*t_e*ctrl_x + t_e**2 * x
        by = (1 - t_e)**2 * cy + 2*(1-t_e)*t_e*ctrl_y + t_e**2 * y
        await page.mouse.move(bx, by)
        await asyncio.sleep(duration_ms / 1000 / steps)

    await page.evaluate(f"window._mx={x}; window._my={y};")


# ── Cursor highlighter CSS ─────────────────────────────────────
# Injected into the viewer page.
# Creates a visible glow ring that follows the cursor.
# Captured in the recording — makes mouse obvious to viewers.

CURSOR_HIGHLIGHT_CSS = """
#wsda-cursor-ring {
    position: fixed;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid rgba(255, 215, 0, 0.85);
    box-shadow: 0 0 8px rgba(255, 215, 0, 0.5),
                0 0 16px rgba(255, 215, 0, 0.2);
    pointer-events: none;
    z-index: 99999;
    transform: translate(-50%, -50%);
    transition: width 0.15s ease, height 0.15s ease,
                border-color 0.15s ease, box-shadow 0.15s ease;
    display: block;
}
#wsda-cursor-ring.active {
    width: 20px;
    height: 20px;
    border-color: rgba(6, 192, 21, 0.9);
    box-shadow: 0 0 6px rgba(6, 192, 21, 0.7),
                0 0 12px rgba(6, 192, 21, 0.3);
}
"""

CURSOR_HIGHLIGHT_JS = """
(function() {
    if (document.getElementById('wsda-cursor-ring')) return;

    const style = document.createElement('style');
    style.textContent = arguments[0];
    document.head.appendChild(style);

    const ring = document.createElement('div');
    ring.id = 'wsda-cursor-ring';
    document.body.appendChild(ring);

    document.addEventListener('mousemove', e => {
        ring.style.left = e.clientX + 'px';
        ring.style.top  = e.clientY + 'px';
        window._mx = e.clientX;
        window._my = e.clientY;
    });

    window.wsdaCursorActive = (on) => {
        ring.classList.toggle('active', on);
    };
})();
"""


# ── Pause model ────────────────────────────────────────────────

class PauseModel:
    """
    Natural pause durations by transition context.
    All values in seconds.
    """
    # Between approach completion and focus firing
    APPROACH_TO_FOCUS = 0.15

    # After focus, before action (when no narration gap)
    FOCUS_TO_ACTION = 0.3

    # After action completes, before returning
    ACTION_SETTLE = {
        "open_database":     0.6,
        "open_file":         0.5,
        "show_schema":       0.8,
        "highlight_section": 0.3,
        "run_query":         0.8,   # results render
        "show_result":       0.5,
        "clear_result":      0.2,
        "compare_results":   1.0,
        "zoom_result":       0.5,
        "focus_callout":     0.4,
        "set_layout":        0.4,
        "activate_table":    0.3,
        "fade_out":          1.5,
        "pause":             0.0,
    }

    @classmethod
    def after_action(cls, event_type: str) -> float:
        return cls.ACTION_SETTLE.get(event_type, 0.4)


PAUSE = PauseModel()


# ── SQL Viewer Adapter ─────────────────────────────────────────

class SQLViewerAdapter(BaseAdapter):
    """
    Controls the WSDA web SQL viewer.
    Implements full BaseAdapter interface.
    """

    BASE_URL = "http://127.0.0.1:5050"

    def __init__(self, page: Page, rehearsal: bool = False):
        self.page = page
        self.rehearsal = rehearsal
        self.targets = TargetRegistry()
        self._screen_state: set[str] = set()  # what is currently visible

    # ── Lifecycle ──────────────────────────────────────────────

    async def navigate(self) -> None:
        await self.page.goto(self.BASE_URL)
        await self.page.wait_for_selector("#schema-list")

        # Inject cursor highlighter
        await self.page.evaluate(CURSOR_HIGHLIGHT_JS, CURSOR_HIGHLIGHT_CSS)
        await self.page.evaluate("window._mx = 640; window._my = 360;")

        await self.set_status("Connected", True)
        console.print("[green]✓[/green] SQL Viewer loaded + cursor ring active")

    async def teardown(self) -> None:
        pass

    # ── Three-phase execution ──────────────────────────────────

    async def approach(self, target: str, lead_time_s: float = 0.5) -> None:
        """
        Phase 1: Move cursor to target before event fires.
        In rehearsal mode this is skipped for speed.
        """
        if self.rehearsal:
            return
        x, y = self.targets.get(target)
        # Slight jitter so it never lands on exact pixel
        jx = x + random.uniform(-6, 6)
        jy = y + random.uniform(-4, 4)
        duration_ms = int(lead_time_s * 1000 * 0.8)
        await bezier_move(self.page, jx, jy, duration_ms)

    async def focus(self, target: str, context: dict) -> None:
        """
        Phase 2: Highlight element as narration begins.
        Cursor is already positioned from approach().
        """
        event_type = context.get("type", "")

        if event_type == "highlight_section":
            section = context.get("section", "")
            await self._highlight_sql_section(section)

        elif event_type == "show_schema":
            await self._scan_schema()

        elif event_type == "activate_table":
            table = context.get("table", "")
            await self.page.evaluate(f"window.wsda.activateTable({json.dumps(table)})")

        elif event_type in ("run_query", "show_result"):
            # Cursor glow activates to signal imminent action
            await self._cursor_active(True)
            await asyncio.sleep(PAUSE.APPROACH_TO_FOCUS)
            await self._cursor_active(False)

        elif event_type == "compare_results":
            # Cursor scans to compare panel area
            await self.cursor_to("compare_panel_1", 300)

    async def action(self, event_type: str, params: dict) -> dict:
        """
        Phase 3: Execute the instructional event.
        Fires after narration ends + system offset.
        """
        result = {}

        if event_type == "open_database":
            result = await self._open_database(params.get("asset", ""))

        elif event_type == "open_file":
            result = await self._open_sql_file(params.get("asset", ""))

        elif event_type == "show_schema":
            result = await self._scan_schema()

        elif event_type == "highlight_section":
            await self._highlight_sql_section(params.get("section", ""))

        elif event_type == "run_query":
            result = await self._run_query(params.get("query_ref", ""))
            self._screen_state.add(f"result:{params.get('query_ref', '')}")

        elif event_type == "show_result":
            await self._highlight_result()

        elif event_type == "clear_result":
            for item in params.get("elements", []):
                await self._clear_element(item)

        elif event_type == "compare_results":
            targets = params.get("targets", [])
            await self._compare_results(targets)

        elif event_type == "zoom_result":
            await self._zoom_result()

        elif event_type == "focus_callout":
            await self._focus_callout(params)

        elif event_type == "set_layout":
            mode = params.get("mode", "single")
            await self._set_layout(mode)

        elif event_type == "activate_table":
            await self._activate_table(params.get("table_name", ""))

        elif event_type == "fade_out":
            await self._fade_out()

        elif event_type == "pause":
            duration = params.get("duration", 0)
            if duration:
                await asyncio.sleep(duration)

        return result

    # ── Screen state management ────────────────────────────────

    async def clear(self, elements: list[str]) -> None:
        """
        Clear named screen elements before a new concept begins.
        """
        for el in elements:
            if el == "all":
                await self._clear_all()
            elif el == "result":
                await self._clear_results()
            elif el == "highlight":
                await self._clear_highlights()
            elif el == "comparison":
                await self._clear_comparison()
            elif el == "annotations":
                await self._clear_annotations()
            elif el == "cursor":
                await self._cursor_active(False)

    async def verify_state(self, expected: dict) -> tuple[bool, str]:
        """Verify screen matches expected state."""
        # TODO: implement actual verification
        return True, "ok"

    # ── Cursor and attention ───────────────────────────────────

    async def cursor_to(self, target: str, duration_ms: int = 500) -> None:
        x, y = self.targets.get(target)
        await bezier_move(self.page, x, y, duration_ms)

    async def highlight_cursor(self, active: bool) -> None:
        await self._cursor_active(active)

    # ── Layout ────────────────────────────────────────────────

    async def set_layout(self, mode: str, options: dict | None = None) -> None:
        await self._set_layout(mode)

    # ── Status ────────────────────────────────────────────────

    async def set_status(self, text: str, active: bool = True) -> None:
        color = "var(--green)" if active else "var(--text-dim)"
        await self.page.evaluate(f"""
            const el = document.getElementById('status-text');
            if (el) {{ el.textContent = {json.dumps(text)}; el.style.color = '{color}'; }}
        """)

    # ═══════════════════════════════════════════════════════════
    #  Internal action implementations
    # ═══════════════════════════════════════════════════════════

    async def _open_database(self, asset_path: str) -> dict:
        """Load database and render its schema in the viewer."""
        db_name = Path(asset_path).name
        await self.page.evaluate(f"loadDatabase({json.dumps(db_name)});")

        # SCHEMA FIX: read actual SQLite schema and render it
        schema = self._get_schema(asset_path)
        if schema:
            await self.page.evaluate(f"renderSchema({json.dumps(schema)});")

        await asyncio.sleep(PAUSE.after_action("open_database"))
        return {"db": db_name, "schema_loaded": len(schema)}

    def _get_schema(self, db_path: str) -> list:
        """Read SQLite schema and return format expected by renderSchema()."""
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = []
            for (name,) in cur.fetchall():
                cur.execute(f"PRAGMA table_info({name})")
                cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
                tables.append({"name": name, "columns": cols})
            conn.close()
            return tables
        except Exception as e:
            console.print(f"[yellow]⚠ Could not read schema: {e}[/yellow]")
            return []

    async def _open_sql_file(self, asset_path: str) -> dict:
        """Load SQL file content into editor."""
        content = Path(asset_path).read_text()
        await self.page.evaluate(f"setSQL({json.dumps(content)});")
        await asyncio.sleep(PAUSE.after_action("open_file"))
        return {"lines": len(content.splitlines())}

    async def _scan_schema(self) -> dict:
        """Expand schema panel and show all tables."""
        await self.page.evaluate("expandSchema();")
        # Expand all table names
        await self.page.evaluate("""
            document.querySelectorAll('.schema-table-name').forEach(el => {
                el.classList.add('expanded');
                el.nextElementSibling.classList.add('visible');
            });
        """)
        await asyncio.sleep(PAUSE.after_action("show_schema"))
        return {"scanned": True}

    async def _highlight_sql_section(self, section: str) -> None:
        """Highlight a named section in the SQL editor."""
        await self.page.evaluate(f"highlightSection({json.dumps(section)});")
        await asyncio.sleep(PAUSE.after_action("highlight_section"))

    async def _run_query(self, query_ref: str) -> dict:
        """Execute current SQL query."""
        await self.page.evaluate("runQuery();")
        await asyncio.sleep(PAUSE.after_action("run_query"))
        return {"query_ref": query_ref}

    async def _highlight_result(self) -> None:
        """Highlight the results area."""
        await self.page.evaluate("zoomResults();")
        await asyncio.sleep(PAUSE.after_action("show_result"))

    async def _clear_results(self) -> None:
        await self.page.evaluate("""
            const wrap = document.getElementById('results-wrap');
            if (wrap) wrap.innerHTML = '';
        """)

    async def _clear_highlights(self) -> None:
        await self.page.evaluate("clearHighlights(null);")

    async def _clear_annotations(self) -> None:
        await self.page.evaluate("clearAnnotations(null);")

    async def _clear_comparison(self) -> None:
        await self.page.evaluate("resetZoom();")

    async def _clear_all(self) -> None:
        await self._clear_results()
        await self._clear_highlights()
        await self._clear_annotations()

    async def _compare_results(self, targets: list) -> None:
        """Show comparison layout."""
        self.targets.set_mode("compare")
        await self.page.evaluate("zoomResults();")
        await asyncio.sleep(PAUSE.after_action("compare_results"))

    async def _zoom_result(self) -> None:
        await self.page.evaluate("zoomResults();")
        await asyncio.sleep(PAUSE.after_action("zoom_result"))

    async def _focus_callout(self, params: dict) -> None:
        """Add cell callout annotation."""
        row = params.get("row_index", 0)
        col = params.get("col_index", 0)
        text = params.get("text", "")
        await self.page.evaluate(f"""
            annotateCell(null, {row}, {col}, {json.dumps(text)});
        """)
        await asyncio.sleep(PAUSE.after_action("focus_callout"))

    async def _set_layout(self, mode: str) -> None:
        self.targets.set_mode(mode)
        await asyncio.sleep(PAUSE.after_action("set_layout"))

    async def _activate_table(self, table_name: str) -> None:
        await self.page.evaluate(f"activateTable({json.dumps(table_name)});")
        await asyncio.sleep(PAUSE.after_action("activate_table"))

    async def _fade_out(self) -> None:
        await self.page.evaluate("fadeOut();")
        await asyncio.sleep(PAUSE.after_action("fade_out"))

    async def _cursor_active(self, active: bool) -> None:
        await self.page.evaluate(f"window.wsdaCursorActive({str(active).lower()});")
