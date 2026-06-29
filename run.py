#!/usr/bin/env python3
"""
WSDA Video Engine — Run v10

Three modes:

  Default:   Silent visual recording only
  --narrated: Silent recording + vision-sync narration (recommended)
  --legacy:  Old audio-during-recording approach (deprecated)

Vision-sync workflow:
  1. Record silent video (visual execution only)
  2. Claude analyzes every frame — sees what's actually on screen
  3. Narration generated from what Claude observes
  4. Audio clips placed at exact timestamps where visuals appeared
  5. FFmpeg renders final MP4

Usage:
  python run.py courses/novabridge/video_1_1/production_card.yml
  python run.py courses/novabridge/video_1_1/production_card.yml --narrated
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import yaml
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent))

from engine.compiler import compile
from engine.timeline_runner import TimelineRunner
from engine.schemas import LessonTimeline

console = Console()


def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def convert_video(raw: Path, out: Path, audio: Path | None = None, trim_s: float | None = None):
    """Convert Playwright WebM to H.264 MP4, optionally mixing audio."""
    cmd = ["ffmpeg", "-y", "-i", str(raw)]
    if audio and audio.exists():
        dur = get_duration(raw)
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-t", str(dur)]
    if trim_s:
        cmd += ["-t", str(trim_s)]
    cmd += ["-vcodec", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if audio and audio.exists():
        cmd += ["-acodec", "aac", "-ab", "192k"]
    cmd.append(str(out))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg: {result.stderr.decode()[-400:]}")


@click.command()
@click.argument("card_path")
@click.option("--narrated", is_flag=True, help="Add vision-synchronized narration")
@click.option("--no-compile", is_flag=True)
@click.option("--no-record", is_flag=True)
@click.option("--voice", default="Samantha", help="macOS voice for narration")
@click.option("--rate", default=155, type=int, help="Speech rate wpm")
def run(card_path, narrated, no_compile, no_record, voice, rate):
    """Record a lesson video. Add --narrated for vision-synchronized audio."""

    card_path = Path(card_path)
    lesson_dir = card_path.parent

    settings_path = Path(__file__).parent / "config" / "settings.yml"
    settings = {}
    if settings_path.exists():
        with open(settings_path) as f:
            settings = yaml.safe_load(f)

    # Load or compile timeline (always use base timeline for recording)
    base_tl = lesson_dir / "lesson_timeline.json"
    if no_compile and base_tl.exists():
        with open(base_tl) as f:
            timeline = LessonTimeline(**json.load(f))
    else:
        timeline = compile(card_path)

    # Output paths
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    mp4_path  = out_dir / f"{timeline.lesson_id}_{ts}.mp4"
    audit_path = out_dir / f"{timeline.lesson_id}_{ts}_audit.json"
    tmp_dir   = out_dir / f"_tmp_{ts}"

    if not no_record:
        tmp_dir.mkdir(exist_ok=True)

    # Record silent video
    runner = TimelineRunner(
        timeline=timeline,
        rehearsal=False,
        speed=1.0,
        settings=settings,
        audio_path=None,  # always silent during recording
    )
    if not no_record:
        runner._video_dir = tmp_dir

    audit = asyncio.run(runner.run())

    # Convert silent video
    final_mp4 = None
    if not no_record:
        raw = runner._recorded_video_path
        if raw and Path(raw).exists():
            console.print("\n[dim]Converting video...[/dim]")
            try:
                # Trim to last event time + 3s buffer
                last_event_s = max((e.completed_at_ms for e in audit.events), default=0) / 1000
                trim_s = last_event_s + 3.0
                convert_video(Path(raw), mp4_path, audio=None, trim_s=trim_s)
                final_mp4 = mp4_path
                console.print(f"[green]✓[/green] Silent video: [cyan]{mp4_path}[/cyan]")
            except Exception as e:
                console.print(f"[red]Convert failed:[/red] {e}")
                shutil.move(str(raw), str(mp4_path))
                final_mp4 = mp4_path
        else:
            console.print("[yellow]⚠[/yellow]  No video produced")

        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # Vision-sync narration
    if narrated and final_mp4 and final_mp4.exists():
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            console.print(
                "\n[yellow]⚠[/yellow]  ANTHROPIC_API_KEY not set — skipping narration.\n"
                "  Set it and run:\n"
                f"  python3 narration/vision_sync.py {final_mp4} {card_path}"
            )
        else:
            console.print(f"\n[bold]Adding vision-synchronized narration...[/bold]")
            from narration.vision_sync import run_vision_sync

            narrated_path = out_dir / f"{timeline.lesson_id}_narrated_{ts}.mp4"
            el_key   = os.environ.get("ELEVENLABS_API_KEY")
            el_voice = os.environ.get("ELEVENLABS_VOICE_ID")

            result = run_vision_sync(
                video_path=final_mp4,
                card_path=card_path,
                output_path=narrated_path,
                api_key=api_key,
                voice=voice,
                rate=rate,
                elevenlabs_key=el_key,
                elevenlabs_voice_id=el_voice,
            )
            if result:
                final_mp4 = result

    # Save audit
    audit.mp4_path = str(final_mp4) if final_mp4 else None
    with open(audit_path, "w") as f:
        json.dump(audit.model_dump(), f, indent=2)

    console.print(Panel(
        f"[bold green]Complete.[/bold green]\n\n"
        + (f"MP4:   [cyan]{final_mp4}[/cyan]\n" if final_mp4 else "")
        + f"Audit: [cyan]{audit_path}[/cyan]\n\n"
        f"Events: {audit.successful_events}/{audit.total_events}"
        + ("\n\nTo add narration later:\n"
           f"  python3 narration/vision_sync.py {final_mp4 or mp4_path} {card_path}"
           if not narrated else ""),
        title="Done",
        border_style="green",
    ))


if __name__ == "__main__":
    run()
