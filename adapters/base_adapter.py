"""
WSDA Video Engine — Base Adapter Interface

Every application adapter MUST implement this interface.
The timeline runner only calls methods defined here.
This guarantees that production cards are interface-agnostic —
a card written for the SQL viewer works identically when
a PowerBIAdapter or ExcelAdapter is substituted.

Implementing a new adapter:
    class PowerBIAdapter(BaseAdapter):
        async def navigate(self): ...
        async def focus_element(self, target: str): ...
        # etc.

The adapter handles:
  - Application-specific interaction
  - Mouse movement and cursor highlighting
  - Screen state management (what is visible)
  - Pause timing appropriate to the interface

The adapter does NOT handle:
  - Timeline scheduling (runner's job)
  - Audio synchronization (aligner's job)
  - Recording (run.py's job)
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """
    Interface contract for all WSDA application adapters.
    
    Three-phase execution model:
        approach(target)  — move cursor to target before action
        focus(target)     — highlight/emphasize element
        action(...)       — execute the instructional event
    
    Screen state model:
        clear(elements)   — remove stale content before new concept
        verify_state()    — confirm screen matches expected state
    """

    # ── Lifecycle ──────────────────────────────────────────────

    @abstractmethod
    async def navigate(self) -> None:
        """Initialize the application and load the interface."""

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up before closing."""

    # ── Three-phase execution ──────────────────────────────────

    @abstractmethod
    async def approach(self, target: str, lead_time_s: float = 0.5) -> None:
        """
        Phase 1: Move cursor toward target before the event fires.
        Called automatically by runner before focus/action.
        lead_time_s: how long before next phase this should complete.
        """

    @abstractmethod
    async def focus(self, target: str, context: dict) -> None:
        """
        Phase 2: Draw visual attention to target.
        Fires as narration begins. Cursor is already positioned.
        context: event-specific parameters (section name, query ref, etc.)
        """

    @abstractmethod
    async def action(self, event_type: str, params: dict) -> dict:
        """
        Phase 3: Execute the instructional event.
        Fires after narration ends + offset.
        Returns result dict (rows returned, state changes, etc.)
        """

    # ── Screen state management ────────────────────────────────

    @abstractmethod
    async def clear(self, elements: list[str]) -> None:
        """
        Clear named screen elements before a new concept begins.
        elements: ["result", "highlight", "comparison", "all"]
        This prevents stale content from appearing during new narration.
        """

    @abstractmethod
    async def verify_state(self, expected: dict) -> tuple[bool, str]:
        """
        Verify screen matches expected state before event fires.
        Returns (passed, description).
        Runner can log or halt on failure.
        """

    # ── Cursor and attention ───────────────────────────────────

    @abstractmethod
    async def cursor_to(self, target: str, duration_ms: int = 500) -> None:
        """Move cursor to named semantic target with natural motion."""

    @abstractmethod
    async def highlight_cursor(self, active: bool) -> None:
        """Enable/disable cursor highlight glow for recording visibility."""

    # ── Layout ────────────────────────────────────────────────

    @abstractmethod
    async def set_layout(self, mode: str, options: dict | None = None) -> None:
        """Switch interface layout mode."""

    # ── Status ────────────────────────────────────────────────

    @abstractmethod
    async def set_status(self, text: str, active: bool = True) -> None:
        """Update status indicator in the interface."""

    # ── Utility ───────────────────────────────────────────────

    async def pause(self, seconds: float) -> None:
        """Natural pause. Implemented here so all adapters get it free."""
        import asyncio
        if seconds > 0:
            await asyncio.sleep(seconds)
