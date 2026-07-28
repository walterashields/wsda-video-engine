#!/usr/bin/env python3
"""
WSDA Narrator v2 — Generate narration by watching actual video frames

This is the core of the render-first architecture. Instead of writing
narration blind and then verifying it, the model watches the actual
rendered video and describes what it sees.

This eliminates:
- Number verification (model sees actual numbers on screen)
- Timing math (system measures actual video duration)
- Quality gate false positives (model narrates what it sees)
- Frozen screen bugs (model sees if nothing changes)

Usage:
    from narrator_v2 import NarratorV2
    narrator = NarratorV2()
    narration_yaml = narrator.narrate("silent.mp4", "storyboard.yml", "micro")
"""

import base64
import json
import re
import subprocess
from pathlib import Path

import yaml
from anthropic import Anthropic
from rich.console import Console

console = Console()
client = Anthropic()

NARRATION_SYSTEM = """You are a professional educational video narrator for WSDA.

Your job is to write narration for a video by WATCHING the actual frames.
You see exactly what the viewer sees, so you can never describe something
that isn't on screen.

NARRATION RULES:
1. Be warm, conversational, and human — use contractions throughout
2. Spell out ALL numbers in words ("twenty nine ninety nine" not "29.99")
3. Every technical term must be translated into a physical image in the SAME sentence
4. First 3 seconds must state the stakes — why should the viewer care?
5. No setup, no context-building — jump straight to the problem
6. Match your pacing to the visual: if the screen shows a result table,
   describe what's in it; if it shows SQL, explain what the query does
7. Use phrases like "Look at this" and "See how" to guide the eye
8. End with a clear takeaway the viewer can act on

FORMAT-SPECIFIC GUIDANCE:
- MICRO (1-3 min): ONE single idea. Hook in 3 seconds. No digressions.
  Total narration under 250 words.
- SHORT (3-5 min): One concept with proof. Hook in 5 seconds.
  Total narration under 500 words.
- STANDARD (8-15 min): Full concept with multiple angles.
  Total narration under 1200 words.

You will receive frames from the video and the visual storyboard that
generated it. Write narration for each frame. Keep it tight.
"""


class NarratorV2:
    """Generates narration by watching actual video frames."""

    def __init__(self):
        self.client = Anthropic()

    def extract_frames(self, mp4_path: Path, count: int = 8) -> list[Path]:
        """Extract evenly-spaced frames from the video."""
        # Get duration
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp4_path)],
            capture_output=True, text=True,
        )
        duration = float(r.stdout.strip())

        frames_dir = mp4_path.parent / f"{mp4_path.stem}_narration_frames"
        frames_dir.mkdir(exist_ok=True)

        frames = []
        for i in range(1, count + 1):
            ts = duration * i / (count + 1)
            out = frames_dir / f"frame_{i:02d}_{ts:.1f}s.jpg"
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(ts), "-i", str(mp4_path),
                "-vframes", "1", "-q:v", "2", str(out)
            ], check=True, capture_output=True)
            frames.append(out)

        return frames

    def encode_image(self, path: Path) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def build_storyboard_context(self, storyboard_path: Path) -> str:
        """Build a text summary of the visual storyboard for context."""
        with open(storyboard_path) as f:
            sb = yaml.safe_load(f)

        events = sb.get("events", [])
        lines = []
        for e in events:
            etype = e.get("type", "")
            if etype == "pause":
                continue
            lines.append(f"- {etype}: {json.dumps(e, default=str)}")

        return "\n".join(lines)

    def narrate(self, mp4_path: Path, storyboard_path: Path, fmt: str) -> str:
        """Generate narration YAML from video frames and storyboard."""
        console.print(f"[cyan]Extracting frames from {mp4_path.name}...[/cyan]")
        frames = self.extract_frames(mp4_path)

        console.print(f"[cyan]Generating narration for {len(frames)} frames...[/cyan]")

        storyboard_context = self.build_storyboard_context(storyboard_path)

        # Build message with frames
        content_blocks = []
        content_blocks.append({
            "type": "text",
            "text": f"""Write narration for this {fmt} format video.

Visual storyboard (what happens on screen):
{storyboard_context}

For each frame shown below, write narration that:
1. Describes what the viewer sees
2. Explains why it matters
3. Uses contractions and casual speech
4. Spells out all numbers in words
5. Keeps total under {250 if fmt == 'micro' else 500 if fmt == 'short' else 1200} words

Return ONLY a YAML structure like:
segments:
  - timestamp: "0:00"
    narration: "Your narration here..."
  - timestamp: "0:15"
    narration: "Next narration..."
"""
        })

        for frame_path in frames:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": self.encode_image(frame_path),
                },
            })

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system=NARRATION_SYSTEM,
            messages=[{"role": "user", "content": content_blocks}]
        )

        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        raw = text_blocks[-1].strip() if text_blocks else ""
        raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```\s*$', '', raw.strip())

        # Validate it's valid YAML
        try:
            parsed = yaml.safe_load(raw)
            if not parsed or "segments" not in parsed:
                console.print("[yellow]Warning: narration missing segments, returning raw[/yellow]")
        except yaml.YAMLError:
            console.print("[yellow]Warning: invalid YAML in narration, returning raw[/yellow]")

        return raw


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python3 narrator_v2.py <silent.mp4> <storyboard.yml> <format>")
        sys.exit(1)

    narrator = NarratorV2()
    result = narrator.narrate(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    print(result)
