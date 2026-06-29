"""
WSDA Video Engine — Timeline Compiler v3

Converts production_card.yml → lesson_timeline.json

v3 model:
- Events carry clears[] for screen state management
- Estimated times based on narration word count + transition type
- Output is structural skeleton — aligner provides actual timing
"""

import json
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table

from engine.schemas import (
    ProductionCard, LessonTimeline, TimelineEvent,
    EVENT_ACTION_OFFSET, TRANSITION_SILENCE, EVENT_DEFAULT_TRANSITION,
)

console = Console()

WORDS_PER_SECOND = 2.4  # comfortable instructional pace


def estimate_duration(text: str) -> float:
    return len(text.strip().split()) / WORDS_PER_SECOND


def resolve_asset(path: str, card_dir: Path) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else (card_dir / p).resolve())


def compile(card_path: str | Path, output_path: str | Path | None = None) -> LessonTimeline:
    card_path = Path(card_path).resolve()
    card_dir = card_path.parent

    console.print(f"\n[bold green]WSDA Compiler v3[/bold green]")
    console.print(f"Source: [cyan]{card_path}[/cyan]\n")

    with open(card_path) as f:
        raw = yaml.safe_load(f)

    try:
        card = ProductionCard(**raw)
    except Exception as e:
        console.print(f"[red]Validation failed:[/red] {e}")
        raise

    console.print(f"[green]✓[/green] [bold]{card.title}[/bold]  ({len(card.events)} events)")

    compiled = []
    cursor_s = 0.0

    for event in card.events:
        params = {}
        if event.asset:
            params["asset"] = resolve_asset(event.asset, card_dir)
        if event.section:
            params["section"] = event.section
        if event.query_ref:
            params["query_ref"] = event.query_ref
        if event.targets:
            params["targets"] = event.targets
        if event.duration is not None:
            params["duration"] = event.duration

        # Narration duration estimate
        narr_s = estimate_duration(event.narration) if event.narration else 0.0

        # Action fires after narration + system offset
        action_offset = EVENT_ACTION_OFFSET.get(event.type, 0.4) + event.offset_override
        action_time_s = cursor_s + narr_s + action_offset

        compiled.append(TimelineEvent(
            id=event.id,
            time_offset_ms=int(action_time_s * 1000),
            type=event.type,
            target=event.target,
            params=params,
            narration=event.narration.strip() if event.narration else None,
            transition=event.transition,
            clears=event.clears,
        ))

        # Advance cursor past narration + silence gap
        silence_ms = TRANSITION_SILENCE.get(event.transition, 650)
        cursor_s = action_time_s + silence_ms / 1000

    total_ms = int(max(e.time_offset_ms for e in compiled) + 5000)

    timeline = LessonTimeline(
        lesson_id=card.lesson_id,
        title=card.title,
        course=card.course,
        compiled_from=str(card_path),
        total_duration_ms=total_ms,
        events=compiled,
    )

    if output_path is None:
        output_path = card_dir / "lesson_timeline.json"

    with open(output_path, "w") as f:
        json.dump(timeline.model_dump(), f, indent=2)

    console.print(f"[green]✓[/green] Timeline: [cyan]{output_path}[/cyan]")

    table = Table(header_style="bold cyan", show_header=True)
    table.add_column("ID", style="dim")
    table.add_column("Est. action time")
    table.add_column("Type")
    table.add_column("Transition")
    table.add_column("Clears")
    table.add_column("Narration")

    for e in compiled:
        s = e.time_offset_ms / 1000
        mm, ss = divmod(s, 60)
        narr = (e.narration or "")[:40] + ("…" if e.narration and len(e.narration) > 40 else "")
        table.add_row(
            e.id, f"{int(mm):02d}:{ss:04.1f}",
            e.type, e.transition,
            ", ".join(e.clears) or "—",
            narr,
        )

    console.print(table)
    console.print(f"\n[bold]Estimated duration:[/bold] {total_ms/1000:.1f}s")
    console.print(f"[dim]Run narration/align.py to lock to actual audio[/dim]")

    return timeline


if __name__ == "__main__":
    import sys
    card = sys.argv[1] if len(sys.argv) > 1 else "courses/novabridge/video_1_1/production_card.yml"
    compile(card)
