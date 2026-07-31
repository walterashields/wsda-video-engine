"""
WSDA v3 -- Browser Controller (Real-Time Recording)
Controls the IDE and injects overlays via JavaScript.
"""

import asyncio
from typing import List
import logging

logger = logging.getLogger("wsda.browser")


class BrowserController:
    def __init__(self, page):
        self.page = page

    async def load_db(self, db_name: str):
        await self.page.evaluate(f"""
            (async () => {{
                if (window.loadDatabase) {{
                    await window.loadDatabase('{db_name}');
                }} else {{
                    const input = document.querySelector('input[type="file"]');
                    if (input) {{
                        const dt = new DataTransfer();
                        dt.items.add(new File([new ArrayBuffer(0)], '{db_name}'));
                        input.files = dt.files;
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
            }})()
        """)
        logger.info(f"Triggered DB load: {db_name}")
        await asyncio.sleep(1.5)

    async def open_schema(self):
        for sel in ['button:has-text("Schema")', '[data-testid="schema-toggle"]', 'text=Schema']:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    logger.info("Opened schema panel")
                    break
            except Exception:
                continue
        await asyncio.sleep(2)

        # Inject schema if panel is empty
        try:
            tables = await self.page.locator(
                '[data-testid="schema-table"], .schema-table, .table-item'
            ).count()
            if tables == 0:
                from schema_fix import get_schema_html
                html = get_schema_html()
                await self.page.evaluate(f"""
                    (() => {{
                        const panel = document.querySelector(
                            '[data-testid="schema-panel"], .schema-panel, aside, .sidebar'
                        );
                        if (panel) panel.innerHTML = `{html}`;
                    }})()
                """)
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def clear_editor(self):
        await self.page.evaluate("""
            (() => {
                const cm = document.querySelector('.CodeMirror');
                if (cm && cm.CodeMirror) { cm.CodeMirror.setValue(''); cm.CodeMirror.refresh(); return; }
                const ta = document.querySelector('textarea');
                if (ta) { ta.value = ''; }
            })()
        """)
        await asyncio.sleep(0.3)

    async def type_query(self, query: str, duration: float):
        """Type query character-by-character over the specified duration."""
        await self.clear_editor()
        if not query:
            return

        chars = list(query)
        delay = duration / len(chars)

        for char in chars:
            safe = char.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
            await self.page.evaluate(f"""
                (() => {{
                    const cm = document.querySelector('.CodeMirror');
                    if (cm && cm.CodeMirror) {{
                        cm.CodeMirror.replaceSelection('{safe}', 'end');
                    }} else {{
                        const ta = document.querySelector('textarea');
                        if (ta) ta.value += '{safe}';
                    }}
                }})()
            """)
            await asyncio.sleep(delay)

    async def run_query(self):
        clicked = False
        for sel in ['button:has-text("Run")', '[data-testid="run-button"]']:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            await self.page.keyboard.press("F5")

        # Wait for results to render
        for i in range(20):
            await asyncio.sleep(0.5)
            try:
                rows = await self.page.locator('tr, .result-row, .ag-row').count()
                if rows > 0:
                    logger.info(f"Query returned {rows} rows")
                    return
            except Exception:
                pass
        logger.warning("Query results not detected")

    async def show_overlay(self, overlay: dict):
        content = overlay["content"].replace("'", "\\'")
        pos_x = overlay["position"][0] * 100
        pos_y = overlay["position"][1] * 100
        style = overlay.get("style", {})

        await self.page.evaluate(f"""
            (() => {{
                const div = document.createElement('div');
                div.className = 'wsda-overlay';
                div.textContent = '{content}';
                div.style.cssText = `
                    position: fixed;
                    left: {pos_x}%;
                    top: {pos_y}%;
                    transform: translate(-50%, -50%);
                    background: {style.get('bg_color', 'rgba(0,0,0,0.85)')};
                    color: {style.get('color', '#ffffff')};
                    font-size: {style.get('font_size', 24)}px;
                    padding: {style.get('padding', 24)}px;
                    border-radius: 16px;
                    z-index: 999999;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    white-space: nowrap;
                    pointer-events: none;
                    line-height: 1.4;
                `;
                document.body.appendChild(div);
            }})()
        """)

    async def show_title_card(self, scene: dict):
        overlays = scene.get("overlays", [])
        html_parts = []
        for ov in overlays:
            content = ov["content"].replace("'", "\\'")
            style = ov.get("style", {})
            html_parts.append(
                f'<div style="color:{style.get("color", "#fff")};'
                f'font-size:{style.get("font_size", 24)}px;'
                f'margin-bottom:16px;'
                f'background:{style.get("bg_color", "transparent")};'
                f'padding:{style.get("padding", 0)}px;'
                f'border-radius:12px;'
                f'line-height:1.3;">'
                f'{content}</div>'
            )

        bg = "#0B0C10" if scene.get("bg_fade_opacity", 0) >= 0.95 else "rgba(11,12,16,0.92)"

        await self.page.evaluate(f"""
            (() => {{
                const card = document.createElement('div');
                card.className = 'wsda-overlay';
                card.style.cssText = `
                    position: fixed;
                    inset: 0;
                    background: {bg};
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    z-index: 999999;
                    pointer-events: none;
                    text-align: center;
                `;
                card.innerHTML = `{' '.join(html_parts)}`;
                document.body.appendChild(card);
            }})()
        """)

    async def clear_overlays(self):
        await self.page.evaluate("""
            document.querySelectorAll('.wsda-overlay').forEach(e => e.remove());
        """)
