"""
WSDA Chat Demo Adapter

Controls the ChatGPT demo interface (web/demo/chat.html) via Playwright.
Used for AI course lessons that demonstrate ChatGPT workflows.

Supported event types:
  open_chat       — load the demo interface
  new_conversation — start a fresh chat with optional title
  type_message    — type a user prompt character by character
  send_message    — submit the current input
  stream_response — display a pre-written AI response with streaming effect
  highlight_region — highlight a named region with gold border
  clear_highlight  — remove highlight
  set_input       — set input text directly (for showing pre-written prompts)
"""

import asyncio
import json
from pathlib import Path

from rich.console import Console

console = Console()


class ChatDemoAdapter:
    """Controls the ChatGPT demo page for lesson recording."""

    def __init__(self, page, base_url: str = "http://localhost:5050"):
        self.page = page
        self.demo_url = f"{base_url}/demo/chat"
        self._loaded = False

    async def navigate(self):
        """Called by runner on startup — load the demo page."""
        # Capture JS errors
        errors = []
        self.page.on("pageerror", lambda e: errors.append(str(e)))

        await self.page.goto(self.demo_url, wait_until="load")
        await asyncio.sleep(2.0)

        if errors:
            console.print(f"  [red]JS errors: {errors}[/red]")

        ready = await self.page.evaluate("typeof window.wsda_chat !== 'undefined'")
        if ready:
            console.print("  [green]✓[/green] Chat demo ready")
        else:
            console.print("  [red]⚠ wsda_chat undefined — page may have JS error[/red]")
            if errors:
                raise RuntimeError(f"Chat demo JS error: {errors[0]}")

    async def action(self, event_type: str, params: dict) -> dict:
        """Route events — matches SQLViewerAdapter interface."""
        return await self.execute(event_type, params)

    async def approach(self, target: str, lead: float = 0.0):
        """No-op for chat demo — no cursor ring needed."""
        pass

    async def focus(self, target: str, params: dict):
        """No-op for chat demo."""
        pass

    async def clear(self, clears: list):
        """No-op for chat demo."""
        pass

    async def execute(self, event_type: str, params: dict) -> dict:
        """Dispatch an event to the appropriate handler."""

        if event_type == "open_chat":
            return await self._open_chat(params)

        elif event_type == "new_conversation":
            title = params.get("title", "")
            await self.page.evaluate(
                f"window.wsda_chat.newConversation({json.dumps(title)})"
            )
            await asyncio.sleep(0.5)
            return {"success": True}

        elif event_type == "show_message":
            # Display a user message instantly — no typing animation
            text      = params.get("text", "")
            region_id = params.get("region", "")
            await self.page.evaluate(
                f"window.wsda_chat.showMessageInstant({json.dumps(text)}, {json.dumps(region_id)})"
            )
            await asyncio.sleep(0.5)
            return {"success": True}

        elif event_type == "show_response":
            # Display a full AI response instantly — no streaming
            text      = params.get("text", "")
            region_id = params.get("region", "")
            await self.page.evaluate(
                f"window.wsda_chat.showResponseInstant({json.dumps(text)}, {json.dumps(region_id)})"
            )
            await asyncio.sleep(0.8)
            return {"success": True}

        elif event_type == "type_message":
            text = params.get("text", "")
            wpm  = params.get("wpm", 60)
            await self.page.evaluate(
                f"window.wsda_chat.typeUserMessage({json.dumps(text)}, {wpm})"
            )
            # Wait for typing to complete
            char_delay = 60000 / (wpm * 5) / 1000
            await asyncio.sleep(len(text) * char_delay * 1.2)
            return {"success": True}

        elif event_type == "send_message":
            await self.page.evaluate("window.wsda_chat.submitMessage()")
            await asyncio.sleep(0.8)
            return {"success": True}

        elif event_type == "stream_response":
            text = params.get("text", "")
            wpm  = params.get("wpm", 180)
            word_count = len(text.split())
            stream_seconds = (word_count / wpm) * 60 * 1.4
            await self.page.evaluate(
                f"window.wsda_chat.streamResponse({json.dumps(text)}, {wpm})"
            )
            await asyncio.sleep(stream_seconds)
            return {"success": True}

        elif event_type == "highlight_region":
            region  = params.get("region", "")
            callout = params.get("callout", "")
            await self.page.evaluate(
                f"window.wsda_chat.highlight({json.dumps(region)}, {json.dumps(callout)})"
            )
            await asyncio.sleep(0.4)
            return {"success": True}

        elif event_type == "clear_highlight":
            await self.page.evaluate("window.wsda_chat.clearHighlight()")
            await asyncio.sleep(0.2)
            return {"success": True}

        elif event_type == "set_input":
            text = params.get("text", "")
            await self.page.evaluate(
                f"window.wsda_chat.setInputText({json.dumps(text)})"
            )
            await asyncio.sleep(0.3)
            return {"success": True}

        elif event_type in ("pause", "show_result", "fade_out"):
            # These are handled by the runner directly — adapter just acknowledges
            if event_type == "fade_out":
                await self.page.evaluate(
                    "document.body.style.transition='opacity 1s';"
                    "document.body.style.opacity='0';"
                )
                await asyncio.sleep(1.0)
            return {"success": True}

        else:
            console.print(f"  [yellow]ChatDemoAdapter: unknown event type '{event_type}'[/yellow]")
            return {"success": False, "error": f"Unknown event: {event_type}"}

    async def _open_chat(self, params: dict) -> dict:
        user_name = params.get("user_name", "Walter Shields")
        initials  = params.get("initials", "WS")

        await self.page.goto(self.demo_url)
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.5)

        await self.page.evaluate(
            f"window.wsda_chat.setUser({json.dumps(user_name)}, {json.dumps(initials)})"
        )
        self._loaded = True
        console.print(f"  [green]✓[/green] Chat demo loaded")
        return {"success": True}
