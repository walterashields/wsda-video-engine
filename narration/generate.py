import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""
WSDA Narration Generator v3 — Variable Cue Architecture

Generates audio with transition-aware silence gaps:
  new_concept  → 900ms silence
  continuation → 450ms silence  
  emphasis     → 650ms silence

Each silence is a precise sync point for the aligner.
"""

import json, os, struct, subprocess, wave
from pathlib import Path
import click, yaml
from rich.console import Console
from rich.table import Table
from engine.schemas import TRANSITION_SILENCE

console = Console()
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2


def make_silence(ms: int) -> bytes:
    n = int(SAMPLE_RATE * ms / 1000)
    return struct.pack(f"<{n}h", *([0] * n))


def read_wav_pcm(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), 'rb') as w:
        return w.readframes(w.getnframes()), w.getframerate()


def write_wav(path: Path, pcm: bytes):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def resample(src: Path, dst: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1", str(dst)],
        capture_output=True, check=True
    )


def tts_macos(text: str, path: Path, voice: str, rate: int):
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                   capture_output=True, check=True)
    resample(aiff, path)
    aiff.unlink(missing_ok=True)


def tts_elevenlabs(text: str, path: Path, voice_id: str, api_key: str):
    import requests
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        json={"text": text, "model_id": "eleven_turbo_v2_5",
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.85}},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    mp3 = path.with_suffix(".mp3")
    mp3.write_bytes(r.content)
    resample(mp3, path)
    mp3.unlink(missing_ok=True)


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


def extract_segments(card_path: Path) -> list[dict]:
    with open(card_path) as f:
        card = yaml.safe_load(f)
    return [
        {
            "event_id":   e["id"],
            "event_type": e["type"],
            "text":       (e.get("narration") or "").strip(),
            "transition": e.get("transition", "new_concept"),
            "offset_override": float(e.get("offset_override", 0.0)),
        }
        for e in card.get("events", [])
        if (e.get("narration") or "").strip()
    ]


@click.command()
@click.argument("card_path", required=False)
@click.option("--elevenlabs", is_flag=True)
@click.option("--voice", default="Samantha")
@click.option("--rate", default=155, type=int)
@click.option("--voice-id", default=None)
@click.option("--list-voices", is_flag=True)
def cli(card_path, elevenlabs, voice, rate, voice_id, list_voices):
    """Generate variable-cue narration audio from a production card."""

    if list_voices:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if "en_" in line or "en-" in line:
                console.print(f"  {line}")
        return

    if not card_path:
        console.print("[red]card_path required[/red]"); return

    card_path = Path(card_path)
    out_dir = card_path.parent
    tmp = out_dir / "_seg_tmp"
    tmp.mkdir(exist_ok=True)

    console.print(f"\n[bold green]WSDA Narration Generator v3[/bold green]")
    segments = extract_segments(card_path)
    console.print(f"[green]✓[/green] {len(segments)} segments with variable silence gaps\n")

    api_key = os.environ.get("ELEVENLABS_API_KEY") if elevenlabs else None
    vid = voice_id or os.environ.get("ELEVENLABS_VOICE_ID") if elevenlabs else None

    table = Table(header_style="bold cyan")
    table.add_column("Event")
    table.add_column("Words")
    table.add_column("Duration")
    table.add_column("Cue silence")
    table.add_column("Transition")

    combined_pcm = b""
    cursor_ms = 0
    segment_meta = []

    for seg in segments:
        if not seg["text"]:
            continue

        seg_path = tmp / f"{seg['event_id']}.wav"

        if elevenlabs:
            tts_elevenlabs(seg["text"], seg_path, vid, api_key)
        else:
            tts_macos(seg["text"], seg_path, voice, rate)

        pcm, sr = read_wav_pcm(seg_path)
        dur_ms = int(len(pcm) / (SAMPLE_WIDTH * CHANNELS) / sr * 1000)

        seg_start_ms = cursor_ms
        combined_pcm += pcm
        cursor_ms += dur_ms

        # Variable silence based on transition type
        silence_ms = TRANSITION_SILENCE.get(seg["transition"], 650)
        combined_pcm += make_silence(silence_ms)
        cue_start_ms = cursor_ms     # silence starts here = cue point
        cursor_ms += silence_ms

        segment_meta.append({
            "event_id":      seg["event_id"],
            "event_type":    seg["event_type"],
            "transition":    seg["transition"],
            "offset_override": seg["offset_override"],
            "text":          seg["text"],
            "seg_start_ms":  seg_start_ms,
            "seg_end_ms":    seg_start_ms + dur_ms,
            "cue_start_ms":  cue_start_ms,
            "cue_silence_ms": silence_ms,
            "duration_ms":   dur_ms,
            "word_count":    len(seg["text"].split()),
        })

        table.add_row(
            seg["event_id"],
            str(len(seg["text"].split())),
            f"{dur_ms/1000:.2f}s",
            f"{silence_ms}ms",
            seg["transition"],
        )

    console.print(table)

    wav_path = out_dir / "narration.wav"
    write_wav(wav_path, combined_pcm)
    total_dur = get_duration(wav_path)

    meta = {
        "schema_version":   "3.0",
        "voice":            voice if not elevenlabs else f"elevenlabs:{vid}",
        "elevenlabs":       elevenlabs,
        "sample_rate":      SAMPLE_RATE,
        "segments":         segment_meta,
        "total_duration_s": total_dur,
        "production_ready": elevenlabs,
    }
    with open(out_dir / "narration_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Script reference
    lines = []
    for s in segment_meta:
        lines += [f"[{s['event_id']} — {s['event_type']} — {s['transition']}]",
                  s["text"], f"  ↳ cue at {s['cue_start_ms']/1000:.2f}s", ""]
    (out_dir / "narration_script.txt").write_text("\n".join(lines))

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    console.print(f"\n[green]✓[/green] Audio: [cyan]{wav_path}[/cyan] ({total_dur:.1f}s)")
    console.print(f"\nNext: [bold]python3 narration/align.py {card_path}[/bold]")


if __name__ == "__main__":
    cli()
