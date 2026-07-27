#!/usr/bin/env python3
"""
WSDA Video Reviewer — Post-render visual quality gate

The text-based quality gate (review_teaching_quality) verifies that the
LESSON is good. This verifies that the VIDEO is good — two completely
different things. A lesson with perfect narration can still fail as a
video if the text is too small, the first frame is boring, or the visual
hierarchy guides the eye to the wrong thing.

This uses a vision model to watch the actual rendered MP4 and score it.
It is deliberately strict: a video that passes here is one a viewer can
actually learn from, not just one that is technically correct.
"""

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel

console = Console()
client = Anthropic()

SAMPLE_FRAMES = 6  # Extract N evenly-spaced frames for review

VIDEO_REVIEW_SYSTEM = """You are a ruthless visual-quality reviewer for short-form
educational video content that will be SOLD to individuals and organizations.

Your ONLY job is to evaluate the VISUAL and PRODUCTION quality of the video frames
you are shown. You do NOT evaluate the correctness of the SQL, the accuracy of the
numbers, or the pedagogical soundness of the lesson — other systems handle that.
You evaluate whether a human viewer can actually WATCH and LEARN from this video.

Score each dimension from 1-5 (5 = excellent, 1 = fails):

1. VISUAL READABILITY: Can a viewer read every piece of text on screen without
   squinting, on a phone held at normal distance? Score 1 if any text is too small,
   too low-contrast, or cluttered. Score 5 if everything is crisp, large, and
   immediately legible.

2. FIRST-3-SECONDS IMPACT: Does the opening frame make someone want to keep
   watching? Is there a compelling visual hook (a surprising number, a clear
   problem statement, an intriguing query)? Score 1 if it's a generic schema
   panel or blank screen. Score 5 if the opening frame alone communicates the
   lesson's stakes.

3. VISUAL-CONTENT ALIGNMENT: When the narration (provided to you) references a
   specific number, table, or query result, is that element VISIBLE and PROMINENT
   in the corresponding frame? Score 1 if the narrator mentions something that
   is off-screen, tiny, or buried. Score 5 if every referenced element is the
   visual center of attention.

4. VISUAL HIERARCHY: Is the most important information the most visible? Are
   secondary elements (UI chrome, metadata, unused panels) appropriately
   de-emphasized? Score 1 if the screen is a wall of equal-weight text. Score 5
   if the eye is naturally guided to what matters.

5. PROFESSIONAL POLISH: Does this look like a product from a professional
   education company (DataCamp, LinkedIn Learning, etc.), or like a screen
   recording thrown together? Score 1 if fonts mismatch, spacing is inconsistent,
   or colors clash. Score 5 if it looks intentionally designed.

Respond with ONLY valid JSON, no markdown, no preamble:
{
  "scores": {"visual_readability": N, "first_3_seconds": N, "visual_alignment": N, "visual_hierarchy": N, "professional_polish": N},
  "overall_pass": true/false,
  "feedback": ["specific, actionable note", "specific, actionable note"],
  "critical_frames": [{"timestamp": "0:00", "issue": "description"}, ...]
}

overall_pass is true ONLY if every dimension scores 4 or higher. Be honest — a
video with perfect content but poor production quality will still fail to engage
learners and should NOT pass."""

VIDEO_REVIEW_PROMPT = """Lesson: {title}

Narration timeline (what the viewer hears at each moment):
{narration_timeline}

Review the {frame_count} video frames provided. These represent key moments
from the lesson. Score each dimension and list specific visual issues.

Be strict. This video will be sold as a paid product."""


def extract_frames(mp4_path: Path, count: int = SAMPLE_FRAMES) -> list[Path]:
    """Extract N evenly-spaced frames from the video as JPEGs."""
    duration_s = _get_duration(mp4_path)
    interval = duration_s / (count + 1)

    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(1, count + 1):
            ts = interval * i
            out = Path(tmpdir) / f"frame_{i:02d}_{ts:.1f}s.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(ts), "-i", str(mp4_path),
                    "-vframes", "1", "-q:v", "2", str(out)
                ],
                check=True, capture_output=True,
            )
            frames.append(out)
    return frames


def _get_duration(mp4_path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp4_path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_narration_timeline(card_yaml: str) -> str:
    """Build a timestamped narration summary for the vision model."""
    card = yaml.safe_load(card_yaml)
    events = card.get("events", [])
    lines = []
    current_time = 0.0

    for e in events:
        etype = e.get("type", "")
        eid = e.get("id", "")
        narr = (e.get("narration") or "").strip()

        if etype == "pause":
            current_time += float(e.get("duration", 0))
            continue

        if narr:
            ts = _fmt_time(current_time)
            lines.append(f"[{ts}] {eid} ({etype}): {narr[:120]}{'...' if len(narr) > 120 else ''}")

    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def review_video(mp4_path: Path, card_path: Path) -> dict:
    """
    Run the post-render visual quality gate.
    Returns the parsed review result dict.
    """
    if not mp4_path.exists():
        raise FileNotFoundError(f"Video not found: {mp4_path}")

    console.print(f"\n[bold cyan]▶ Video Review[/bold cyan]")
    console.print(f"Video: {mp4_path.name}")
    console.print(f"Extracting {SAMPLE_FRAMES} frames for vision analysis...")

    frames = extract_frames(mp4_path, SAMPLE_FRAMES)
    for f in frames:
        console.print(f"  [dim]Frame: {f.name}[/dim]")

    card_yaml = card_path.read_text()
    narration_timeline = _build_narration_timeline(card_yaml)

    # Build message with images
    content_blocks = []
    content_blocks.append({
        "type": "text",
        "text": VIDEO_REVIEW_PROMPT.format(
            title=yaml.safe_load(card_yaml).get("title", "Untitled"),
            narration_timeline=narration_timeline,
            frame_count=len(frames),
        ),
    })

    for frame_path in frames:
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": _encode_image(frame_path),
            },
        })

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=VIDEO_REVIEW_SYSTEM,
            messages=[{"role": "user", "content": content_blocks}],
        )
    except Exception as e:
        return {
            "scores": {}, "overall_pass": False,
            "feedback": [f"Video review API call failed: {e}. Treating as fail-safe."],
            "critical_frames": [],
        }

    text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    text = text_blocks[-1].strip() if text_blocks else ""
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = __import__("re").search(r"\{.*\}", text, __import__("re").DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {
            "scores": {}, "overall_pass": False,
            "feedback": ["Could not parse video review response — treating as fail-safe."],
            "critical_frames": [],
        }


def main():
    import click

    @click.command()
    @click.argument("mp4_path")
    @click.argument("card_path")
    def cli(mp4_path, card_path):
        result = review_video(Path(mp4_path), Path(card_path))
        console.print(Panel(
            f"[bold]Video Review Result[/bold]\n\n"
            f"Scores: {result.get('scores')}\n"
            f"Pass: {'[green]YES[/green]' if result.get('overall_pass') else '[red]NO[/red]'}\n\n"
            f"Feedback:\n" + "\n".join(f"- {f}" for f in result.get("feedback", [])),
            border_style="green" if result.get("overall_pass") else "red",
        ))
        sys.exit(0 if result.get("overall_pass") else 1)

    cli()


if __name__ == "__main__":
    main()
