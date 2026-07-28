#!/usr/bin/env python3
"""
WSDA Storyboard v2 — Visual-first production card generation

Generates storyboards that specify what happens ON SCREEN, not what is said.
Narration is added later by watching the actual rendered frames.

This eliminates:
- Number verification (model sees actual numbers on screen)
- Timing math (system measures actual video duration)
- Quality gate false positives (model narrates what it sees)
- Frozen screen bugs (each event produces visible change)
"""

import json
import re
import sqlite3
from pathlib import Path

import yaml
from anthropic import Anthropic
from rich.console import Console

console = Console()
client = Anthropic()

# ── Format Specifications ────────────────────────────────────────────────
FORMAT_SPECS = {
    "micro": {
        "max_events": 5,
        "target_duration_s": 180,
        "pause_range": (2.0, 4.0),
    },
    "short": {
        "max_events": 8,
        "target_duration_s": 300,
        "pause_range": (3.0, 6.0),
    },
    "standard": {
        "max_events": 12,
        "target_duration_s": 900,
        "pause_range": (4.0, 10.0),
    },
}


def get_spec(fmt: str) -> dict:
    return FORMAT_SPECS.get(fmt.lower(), FORMAT_SPECS["standard"])


# ── Visual Storyboard Prompt ─────────────────────────────────────────────
VISUAL_STORYBOARD_SYSTEM = """You are a senior video director for WSDA, a company that produces
premium educational video content sold to individuals and organizations.

Your job is to create VISUAL STORYBOARDS — detailed specifications of what
appears on screen at every moment of the video. You do NOT write narration.
You specify visuals only.

CRITICAL RULES:
1. EVERY event must produce a VISIBLE CHANGE on screen. Never write two
   consecutive events that leave the screen looking identical.
2. The FIRST event MUST be show_title_card with a compelling visual hook.
3. Schema panel starts COLLAPSED and only expands when needed.
4. When showing query results, always highlight the key row and annotate
   the punchline cell with a floating callout.
5. Use zoom_results when the focus shifts to results.
6. Use collapse_schema during query execution for clean visuals.
7. Query blocks are color-coded: green for correct, red for buggy.
8. All text must be readable on a phone held at normal distance.

VISUAL EVENT TYPES:
- show_title_card: Full-screen title overlay
  params: badge (category label), headline (large text), sub (subtitle),
          stakes (optional consequence callout)
- open_database: Load database, show name in header
  params: db_name
- expand_schema: Show schema sidebar with tables
- collapse_schema: Hide schema sidebar
- activate_table: Expand a specific table to show columns
  params: table_name
- set_sql: Display SQL query in editor
  params: query_text, label ("correct" or "buggy" for color coding)
- highlight_section: Scroll to and emphasize a section of SQL
  params: section_name
- run_query: Execute current SQL (visual: button press, status update)
- show_results: Display query results table
  params: columns (list), rows (list of lists),
          highlight_row (index), annotate_cell (row, col, text)
- zoom_results: Expand results panel to 65% height
- reset_zoom: Restore default panel heights
- highlight_row: Emphasize a specific row
  params: row_index, color ("blue", "red", "green")
- annotate_cell: Add floating callout on a cell
  params: row_index, col_index, text
- clear_highlights: Remove all row highlighting
- clear_annotations: Remove all cell callouts
- fade_out: Fade screen to black

PAUSE DURATIONS:
Each event is followed by a pause. The pause is how long that visual stays
on screen before the next event changes it.
- Micro format: 2-4 seconds
- Short format: 3-6 seconds
- Standard format: 4-10 seconds

The pause duration is NOT for narration — it's for the viewer to process
what they see. Narration timing is handled separately after rendering.
"""


def generate_storyboard(topic: str, brief: dict, sql_content: str,
                        verified_data: str, fmt: str) -> str:
    """Generate a visual storyboard with format constraints."""
    spec = get_spec(fmt)

    prompt = f"""Create a visual storyboard for this SQL lesson.

Topic: {topic}
Format: {fmt}
Max events: {spec['max_events']}
Pause range: {spec['pause_range'][0]}-{spec['pause_range'][1]} seconds

VERIFIED DATA (use these exact values in the storyboard):
{verified_data}

SQL QUERIES:
{sql_content}

REQUIREMENTS:
1. First event MUST be show_title_card with a compelling hook
2. Show the schema briefly, then collapse it for query execution
3. Display the SQL query with color coding (green=correct, red=buggy)
4. Execute the query and show results
5. Highlight the key row and annotate the punchline cell
6. End with fade_out

Return ONLY valid YAML starting with schema_version: "3.0"
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        system=VISUAL_STORYBOARD_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    raw = text_blocks[-1].strip() if text_blocks else ""
    raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip())

    # Validate structure
    parsed = yaml.safe_load(raw)
    events = parsed.get("events", [])
    non_pause = [e for e in events if e.get("type") != "pause"]

    if len(non_pause) > spec["max_events"]:
        console.print(f"[yellow]Warning: {len(non_pause)} events exceeds {spec['max_events']} max for {fmt}[/yellow]")

    # Ensure first event is show_title_card
    if non_pause and non_pause[0].get("type") != "show_title_card":
        console.print("[yellow]Warning: First event should be show_title_card[/yellow]")

    return raw


def build_verified_sql_and_db(topic: str) -> tuple[str, str, str]:
    """Build SQL, database, and verified data summary."""
    # This is a simplified version — in production, reuse the logic from draft.py
    # For now, return placeholder data
    return (
        "-- SQL queries would be generated here\nSELECT * FROM orders;",
        "-- Database would be built here",
        "orders: 100 rows, avg_price: 29.99, max_price: 349.99"
    )


if __name__ == "__main__":
    # Test mode
    topic = "Why your GROUP BY is silently wrong"
    brief = {"topic": topic}
    sql_content = "SELECT customer_id, product_name FROM orders GROUP BY customer_id;"
    verified_data = "orders: 100 rows, avg_price: 29.99, max_price: 349.99"

    storyboard = generate_storyboard(topic, brief, sql_content, verified_data, "micro")
    print(storyboard)
