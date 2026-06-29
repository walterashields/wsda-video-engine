#!/usr/bin/env python3
"""
WSDA Vision Narrator v2

Clean architecture:
1. Extract 1fps frames from silent video
2. Claude analyzes all frames, writes timed narration script
3. Each script line is synthesized as a WAV clip
4. Clips are concatenated into ONE sequential audio file
   with silence padding to hit the right start times
5. Single audio track mixed into video

No amix. No overlapping clips. One voice, one track.
"""

import base64, json, os, struct, subprocess, sys, wave
from pathlib import Path
import click, yaml
from rich.console import Console
from rich.panel import Panel

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


def extract_frames(video_path: Path) -> list[dict]:
    out_dir = video_path.parent / f"_vframes_{video_path.stem}"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "fps=1", "-q:v", "4",
        str(out_dir / "f%04d.jpg")
    ], capture_output=True, check=True)
    frames = sorted(out_dir.glob("f*.jpg"))
    return [{"t": i, "path": str(f)} for i, f in enumerate(frames)]


def generate_script(frames: list[dict], duration: float, context: str, api_key: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    content = []
    for f in frames:
        content.append({"type": "text", "text": f"[{f['t']}s]"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(open(f["path"], "rb").read()).decode()
            }
        })

    content.append({"type": "text", "text": f"""
You are writing narration for a {duration:.0f}-second instructional video about data analysis.

Lesson context:
{context}

I've shown you every second of the video labeled with its timestamp.

Write a narration script. Rules:
- One sentence at a time, each with a start time
- Each sentence must FINISH before the next one STARTS
- Assume 140 words per minute speech rate
- Calculate: if a sentence has 14 words, it takes ~6 seconds, so next sentence starts 6+ seconds later
- Cover the whole video but end by {duration-4:.0f}s
- Describe what's actually visible on screen at each timestamp
- Sound like a professional instructor — natural, clear, specific
- Mention actual table names, column names, numbers you can read

Respond ONLY with a JSON array:
[
  {{"start_s": 1, "text": "sentence here"}},
  {{"start_s": 8, "text": "next sentence here"}},
  ...
]

IMPORTANT: Double-check your timing. If sentence at 1s has 15 words (~6.4s), 
the next sentence must start at 8s or later. No overlapping allowed.
"""})

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except Exception:
        import re
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        return json.loads(m.group()) if m else []


def synthesize(text: str, path: Path, voice: str, rate: int):
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(aiff),
                    "-ar", str(SAMPLE_RATE), "-ac", "1", str(path)],
                   check=True, capture_output=True)
    aiff.unlink(missing_ok=True)


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def read_wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), 'rb') as w:
        return w.readframes(w.getnframes())


def silence_pcm(seconds: float) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    return struct.pack(f"<{n}h", *([0] * n))


def build_audio_track(script: list[dict], duration: float, work_dir: Path, voice: str, rate: int) -> Path | None:
    """
    Build one sequential audio track.
    Each sentence starts at its scheduled time by padding with silence.
    No mixing. No overlapping. One clean track.
    """
    work_dir.mkdir(exist_ok=True)
    
    # Synthesize all lines first
    lines = []
    for i, entry in enumerate(script):
        start_s = float(entry["start_s"])
        text = entry["text"].strip()
        if not text:
            continue
        wav_path = work_dir / f"line_{i:03d}.wav"
        try:
            synthesize(text, wav_path, voice, rate)
            dur = wav_duration_s(wav_path)
            lines.append({"start_s": start_s, "dur_s": dur, "path": wav_path, "text": text})
            console.print(f"  {start_s:5.1f}s [{dur:.1f}s] {text[:65]}")
        except Exception as e:
            console.print(f"  [yellow]⚠ Failed: {e}[/yellow]")

    if not lines:
        return None

    # Build one sequential PCM buffer
    # Total length = video duration
    total_samples = int(SAMPLE_RATE * duration)
    buffer = bytearray(total_samples * 2)  # 16-bit = 2 bytes per sample

    cursor_s = 0.0  # where we are in the buffer

    for line in lines:
        target_s = line["start_s"]
        
        # If we're behind the target, add silence to reach it
        if cursor_s < target_s:
            gap = target_s - cursor_s
            gap_pcm = silence_pcm(gap)
            # Already have silence in buffer (zeros), just advance cursor
            cursor_s = target_s

        # Write speech at current position
        pcm = read_wav_pcm(line["path"])
        start_byte = int(cursor_s * SAMPLE_RATE) * 2
        end_byte = start_byte + len(pcm)
        
        if end_byte > len(buffer):
            # Clip to fit
            pcm = pcm[:len(buffer) - start_byte]
            end_byte = len(buffer)
        
        if start_byte < len(buffer) and len(pcm) > 0:
            buffer[start_byte:start_byte + len(pcm)] = pcm
        
        cursor_s = start_byte / 2 / SAMPLE_RATE + line["dur_s"]

    # Write final WAV
    out_path = work_dir / "track.wav"
    with wave.open(str(out_path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buffer))

    console.print(f"[green]✓[/green] Audio track: {duration:.1f}s")
    return out_path


def render(video: Path, audio: Path, output: Path, duration: float):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-vcodec", "copy",
        "-acodec", "aac", "-ab", "192k",
        str(output)
    ], check=True, capture_output=True)


@click.command()
@click.argument("video_path")
@click.argument("card_path")
@click.option("--output", default=None)
@click.option("--voice", default="Samantha")
@click.option("--rate", default=140, type=int)
@click.option("--api-key", default=None)
def cli(video_path, card_path, output, voice, rate, api_key):
    """Generate clean single-voice narration for a silent lesson video."""

    video_path = Path(video_path)
    card_path  = Path(card_path)
    api_key    = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        console.print("[red]Set ANTHROPIC_API_KEY[/red]"); return

    output = Path(output) if output else \
        video_path.parent / f"{video_path.stem}_narrated.mp4"

    with open(card_path) as f:
        card = yaml.safe_load(f)

    context = f"Title: {card.get('title','')}\n" + \
        "\n".join(f"- {e.get('narration','').strip()}"
                  for e in card.get('events', []) if e.get('narration','').strip())

    duration = get_video_duration(video_path)

    console.print(Panel(
        f"Video: [cyan]{video_path.name}[/cyan] ({duration:.1f}s)\n"
        f"Voice: [cyan]{voice}[/cyan] @ {rate} wpm",
        title="WSDA Vision Narrator v2", border_style="green"
    ))

    # 1. Extract frames
    console.print("\n[bold]1 — Extracting frames[/bold]")
    frames = extract_frames(video_path)
    console.print(f"[green]✓[/green] {len(frames)} frames")

    # 2. Generate script
    console.print("\n[bold]2 — Generating narration script[/bold]")
    script = generate_script(frames, duration, context, api_key)
    if not script:
        console.print("[red]No script generated[/red]"); return

    script_path = video_path.parent / f"script_{video_path.stem}.json"
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2)
    console.print(f"[green]✓[/green] {len(script)} lines — saved to {script_path.name}")

    # 3. Build audio track
    console.print("\n[bold]3 — Synthesizing narration[/bold]")
    work_dir = video_path.parent / f"_work_{video_path.stem}"
    audio = build_audio_track(script, duration, work_dir, voice, rate)
    if not audio:
        console.print("[red]Audio build failed[/red]"); return

    # 4. Render
    console.print("\n[bold]4 — Rendering final video[/bold]")
    try:
        render(video_path, audio, output, duration)
        console.print(Panel(
            f"[bold green]Done.[/bold green]\n\nVideo: [cyan]{output}[/cyan]",
            title="Complete", border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Render failed:[/red] {e}")


if __name__ == "__main__":
    cli()
