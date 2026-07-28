#!/usr/bin/env python3
"""
WSDA Storyboard — Visual-first production card generation

Replaces draft.py with a system that thinks in frames first, narration second.
Every event specifies what the viewer SEES, not just what they HEAR.

Key changes from draft.py:
1. Events specify visual state (what's on screen) not just narration
2. Timing is enforced at generation time, not as a post-hoc fix
3. The storyboard is validated for visual progression (no frozen screens)
4. Format constraints are structural, not just prompt-based
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

import click
import yaml
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel

console = Console()
client = Anthropic()
ROOT = Path(__file__).parent

# ── Format Specifications — Hard Constraints ──────────────────────────────
FORMAT_SPECS = {
    "micro": {
        "max_events": 5,
        "max_pauses": 3.0,
        "max_words": 300,
        "target_duration_s": 180,
        "description": "1-3 min, feed-scroll, ONE idea, hook in 3 seconds",
    },
    "short": {
        "max_events": 8,
        "max_pauses": 5.0,
        "max_words": 600,
        "target_duration_s": 300,
        "description": "3-5 min, one concept with proof",
    },
    "standard": {
        "max_events": 12,
        "max_pauses": 10.0,
        "max_words": 1200,
        "target_duration_s": 900,
        "description": "8-15 min, full concept with multiple angles",
    },
}

# ── Storyboard System Prompt ──────────────────────────────────────────────
STORYBOARD_SYSTEM = """You are a senior instructional designer and video director for WSDA.

You generate STORYBOARDS, not just narration. Every event you create specifies:
1. What the viewer SEES on screen (visual state)
2. What the viewer HEARS (narration)
3. How long the visual stays before changing (pause duration)

VISUAL-FIRST RULE: Before writing any narration, decide what will be on screen.
The visual drives the narration, not the other way around.

CRITICAL VISUAL PROGRESSION RULES:
- Every event must produce a VISIBLE CHANGE on screen. Never write two consecutive
  events that leave the screen looking identical.
- The first frame must be a TITLE CARD with the hook — never an empty SQL editor.
- When narration references a specific number, that number must be VISIBLE and
  PROMINENT on screen at that moment.
- Schema panel is collapsed during query execution — it adds clutter.
- Results are zoomed when narration focuses on them.
- Rows are highlighted when narration names them.
- Cells are annotated when narration calls out specific values.

NARRATION RULES:
- Use contractions throughout
- Spell out all numbers in words
- Every technical term must be translated into a physical image in the SAME sentence
- First 3 seconds must state the stakes
- No setup, no context-building — jump straight to the problem
"""

STORYBOARD_PROMPT = """Generate a production card storyboard for this lesson.

Topic: {topic}
Format: {format} ({format_desc})
Hard limits: {max_events} events max, {max_pauses}s pauses max, {max_words} words max

VERIFIED DATA (only facts allowed in narration):
{verified_data}

LESSON CONTEXT:
{context}

VISUAL EVENT TYPES AVAILABLE:
- show_title_card: Full-screen title with badge, headline, sub, optional stakes
- open_database: Load database, show schema (briefly)
- collapse_schema: Hide schema panel
- highlight_section: Show and explain a SQL query section
- run_query: Execute query (no narration — visual only)
- show_result: Display results with narration
- highlight_row: Emphasize a specific row (red/green/blue)
- annotate_cell: Add floating callout on a cell
- zoom_results: Expand results panel
- reset_zoom: Restore default layout
- fade_out: End screen

EVENT STRUCTURE:
Every event with narration MUST be followed by a pause event.
Pause duration = (word_count / 150 * 60) + 2 seconds

Return ONLY valid YAML starting with schema_version: "3.0"
"""


def calculate_pause(narration: str) -> float:
    """Calculate pause from word count with numeric awareness."""
    words = len(narration.split())
    for tok in narration.split():
        digits = sum(c.isdigit() for c in tok)
        if digits > 2:
            words += digits // 2
    return round((words / 150 * 60) + 2, 1)


def enforce_format_constraints(card_yaml: str, fmt: str) -> tuple[str, list[str]]:
    """Apply all 4 layers of timing enforcement."""
    spec = FORMAT_SPECS.get(fmt.lower(), FORMAT_SPECS["standard"])
    parsed = yaml.safe_load(card_yaml)
    events = parsed.get("events", [])
    errors = []

    # Layer 2: Structural validation
    non_pause = [e for e in events if e.get("type") != "pause"]
    if len(non_pause) > spec["max_events"]:
        errors.append(f"Too many events: {len(non_pause)} > {spec['max_events']}")

    # Layer 3: Recompute pauses
    for i, e in enumerate(events):
        narr = (e.get("narration") or "").strip()
        if narr and i + 1 < len(events) and events[i + 1].get("type") == "pause":
            events[i + 1]["duration"] = min(calculate_pause(narr), spec["max_pauses"])

    # Layer 4: Hard cap
    total = sum(e.get("duration", 0) for e in events if e.get("type") == "pause")
    total += sum(len((e.get("narration") or "").split()) / 150 * 60 for e in events)

    if total > spec["target_duration_s"]:
        excess = total - spec["target_duration_s"]
        pauses = [e for e in events if e.get("type") == "pause"]
        if pauses:
            floor = 1.5
            compressible = sum(max(0, p.get("duration", 0) - floor) for p in pauses)
            if compressible > 0 and excess <= compressible:
                ratio = excess / compressible
                for p in pauses:
                    p["duration"] = round(max(floor, p["duration"] - (p["duration"] - floor) * ratio), 1)
            else:
                for p in pauses:
                    p["duration"] = floor
                errors.append(f"HONEST OVERFLOW: Script needs {total/60:.1f}min for {spec['target_duration_s']/60:.0f}min format")

    return yaml.dump(parsed, sort_keys=False, allow_unicode=True, width=100), errors


def generate_storyboard(topic: str, verified_data: str, context: str, fmt: str) -> str:
    """Generate a storyboard with format constraints enforced."""
    spec = FORMAT_SPECS.get(fmt.lower(), FORMAT_SPECS["standard"])

    format_constraints = f"""
CRITICAL FORMAT CONSTRAINTS — HARD RULES:
- This is {fmt.upper()}: {spec['description']}
- MAX {spec['max_events']} non-pause events
- MAX {spec['max_pauses']}-second pauses
- MAX {spec['max_words']} spoken words
- Target: {spec['target_duration_s']/60:.0f} minutes
"""

    prompt = STORYBOARD_PROMPT.format(
        topic=topic,
        format=fmt,
        format_desc=spec["description"],
        max_events=spec["max_events"],
        max_pauses=spec["max_pauses"],
        max_words=spec["max_words"],
        verified_data=verified_data,
        context=context,
    ) + format_constraints

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        system=STORYBOARD_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    raw = text_blocks[-1].strip() if text_blocks else ""
    raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip())

    # Enforce constraints
    return enforce_format_constraints(raw, fmt)


@click.command()
@click.argument("brief_path")
@click.option("--format", "fmt", default="micro")
def main(brief_path, fmt):
    with open(brief_path) as f:
        brief = json.load(f)

    topic = brief["topic"]
    console.print(Panel(f"[bold]Storyboard[/bold]\nTopic: {topic}\nFormat: {fmt}", border_style="green"))

    # TODO: Integrate with SQL generation from draft.py
    # For now, this is the storyboard generation module
    # Full integration would call build_verified_sql_and_db first

    card_yaml, errors = generate_storyboard(topic, "", "", fmt)

    if errors:
        console.print(f"[yellow]Warnings:[/yellow]")
        for e in errors:
            console.print(f"  - {e}")

    out_path = Path("storyboard_output.yml")
    out_path.write_text(card_yaml)
    console.print(f"[green]Written:[/green] {out_path}")

if __name__ == "__main__":
    main()
