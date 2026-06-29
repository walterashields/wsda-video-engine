#!/usr/bin/env python3
"""
WSDA Audit Narrator v3

Key insight: pause events in the audit ARE the narration windows.
Each pause event tells us exactly when there is dead air on screen.
That dead air is when narration should play.

Flow:
  Visual fires → completes → PAUSE starts → narration plays during pause → next visual

The narration for event X plays during the PAUSE that follows event X.
Not immediately after event X completes.
"""

import json, os, struct, subprocess, sys, wave
from pathlib import Path
import click, yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))
console = Console()
SAMPLE_RATE = 44100


def get_video_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def synthesize(text: str, path: Path, voice: str, rate: int,
               el_key=None, el_voice=None):
    if el_key and el_voice:
        import urllib.request, json as _j
        payload = _j.dumps({"text": text, "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.85,
                               "style": 0.0, "use_speaker_boost": True}}).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice}",
            data=payload,
            headers={"xi-api-key": el_key, "Content-Type": "application/json",
                     "Accept": "audio/mpeg"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            mp3 = path.with_suffix(".mp3")
            mp3.write_bytes(resp.read())
        subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-ar", str(SAMPLE_RATE),
                        "-ac", "1", str(path)], check=True, capture_output=True)
        mp3.unlink(missing_ok=True)
    else:
        aiff = path.with_suffix(".aiff")
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff), "-ar", str(SAMPLE_RATE),
                        "-ac", "1", str(path)], check=True, capture_output=True)
        aiff.unlink(missing_ok=True)


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def read_wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), 'rb') as w:
        return w.readframes(w.getnframes())


def build_track(clips: list[dict], duration_s: float, work_dir: Path) -> Path:
    """Place clips into a PCM buffer at exact timestamps. No mixing."""
    total = int(SAMPLE_RATE * duration_s)
    buf = bytearray(total * 2)

    table = Table(header_style="bold cyan")
    table.add_column("Starts at")
    table.add_column("Duration")
    table.add_column("Ends at")
    table.add_column("Narration")

    for clip in clips:
        start_s = clip["start_s"]
        wav = clip["wav_path"]
        if not wav or not Path(wav).exists():
            continue

        dur = wav_duration_s(Path(wav))
        end_s = start_s + dur
        pcm = read_wav_pcm(Path(wav))

        start_byte = int(start_s * SAMPLE_RATE) * 2
        available = len(buf) - start_byte
        if available <= 0:
            console.print(f"  [yellow]⚠ Clip past end, skipping[/yellow]")
            continue
        pcm = pcm[:available]
        buf[start_byte:start_byte + len(pcm)] = pcm

        mm_s, ss_s = divmod(start_s, 60)
        mm_e, ss_e = divmod(end_s, 60)
        table.add_row(
            f"{int(mm_s):02d}:{ss_s:04.1f}",
            f"{dur:.1f}s",
            f"{int(mm_e):02d}:{ss_e:04.1f}",
            clip["text"][:60] + ("…" if len(clip["text"]) > 60 else "")
        )

    console.print(table)

    out = work_dir / "track.wav"
    with wave.open(str(out), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))
    return out


def render(video: Path, audio: Path, output: Path, duration: float):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video), "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-acodec", "aac", "-ab", "192k",
        str(output)
    ], check=True, capture_output=True)


@click.command()
@click.argument("video_path")
@click.argument("audit_path")
@click.argument("card_path")
@click.option("--output", default=None)
@click.option("--voice", default="Samantha")
@click.option("--rate", default=145, type=int)
@click.option("--lead", default=0.3, type=float,
              help="Seconds into the pause before narration starts")
@click.option("--elevenlabs", is_flag=True, help="Use ElevenLabs voice")
@click.option("--el-key", default=None, help="ElevenLabs API key (or ELEVENLABS_API_KEY)")
@click.option("--el-voice", default=None, help="ElevenLabs voice ID (or ELEVENLABS_VOICE_ID)")
def cli(video_path, audit_path, card_path, output, voice, rate, lead, elevenlabs, el_key, el_voice):
    """
    Add narration timed to visual pause events in the audit log.
    Narration plays DURING the pause that follows each visual event.
    """
    video_path = Path(video_path)
    audit_path = Path(audit_path)
    card_path  = Path(card_path)
    output = Path(output) if output else \
        video_path.parent / f"{video_path.stem}_narrated.mp4"

    with open(audit_path) as f:
        audit = json.load(f)
    with open(card_path) as f:
        card = yaml.safe_load(f)

    # Build event map from audit
    audit_events = {e["event_id"]: e for e in audit["events"]}

    # Build narration map from card
    narration_map = {}
    for e in card.get("events", []):
        text = (e.get("narration") or "").strip()
        if text:
            narration_map[e["id"]] = text

    # Build pause map: pause_event_id → start_ms
    # A pause event starts when the previous event completes
    # We need to find each pause and what narration precedes it
    card_events = card.get("events", [])

    # Build schedule: for each narration event, find the pause that follows it
    # and schedule narration to start at pause_start + lead
    schedule = []

    for i, event in enumerate(card_events):
        eid = event["id"]
        if eid not in narration_map:
            continue

        # Find the pause that follows this event
        next_pause = None
        for j in range(i + 1, len(card_events)):
            if card_events[j]["type"] == "pause":
                next_pause = card_events[j]
                break
            elif card_events[j].get("narration", "").strip():
                # Another narration event before a pause — no pause window
                break

        if next_pause is None:
            # No pause follows — use end of this event + lead as fallback
            if eid in audit_events:
                start_s = audit_events[eid]["completed_at_ms"] / 1000 + lead
            else:
                continue
        else:
            pause_id = next_pause["id"]
            if pause_id in audit_events:
                # Pause starts when audit says it started
                start_s = audit_events[pause_id]["started_at_ms"] / 1000 + lead
            elif eid in audit_events:
                # Fallback: after the narration event
                start_s = audit_events[eid]["completed_at_ms"] / 1000 + lead
            else:
                continue

        schedule.append({
            "event_id": eid,
            "start_s":  start_s,
            "text":     narration_map[eid],
            "wav_path": None,
        })

    if not schedule:
        console.print("[red]No narration schedule built[/red]")
        return

    duration = get_video_duration(video_path)

    import os as _os
    _el_key   = el_key   or _os.environ.get("ELEVENLABS_API_KEY")
    _el_voice = el_voice or _os.environ.get("ELEVENLABS_VOICE_ID")
    if elevenlabs and not (_el_key and _el_voice):
        console.print("[red]--elevenlabs requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID[/red]")
        return
    use_el = elevenlabs and _el_key and _el_voice
    voice_label = f"ElevenLabs ({_el_voice[:8]}…)" if use_el else f"{voice} @ {rate}wpm"

    console.print(Panel(
        f"Video: [cyan]{video_path.name}[/cyan] ({duration:.1f}s)\n"
        f"Voice: [cyan]{voice_label}[/cyan]  |  Lead: {lead}s into pause",
        title="WSDA Audit Narrator v3", border_style="green"
    ))

    # Synthesize clips
    work_dir = video_path.parent / f"_auditwork_{video_path.stem}"
    work_dir.mkdir(exist_ok=True)

    console.print(f"\n[bold]Synthesizing {len(schedule)} clips...[/bold]")
    for i, entry in enumerate(schedule):
        wav = work_dir / f"clip_{i:03d}_{entry['event_id']}.wav"
        try:
            synthesize(entry["text"], wav, voice, rate,
                       el_key=_el_key if use_el else None,
                       el_voice=_el_voice if use_el else None)
            entry["wav_path"] = str(wav)
            dur = wav_duration_s(wav)
            words = len(entry["text"].split())
            console.print(
                f"  {entry['start_s']:5.1f}s  {dur:.1f}s  "
                f"[dim]{words}w[/dim]  {entry['text'][:55]}"
            )
        except Exception as e:
            console.print(f"  [red]Failed {entry['event_id']}: {e}[/red]")

    # Build and render
    # ── Auto QA before render ──────────────────────────────────
    console.print(f"\n[bold]Running QA checks...[/bold]")
    from narration.qa import qa as run_qa
    from click.testing import CliRunner
    runner_cli = CliRunner()
    qa_result = runner_cli.invoke(run_qa, [
        str(audit_path),
        str(card_path),
        "--work-dir", str(work_dir),
        "--fix",
    ])
    console.print(qa_result.output)

    # Check if QA found CRITICAL timing issues (>5s overrun)
    # Minor overruns (<5s) are allowed - audio will overlap slightly but remain usable
    import re as _re
    critical = False
    for m in _re.finditer(r'by ([\d.]+)s', qa_result.output):
        overrun = float(m.group(1))
        if overrun > 5.0:
            critical = True
            break

    if critical:
        console.print("[bold red]⚠ QA found critical timing issues (>5s). Auto-fixed pause durations.[/bold red]")
        console.print("[bold yellow]Re-record with: python3 run.py " + str(card_path) + "[/bold yellow]")
        console.print("[dim]Then re-run this command with the new timestamp.[/dim]")
        return
    elif "TIMING" in qa_result.output:
        console.print("[yellow]⚠ Minor timing issues (<5s). Proceeding with render.[/yellow]")

    console.print(f"\n[bold]Building audio track...[/bold]")
    track = build_track(schedule, duration, work_dir)

    console.print(f"\n[bold]Rendering...[/bold]")
    render(video_path, track, output, duration)

    console.print(Panel(
        f"[bold green]Done.[/bold green]\n\nVideo: [cyan]{output}[/cyan]",
        title="Complete", border_style="green"
    ))


if __name__ == "__main__":
    cli()
