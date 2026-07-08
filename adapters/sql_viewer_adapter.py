"""
WSDA Video Engine — SQL Viewer Adapter v3

Implements BaseAdapter for the WSDA web SQL viewer.

Key features:
- Cursor glow ring (visible in recordings)
- Three-phase execution: approach → focus → action
- Screen state management via clear()
- Semantic targets (no coordinates in production cards)
- Natural bezier mouse movement
- Transition-aware pause model
"""

from __future__ import annotations
import asyncio
import json
import math
import random
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
        self._schema_table_count = 0
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
            result = await self._open_database(params["asset"])

        elif event_type == "open_file":
            result = await self._open_sql_file(params["asset"])

        elif event_type == "show_schema":
            result = await self._scan_schema()

        elif event_type == "open_view":
            # Fetch CREATE VIEW SQL from Flask, inject into SQL editor pane
            import json as _json
            view_name = params.get("view", "")
            view_sql = ""
            try:
                result = await self._api("/api/get-view-sql", {"view": view_name})
                view_sql = result.get("sql", "")
            except Exception as e:
                console.print(f"  [yellow]open_view warning: {e}[/yellow]")

            if view_sql:
                sql_json = _json.dumps(view_sql)
                vn_json  = _json.dumps(view_name)
                js = ("(function(){"
                      f"var sql={sql_json}; var name={vn_json};"
                      "if(window.showViewDefinition){window.showViewDefinition(name,sql);}"
                      "else{"
                      "  var el=document.getElementById('sql-content-single');"
                      "  if(el) el.innerHTML=window.syntaxHL?window.syntaxHL(sql):sql;"
                      "}"
                      "document.querySelectorAll('.table-item')"
                      "  .forEach(function(e){e.classList.remove('active');});"
                      "var v=document.querySelector('[data-table="'+name+'"]');"
                      "if(v){v.classList.add('active');}"
                      "})();")
                await self.page.evaluate(js)
                console.print(f"  [green]✓[/green] View loaded: {view_name}")
            else:
                console.print(f"  [yellow]⚠[/yellow] No SQL found for view: {view_name}")
            await asyncio.sleep(1.0)


        elif event_type == "highlight_section":
            await self._expand_sql_pane()
            await self._highlight_sql_section(params.get("section", ""))

        elif event_type == "run_query":
            result = await self._run_query(params.get("query_ref", ""))
            self._screen_state.add(f"result:{params.get('query_ref', '')}")

        elif event_type == "show_result":
            await self._collapse_sql_pane()
            await self._highlight_result()

        elif event_type == "clear_result":
            for item in params.get("elements", []):
                await self._clear_element(item)

        elif event_type == "compare_results":
            targets = params.get("targets", [])
            await self._compare_results(targets)

        elif event_type == "zoom_result":
            await self.page.evaluate(
                "window.wsda.applyAttention('zoom', [], 2.0)"
            )
            await asyncio.sleep(2.0)

        elif event_type == "focus_callout":
            await self.page.evaluate(
                "window.wsda.applyAttention('callout', [], 2.0)"
            )
            await asyncio.sleep(2.0)

        elif event_type == "set_layout":
            # When switching to compare, auto-populate from result history
            mode = params.get("mode", "compare")
            history_keys = list(self._screen_state)
            result_refs = [k.replace("result:","") for k in history_keys if k.startswith("result:")]
            if mode == "compare" and result_refs:
                panels = [{"id": r, "label": r.replace("_"," ").title()} for r in result_refs]
                await self.set_layout("compare", {"panels": panels})
            else:
                await self.set_layout(mode, params)

        elif event_type == "activate_table":
            table = params.get("table") or params.get("target", "")
            await self.page.evaluate(f"window.wsda.activateTable({json.dumps(table)})")

        elif event_type == "fade_out":
            await self.page.evaluate("window.wsda.fadeOut(1.5)")
            await asyncio.sleep(1.5)

        elif event_type == "pause":
            duration = params.get("duration", 1.0)
            await asyncio.sleep(duration)

        await asyncio.sleep(PAUSE.after_action(event_type))
        return result

    # ── Screen state management ────────────────────────────────

    async def clear(self, elements: list[str]) -> None:
        """
        Clear named screen elements before new concept begins.
        Prevents stale results from showing during next narration.
        """
        for element in elements:
            await self._clear_element(element)

    async def _clear_element(self, element: str) -> None:
        if element == "result" or element == "all_results":
            # Fade results to dimmed state, then clear
            await self.page.evaluate("""
                () => {
                    const area = document.getElementById('results-area-single');
                    if (area) {
                        area.style.transition = 'opacity 0.3s ease';
                        area.style.opacity = '0.15';
                    }
                }
            """)
            await asyncio.sleep(0.3)
            await self.page.evaluate("""
                () => {
                    const area = document.getElementById('results-area-single');
                    if (area) {
                        area.innerHTML = '<div class="empty-state"><div class="empty-icon">▷</div><div>Run a query to see results</div></div>';
                        area.style.opacity = '1';
                    }
                    const meta = document.getElementById('results-meta-single');
                    if (meta) meta.textContent = '';
                    const sbRows = document.getElementById('sb-rows');
                    if (sbRows) sbRows.textContent = '';
                    const sbRef = document.getElementById('sb-ref');
                    if (sbRef) sbRef.textContent = '';
                }
            """)
            # Clear from state tracking
            self._screen_state = {
                s for s in self._screen_state if not s.startswith("result:")
            }

        elif element == "highlight":
            await self.page.evaluate("""
                document.querySelectorAll('.sql-block').forEach(b => 
                    b.classList.remove('highlighted')
                );
            """)

        elif element == "all":
            await self.clear(["result", "highlight"])

    async def verify_state(self, expected: dict) -> tuple[bool, str]:
        """Verify screen state matches expectations."""
        state = await self.page.evaluate("() => window.wsda ? 'ready' : 'not_ready'")
        if state != "ready":
            return False, "Viewer not initialized"
        return True, "OK"

    # ── Cursor ─────────────────────────────────────────────────

    async def cursor_to(self, target: str, duration_ms: int = 500) -> None:
        if self.rehearsal:
            return
        x, y = self.targets.get(target)
        jx = x + random.uniform(-5, 5)
        jy = y + random.uniform(-4, 4)
        await bezier_move(self.page, jx, jy, duration_ms)

    async def highlight_cursor(self, active: bool) -> None:
        await self._cursor_active(active)

    async def _cursor_active(self, active: bool) -> None:
        if self.rehearsal:
            return
        await self.page.evaluate(
            f"if(window.wsdaCursorActive) window.wsdaCursorActive({str(active).lower()})"
        )

    # ── Layout ─────────────────────────────────────────────────

    async def set_layout(self, mode: str, options: dict | None = None) -> None:
        console.print(f"  Layout → [bold]{mode}[/bold]")
        panels = (options or {}).get("panels", None)
        opts = {"panels": panels} if panels else {}
        await self.page.evaluate(f"""
            window.wsda.setLayout({json.dumps(mode)}, {json.dumps(opts)})
        """)
        self.targets.set_mode(mode)
        await asyncio.sleep(0.4)

    # ── Status ─────────────────────────────────────────────────

    async def set_status(self, text: str, active: bool = True) -> None:
        await self.page.evaluate(
            f"window.wsda.setStatus({json.dumps(text)}, {str(active).lower()})"
        )

    # ── Private implementations ────────────────────────────────

    async def _api(self, endpoint: str, payload: dict) -> dict:
        return await self.page.evaluate(f"""
            async () => {{
                const r = await fetch('{endpoint}', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({json.dumps(payload)})
                }});
                return await r.json();
            }}
        """)

    async def _open_database(self, db_path: str) -> dict:
        console.print(f"  Opening: [cyan]{Path(db_path).name}[/cyan]")
        await self.cursor_to("schema_panel", 600)
        result = await self._api("/api/load-db", {"path": db_path})
        if not result.get("success"):
            raise RuntimeError(f"DB load failed: {result.get('error')}")
        schema = result["schema"]
        self._schema_table_count = len([1 for info in schema.values() if not info.get("is_view")])
        await self.page.evaluate(f"window.wsda.renderSchema({json.dumps(schema)})")
        await self.page.evaluate(f"window.wsda.setDBLabel({json.dumps(Path(db_path).name)})")
        await self.set_status("Database loaded", True)
        console.print(f"  [green]✓[/green] Tables: {list(schema.keys())}")
        return result

    async def _open_sql_file(self, sql_path: str) -> dict:
        console.print(f"  Opening: [cyan]{Path(sql_path).name}[/cyan]")
        result = await self._api("/api/load-sql", {"path": sql_path})
        if not result.get("success"):
            raise RuntimeError(f"SQL load failed: {result.get('error')}")
        await self.page.evaluate(f"""
            window.wsda.renderSQL(
                {json.dumps(result['content'])},
                {json.dumps({s: '' for s in result['sections']})}
            )
        """)
        await self.page.evaluate(
            f"window.wsda.setSQLFilename({json.dumps(Path(sql_path).name)})"
        )
        await self.cursor_to("sql_query_1", 500)
        console.print(f"  [green]✓[/green] Sections: {result['sections']}")
        return result

    async def _scan_schema(self) -> dict:
        """Mouse scans schema panel — learner's eye follows.
        Scans exactly as many rows as actually exist in the current database,
        never more (older lessons had fixed 3-table layouts; this must not
        assume a table count that doesn't match the real schema)."""
        if not self.rehearsal:
            base_x, base_y, row_h = 100, 133, 50
            row_count = max(1, min(self._schema_table_count or 1, 4))
            for i in range(row_count):
                x, y = base_x, base_y + i * row_h
                jx = x + random.uniform(-5, 5)
                jy = y + random.uniform(-4, 4)
                await bezier_move(self.page, jx, jy, 400 if i else 500)
                await asyncio.sleep(0.3 if i else 0.4)
        await self.set_status("Reviewing schema...", True)
        return {}

    async def _expand_sql_pane(self):
        """Collapse results pane so full SQL section is visible."""
        await self.page.evaluate("if(window.expandSQLPane) window.expandSQLPane();")

    async def _collapse_sql_pane(self):
        """Restore results pane after showing results."""
        await self.page.evaluate("if(window.collapseSQLPane) window.collapseSQLPane();")

    async def _highlight_sql_section(self, section: str) -> None:
        console.print(f"  Highlight: [yellow]{section}[/yellow]")
        # Cursor moves to section first
        target = f"sql_{section}"
        await self.cursor_to(target, 400)
        # Activate cursor glow
        await self._cursor_active(True)
        await asyncio.sleep(0.1)
        # Highlight fires
        await self.page.evaluate(f"""
            async () => {{
                await fetch('/api/highlight-section', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ section: {json.dumps(section)} }})
                }});
                window.wsda.highlightSection({json.dumps(section)});
            }}
        """)
        await self._cursor_active(False)

    async def _run_query(self, query_ref: str) -> dict:
        console.print(f"  Running: [cyan]{query_ref}[/cyan]")
        # Cursor moves toward results before query fires
        await self.cursor_to("results_area", 350)
        await self._cursor_active(True)
        await self.set_status(f"Running {query_ref}...", True)
        result = await self._api("/api/run-query", {"query_ref": query_ref})
        if not result.get("success"):
            raise RuntimeError(f"Query failed: {result.get('error')}")
        await self.page.evaluate(f"""
            window.wsda.renderResults(
                {json.dumps(result)},
                {json.dumps(query_ref)}
            )
        """)
        await self._cursor_active(False)
        await self.set_status(f"{result['row_count']} rows", True)
        console.print(f"  [green]✓[/green] {result['row_count']} rows")
        return result

    async def _highlight_result(self) -> None:
        await self.cursor_to("results_top", 300)
        await self.page.evaluate(
            "window.wsda.applyAttention('highlight_result', [], 1.5)"
        )
        await asyncio.sleep(1.5)

    async def _compare_results(self, targets: list[str]) -> None:
        panels = [{"id": t, "label": t.replace("_", " ").title()} for t in targets]
        await self.set_layout("compare", {"panels": panels})
        await asyncio.sleep(0.5)
        # Scan across panels
        if not self.rehearsal:
            await self.cursor_to("compare_panel_1", 500)
            await asyncio.sleep(0.5)
            await self.cursor_to("compare_panel_2", 500)
            await asyncio.sleep(0.5)
            await self.cursor_to("compare_panel_3", 500)
            await asyncio.sleep(0.5)
        await self.page.evaluate(
            f"window.wsda.applyAttention('comparison', {json.dumps(targets)}, 3.0)"
        )
        await asyncio.sleep(3.0)
