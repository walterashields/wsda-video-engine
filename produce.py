#!/usr/bin/env python3
"""
WSDA Produce — single-command lesson pipeline

Runs the full production chain for one lesson:
  1. Pre-check  — verify narration numbers match actual query results
  2. Record     — silent video execution, produces audit log
  3. Narrate    — synthesize ElevenLabs clips, mix into video
  4. QA         — verify clip timing fits pause windows
                  if critical overrun (>5s): auto-fix card, re-record, re-narrate (once)
  5. Trim       — cut blank opening / dead tail
  6. Report     — summary of what was produced and any remaining warnings

Usage:
  python3 produce.py courses/novabridge/video_1_4/production_card.yml
  python3 produce.py courses/novabridge/video_1_4/production_card.yml --el-key KEY --el-voice ID

If ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID are set as environment variables,
--el-key / --el-voice are not required.
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

ROOT = Path(__file__).parent


def run_step(label: str, cmd: list[str]) -> tuple[int, str]:
    console.print(f"\n[bold cyan]▶ {label}[/bold cyan]")
    console.print(f"[dim]{' '.join(cmd)}[/dim]\n")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    output = result.stdout + result.stderr
    console.print(output)
    return result.returncode, output


def latest_pair(lesson_id: str) -> tuple[Path, Path] | None:
    """Find the most recent {lesson_id}_{ts}.mp4 / _audit.json pair in output/."""
    out_dir = ROOT / "output"
    mp4s = sorted(
        out_dir.glob(f"{lesson_id}_2*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for mp4 in mp4s:
        audit = mp4.with_name(mp4.stem + "_audit.json")
        if audit.exists():
            return mp4, audit
    return None


@click.command()
@click.argument("card_path")
@click.option("--el-key", default=None, help="ElevenLabs API key")
@click.option("--el-voice", default=None, help="ElevenLabs voice ID")
@click.option("--voice", default="Samantha", help="macOS fallback voice")
@click.option("--max-retries", default=1, type=int, help="Max auto-fix retry cycles")
@click.option("--skip-precheck", is_flag=True)
@click.option("--format", "fmt", default=None, help="Format constraint for duration")
def produce(card_path, el_key, el_voice, voice, max_retries, skip_precheck, fmt):
    card_path = Path(card_path)
    if not card_path.exists():
        console.print(f"[red]Production card not found: {card_path}[/red]")
        sys.exit(1)

    import yaml
    with open(card_path) as f:
        card = yaml.safe_load(f)
    lesson_id = card["lesson_id"]
    lesson_dir = card_path.parent

    el_key   = el_key   or os.environ.get("ELEVENLABS_API_KEY")
    el_voice = el_voice or os.environ.get("ELEVENLABS_VOICE_ID")
    use_el   = bool(el_key and el_voice)

    console.print(Panel(
        f"[bold]{card.get('title', lesson_id)}[/bold]\n"
        f"Lesson: {lesson_id}\n"
        f"Voice:  {'ElevenLabs' if use_el else f'macOS {voice}'}",
        title="WSDA Produce — single-command pipeline",
        border_style="green",
    ))

    # ── Step 1: Pre-check ────────────────────────────────────────
    if not skip_precheck:
        code, out = run_step(
            "Step 1/5 — Number pre-check",
            [sys.executable, "narration/check_numbers.py", str(card_path)],
        )
        passed = "No number mismatches found" in out
        if not passed:
            console.print(Panel(
                "[bold red]Pre-check failed.[/bold red]\n"
                "Narration numbers do not match what the viewer will display.\n"
                "Fix the production card narration, then run produce.py again.",
                border_style="red",
            ))
            sys.exit(1)
        console.print("[green]✓ Pre-check passed[/green]")
    else:
        console.print("[yellow]⚠ Skipping pre-check (--skip-precheck)[/yellow]")

    # ── Verify production card ────────────────────────────────
    console.print("\n[bold]Running verification...[/bold]")
    verify_cmd = [sys.executable, "verify.py", str(card_path), "--fix"]
    if fmt:
        verify_cmd += ["--format", fmt]
    vr = subprocess.run(verify_cmd, cwd=str(ROOT), capture_output=True, text=True)
    console.print(vr.stdout)
    if vr.returncode > 2:  # >2 unfixed issues = abort
        console.print(Panel(
            "[bold red]Verification failed — too many unfixable issues.[/bold red]\n"
            "Review the production card and fix manually.",
            border_style="red",
        ))
        sys.exit(1)
    console.print("[green]✓ Verification passed[/green]")

    attempt = 0
    final_mp4 = None

    while attempt <= max_retries:
        attempt += 1
        console.print(f"\n[bold]── Attempt {attempt}/{max_retries + 1} ──[/bold]")

        # ── Step 2: Record ──────────────────────────────────────
        code, out = run_step(
            "Step 2/5 — Recording silent video",
            [sys.executable, "run.py", str(card_path)],
        )
        if code != 0:
            console.print("[red]Recording failed. Aborting.[/red]")
            sys.exit(1)

        pair = latest_pair(lesson_id)
        if not pair:
            console.print("[red]Could not find recorded video/audit pair. Aborting.[/red]")
            sys.exit(1)
        mp4_path, audit_path = pair
        console.print(f"[green]✓[/green] Recorded: {mp4_path.name}")

        # ── Step 3: Narrate (includes built-in QA) ──────────────
        narrated_path = ROOT / "output" / f"{lesson_id}_produced.mp4"
        narrate_cmd = [
            sys.executable, "narration/audit_narrator.py",
            str(mp4_path), str(audit_path), str(card_path),
            "--output", str(narrated_path),
        ]
        if use_el:
            narrate_cmd += ["--elevenlabs", "--el-key", el_key, "--el-voice", el_voice]
        else:
            narrate_cmd += ["--voice", voice]

        code, out = run_step("Step 3/5 — Narrating + QA", narrate_cmd)

        if code != 0 and not ("QA found critical timing issues" in out):
            # A nonzero exit that ISN'T the known timing-retry case is a
            # real failure (e.g. narration synthesis failed for most/all
            # clips) - don't fall through to checking whether a file
            # happens to exist, since a silent video can still get written.
            console.print(
                f"[red]Narration step exited with an error (code {code}). "
                f"See output above for the cause.[/red]"
            )
            sys.exit(1)

        critical_fail = "QA found critical timing issues" in out
        rendered = narrated_path.exists()

        if critical_fail:
            console.print(
                f"[yellow]⚠ QA found critical timing issues and auto-fixed the "
                f"production card.[/yellow]"
            )
            if attempt <= max_retries:
                console.print("[bold]Retrying with corrected pause durations...[/bold]")
                continue
            else:
                console.print(
                    "[red]Max retries reached. Pauses were fixed in the card "
                    "but not re-recorded. Run produce.py again to apply them.[/red]"
                )
                sys.exit(1)

        if rendered:
            final_mp4 = narrated_path
            break
        else:
            console.print("[red]Narration step did not produce a video. Aborting.[/red]")
            sys.exit(1)

    if not final_mp4:
        console.print("[red]Production failed — no final video produced.[/red]")
        sys.exit(1)

    # ── Step 4: Trim ─────────────────────────────────────────────
    trimmed_path = ROOT / "output" / f"{lesson_id}_final.mp4"
    code, out = run_step(
        "Step 4/5 — Trimming blank opening / dead tail",
        [sys.executable, "trim.py", str(final_mp4), str(trimmed_path)],
    )
    if trimmed_path.exists():
        final_mp4 = trimmed_path

    # ── Step 5: Report ───────────────────────────────────────────
    dur_cmd = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(final_mp4)],
        capture_output=True, text=True,
    )
    try:
        dur = float(dur_cmd.stdout.strip())
        dur_str = f"{int(dur//60)}:{int(dur%60):02d}"
    except Exception:
        dur_str = "?"

    console.print(Panel(
        f"[bold green]Production complete.[/bold green]\n\n"
        f"Final video: [cyan]{final_mp4}[/cyan]\n"
        f"Duration:    {dur_str}\n"
        f"Attempts:    {attempt}\n\n"
        f"Open it with:\n  open {final_mp4}",
        title="Step 5/5 — Done",
        border_style="green",
    ))


if __name__ == "__main__":
    produce()
