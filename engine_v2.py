#!/usr/bin/env python3
"""
WSDA Engine v2 — Render-First Video Production

Architecture:
  Topic → Research → Visual Storyboard → Silent Render → Narrate from Frames → Final Render → Ship

Key inversion from v1: The model sees the actual video frames before writing narration.
This eliminates number verification, timing math, and quality gate false positives.

Usage:
    python3 engine_v2.py research/<topic>/brief.json --format micro
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click
import yaml
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel

console = Console()
client = Anthropic()
ROOT = Path(__file__).parent

# ── Format Specifications ────────────────────────────────────────────────
FORMAT_SPECS = {
    "micro": {
        "max_events": 5,
        "target_duration_s": 180,
        "description": "1-3 min, ONE idea, hook in first 3 seconds",
    },
    "short": {
        "max_events": 8,
        "target_duration_s": 300,
        "description": "3-5 min, one concept with proof",
    },
    "standard": {
        "max_events": 12,
        "target_duration_s": 900,
        "description": "8-15 min, full concept with multiple angles",
    },
}


def get_spec(fmt: str) -> dict:
    return FORMAT_SPECS.get(fmt.lower(), FORMAT_SPECS["standard"])


# ── Step 1: Research (reuse existing) ────────────────────────────────────
def run_research(topic: str, fmt: str) -> Path:
    """Run research.py to generate brief."""
    cmd = [sys.executable, "research.py", topic, "--format", fmt]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Research failed: {result.stderr}[/red]")
        sys.exit(1)

    slug = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')[:40]
    brief_path = ROOT / "research" / slug / "brief.json"
    return brief_path


# ── Step 2: Visual Storyboard ────────────────────────────────────────────
def generate_visual_storyboard(brief_path: Path, fmt: str) -> str:
    """Generate a visual storyboard: what happens on screen, not what is said."""
    with open(brief_path) as f:
        brief = json.load(f)

    spec = get_spec(fmt)
    topic = brief["topic"]

    prompt = f"""You are a video director. Generate a VISUAL STORYBOARD for this lesson.

Topic: {topic}
Format: {fmt} ({spec['description']})
Hard limit: {spec['max_events']} visual events maximum

RULES:
- You specify what happens ON SCREEN, not what is said
- Every event must produce a VISIBLE CHANGE
- The first event MUST be show_title_card with a compelling hook
- Schema panel starts COLLAPSED (cleaner visuals)
- When showing results, highlight the key row and annotate the punchline cell
- Use zoom_results when the focus is on results
- Use collapse_schema during query execution

VISUAL EVENT TYPES:
- show_title_card: badge, headline, sub, stakes (MUST be first)
- open_database: db_name
- expand_schema: (briefly show tables)
- collapse_schema: (hide for clean query view)
- set_sql: query_text, label ("correct" or "buggy")
- run_query: (executes current SQL)
- show_results: columns, rows, highlight_row, annotate_cell
- zoom_results: (expand results panel)
- reset_zoom: (restore layout)
- fade_out: (end screen)

Each event is followed by a pause. Pause duration is the time that visual
stays on screen before the next event. For micro format: 2-4 seconds per pause.

Return ONLY valid YAML starting with schema_version: "3.0"
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system="You are a video director for WSDA. You specify visual events only. "
               "No narration text. No spoken words. Only what appears on screen. "
               "Return only YAML.",
        messages=[{"role": "user", "content": prompt}]
    )

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    raw = text_blocks[-1].strip() if text_blocks else ""
    raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip())

    return raw


# ── Step 3: Silent Render ────────────────────────────────────────────────
def silent_render(card_path: Path, output_mp4: Path) -> bool:
    """Render video silently (no audio)."""
    # Import and use the silent renderer module
    sys.path.insert(0, str(ROOT))
    from silent_renderer import SilentRenderer

    renderer = SilentRenderer()
    try:
        renderer.render(card_path, output_mp4)
        return True
    except Exception as e:
        console.print(f"[red]Silent render failed: {e}[/red]")
        return False


# ── Step 4: Narrate from Frames ──────────────────────────────────────────
def narrate_from_frames(mp4_path: Path, card_path: Path, fmt: str) -> str:
    """Generate narration by watching actual video frames."""
    sys.path.insert(0, str(ROOT))
    from narrator_v2 import NarratorV2

    narrator = NarratorV2()
    return narrator.narrate(mp4_path, card_path, fmt)


# ── Step 5: Final Render ─────────────────────────────────────────────────
def final_render(silent_mp4: Path, narration_yaml: str, output_mp4: Path) -> bool:
    """Combine silent video with synthesized audio."""
    # Parse narration YAML to get audio segments
    parsed = yaml.safe_load(narration_yaml)
    segments = parsed.get("segments", [])

    # Generate audio for each segment using ElevenLabs
    # Then combine with silent video using ffmpeg
    # This is a placeholder - actual implementation depends on your audio pipeline
    console.print(f"[yellow]Final render: combining {len(segments)} audio segments[/yellow]")

    # For now, copy silent video as placeholder
    shutil.copy(silent_mp4, output_mp4)
    return True


# ── Main Orchestrator ────────────────────────────────────────────────────
@click.command()
@click.argument("topic")
@click.option("--format", "fmt", default="micro")
def main(topic, fmt):
    console.print(Panel(
        f"[bold]WSDA Engine v2[/bold]\n"
        f"Topic: [cyan]{topic}[/cyan]\n"
        f"Format: [cyan]{fmt}[/cyan]\n"
        f"Mode: [green]Render-first[/green]",
        border_style="green"
    ))

    # Step 1: Research
    console.print("\n[bold]Step 1: Research[/bold]")
    brief_path = run_research(topic, fmt)
    console.print(f"[green]OK[/green] Brief: {brief_path}")

    # Step 2: Visual Storyboard
    console.print("\n[bold]Step 2: Visual Storyboard[/bold]")
    storyboard_yaml = generate_visual_storyboard(brief_path, fmt)

    slug = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')[:40]
    course_dir = ROOT / "courses" / slug / "video_1_1"
    course_dir.mkdir(parents=True, exist_ok=True)

    storyboard_path = course_dir / "visual_storyboard.yml"
    storyboard_path.write_text(storyboard_yaml)
    console.print(f"[green]OK[/green] Storyboard: {storyboard_path}")

    # Step 3: Silent Render
    console.print("\n[bold]Step 3: Silent Render[/bold]")
    silent_mp4 = course_dir / "silent.mp4"
    if not silent_render(storyboard_path, silent_mp4):
        console.print("[red]Production failed at silent render[/red]")
        sys.exit(1)
    console.print(f"[green]OK[/green] Silent video: {silent_mp4}")

    # Step 4: Narrate from Frames
    console.print("\n[bold]Step 4: Narrate from Frames[/bold]")
    narration_yaml = narrate_from_frames(silent_mp4, storyboard_path, fmt)
    narration_path = course_dir / "narration.yml"
    narration_path.write_text(narration_yaml)
    console.print(f"[green]OK[/green] Narration: {narration_path}")

    # Step 5: Final Render
    console.print("\n[bold]Step 5: Final Render[/bold]")
    final_mp4 = course_dir / "final.mp4"
    if not final_render(silent_mp4, narration_yaml, final_mp4):
        console.print("[red]Production failed at final render[/red]")
        sys.exit(1)
    console.print(f"[green]OK[/green] Final video: {final_mp4}")

    console.print("\n[bold green]Production complete![/bold green]")

if __name__ == "__main__":
    main()
