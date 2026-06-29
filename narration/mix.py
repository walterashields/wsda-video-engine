#!/usr/bin/env python3
"""
WSDA Audio Mixer
Takes a sync file produced by the runner and assembles
narration segments into a final mixed WAV using ffmpeg.

Sync file format (JSON):
  [{"event_id": "e04", "segment_starts_at_ms": 10500, "segment_file": "seg_e04.wav"}, ...]

Uses FFmpeg amix with adelay — precise, no Python audio math.
"""

import json
import subprocess
from pathlib import Path
from rich.console import Console

console = Console()


def mix_from_sync(sync_path: Path, output_path: Path, video_duration_ms: int):
    """
    Build audio track from sync file using FFmpeg adelay filter.
    Each segment is delayed by its start time and mixed together.
    """
    with open(sync_path) as f:
        entries = json.load(f)

    if not entries:
        console.print("[yellow]No audio segments to mix[/yellow]")
        return None

    # Verify all segment files exist
    missing = [e for e in entries if not Path(e["segment_file"]).exists()]
    if missing:
        console.print(f"[red]Missing segment files: {[m['event_id'] for m in missing]}[/red]")
        return None

    # Build FFmpeg filter graph
    # Each input gets delayed by its start time
    # All delayed inputs are mixed together

    inputs = []
    filter_parts = []
    mix_inputs = []

    for i, entry in enumerate(entries):
        inputs += ["-i", entry["segment_file"]]
        delay_ms = entry["segment_starts_at_ms"]
        # adelay applies delay in ms to each channel
        filter_parts.append(f"[{i}]adelay={delay_ms}|{delay_ms}[a{i}]")
        mix_inputs.append(f"[a{i}]")

    # Mix all delayed streams
    n = len(entries)
    filter_parts.append(f"{''.join(mix_inputs)}amix=inputs={n}:dropout_transition=0[out]")
    filter_graph = ";".join(filter_parts)

    # Duration to trim to
    dur_s = video_duration_ms / 1000

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-t", str(dur_s),
        "-ar", "16000",
        "-ac", "1",
        str(output_path)
    ]

    console.print(f"  Mixing {n} segments into audio track...")
    console.print(f"  [dim]Filter: {filter_graph[:120]}...[/dim]")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]FFmpeg mix failed:[/red]")
        console.print(result.stderr[-500:])
        return None

    console.print(f"[green]✓[/green] Audio track: [cyan]{output_path.name}[/cyan]")
    return output_path
