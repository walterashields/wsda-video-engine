#!/usr/bin/env python3
"""
WSDA Video Engine — Rehearsal Mode
Dry-runs a lesson at 2x speed with verbose logging.
No recording. No MP4.
Use this to validate your production card before committing to a full record.

Usage:
    python rehearse.py courses/novabridge/video_1_1/production_card.yml
    python rehearse.py courses/novabridge/video_1_1/production_card.yml --resume e08
    python rehearse.py courses/novabridge/video_1_1/production_card.yml --speed 3
"""

import asyncio
import json
import sys
import yaml
from pathlib import Path

import click
from rich.console import Console

# Make sure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

from engine.compiler import compile
from engine.timeline_runner import TimelineRunner

console = Console()


@click.command()
@click.argument("card_path")
@click.option("--resume", default=None, help="Resume from event ID (e.g. e08)")
@click.option("--speed", default=2.0, type=float, help="Playback speed multiplier (default: 2.0)")
@click.option("--no-compile", is_flag=True, help="Skip recompile, use existing timeline JSON")
def rehearse(card_path: str, resume: str | None, speed: float, no_compile: bool):
    """Rehearse a lesson without recording."""

    card_path = Path(card_path)
    timeline_path = card_path.parent / "lesson_timeline.json"

    # Load settings
    settings_path = Path(__file__).parent / "config" / "settings.yml"
    settings = {}
    if settings_path.exists():
        with open(settings_path) as f:
            settings = yaml.safe_load(f)

    # Compile (or load existing)
    if no_compile and timeline_path.exists():
        console.print(f"[dim]Loading existing timeline: {timeline_path}[/dim]")
        from engine.schemas import LessonTimeline
        with open(timeline_path) as f:
            timeline = LessonTimeline(**json.load(f))
    else:
        timeline = compile(card_path)

    # Run rehearsal
    runner = TimelineRunner(
        timeline=timeline,
        rehearsal=True,
        speed=speed,
        resume_from=resume,
        settings=settings,
    )

    async def go():
        audit = await runner.run()

        # Write audit log
        audit_path = card_path.parent.parent.parent.parent / "output" / f"{timeline.lesson_id}_rehearsal_{audit.run_started[:10]}.json"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_path, "w") as f:
            json.dump(audit.model_dump(), f, indent=2)
        console.print(f"\n[dim]Audit log: {audit_path}[/dim]")

    asyncio.run(go())


if __name__ == "__main__":
    rehearse()
