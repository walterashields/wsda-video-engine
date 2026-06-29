import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""
WSDA Narration Aligner v3 — Variable-Cue Detection

Detects variable-length silence cues embedded during generation.
Each silence is a known transition type with a known minimum duration.
Uses that knowledge to reject false positives.

Visual fire time = seg_end + EVENT_ACTION_OFFSET[event_type] + offset_override
"""

import json, math, struct, subprocess, wave
from pathlib import Path
import click, yaml
from rich.console import Console
from rich.table import Table
from engine.schemas import EVENT_ACTION_OFFSET, TRANSITION_SILENCE

# Can't use walrus in import line — define here
MIN_CONFIDENCE = 0.82

console = Console()


def read_wav(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), 'rb') as w:
        sr = w.getframerate()
        sw = w.getsampwidth()
        nc = w.getnchannels()
        raw = w.readframes(w.getnframes())
        n = w.getnframes()

    if sw == 2:
        samples = [s / 32768.0 for s in struct.unpack(f"<{n*nc}h", raw)]
    else:
        samples = [(s-128)/128.0 for s in struct.unpack(f"{n*nc}B", raw)]

    if nc == 2:
        samples = [(samples[i]+samples[i+1])/2 for i in range(0, len(samples), 2)]

    return samples, sr


def rms_windows(samples: list[float], sr: int, win_ms: int = 15) -> list[tuple[float, float]]:
    size = int(sr * win_ms / 1000)
    step = size // 2
    out = []
    for i in range(0, len(samples) - size, step):
        w = samples[i:i+size]
        rms = math.sqrt(sum(s*s for s in w) / len(w))
        out.append((i / sr, rms))
    return out


def auto_threshold(windows: list[tuple[float, float]]) -> float:
    vals = sorted(r for _, r in windows)
    p10 = vals[len(vals)//10]
    p90 = vals[int(len(vals)*0.9)]
    return max(0.004, min(0.04, p10 + (p90 - p10) * 0.10))


def detect_silences(
    windows: list[tuple[float, float]],
    threshold: float,
    min_ms: int = 200,
    min_speech_ms: int = 80,
) -> list[tuple[float, float]]:
    silent = [t for t, r in windows if r < threshold]
    if not silent:
        return []

    gap = min_speech_ms / 1000
    min_dur = min_ms / 1000
    regions, start, prev = [], silent[0], silent[0]

    for t in silent[1:]:
        if t - prev > gap:
            if prev - start >= min_dur:
                regions.append((start, prev))
            start = t
        prev = t

    if prev - start >= min_dur:
        regions.append((start, prev))

    return regions


def match_segments(
    silence_regions: list[tuple[float, float]],
    segments: list[dict],
) -> list[dict]:
    """
    Match each segment to its silence cue.
    Uses expected cue duration (from transition type) as a discriminator
    to reject false positives.
    """
    results = []
    cursor = 0.0

    for seg in segments:
        expected_cue_dur = seg["cue_silence_ms"] / 1000
        expected_seg_dur = seg["duration_ms"] / 1000
        expected_seg_end = cursor + expected_seg_dur

        # Only consider silences after expected speech start
        # and within a generous window around expected cue position
        window_start = max(0, expected_seg_end - expected_seg_dur * 0.4)
        window_end   = expected_seg_end + expected_seg_dur * 0.6 + expected_cue_dur * 2

        candidates = [
            (s, e) for s, e in silence_regions
            if s >= window_start and s <= window_end
            and (e - s) >= expected_cue_dur * 0.35   # must be at least 35% of expected
        ]

        if candidates:
            # Pick closest to expected
            best = min(candidates, key=lambda r: abs(r[0] - expected_seg_end))
            sil_s, sil_e = best
            distance = abs(sil_s - expected_seg_end)
            tolerance = max(1.5, expected_seg_dur * 0.35)
            confidence = max(0.0, 1.0 - distance / tolerance)

            results.append({
                "event_id":       seg["event_id"],
                "event_type":     seg["event_type"],
                "transition":     seg["transition"],
                "offset_override": seg.get("offset_override", 0.0),
                "seg_end_s":      sil_s,
                "cue_start_s":    sil_s,
                "cue_end_s":      sil_e,
                "confidence":     round(confidence, 3),
                "matched":        True,
            })
            cursor = sil_e
        else:
            fallback = cursor + expected_seg_dur
            results.append({
                "event_id":       seg["event_id"],
                "event_type":     seg["event_type"],
                "transition":     seg["transition"],
                "offset_override": seg.get("offset_override", 0.0),
                "seg_end_s":      fallback,
                "cue_start_s":    None,
                "cue_end_s":      None,
                "confidence":     0.0,
                "matched":        False,
            })
            cursor = fallback + seg["cue_silence_ms"] / 1000
            console.print(f"  [yellow]⚠[/yellow]  [{seg['event_id']}] no cue — using estimate")

    return results


def lock_timeline(timeline: dict, results: list[dict], card: dict) -> dict:
    result_map = {r["event_id"]: r for r in results}
    card_events = {e["id"]: e for e in card.get("events", [])}

    VISUAL_DURATIONS = {
        "run_query": 1.5, "show_result": 1.5, "compare_results": 4.0,
        "zoom_result": 2.0, "highlight_section": 0.5, "show_schema": 1.5,
        "open_database": 1.0, "open_file": 0.5, "fade_out": 2.0, "pause": 1.0,
    }

    resolved: dict[str, float] = {}
    new_events = []

    for event in timeline["events"]:
        eid = event["id"]
        etype = event["type"]
        ce = card_events.get(eid, {})
        offset_override = float(ce.get("offset_override", 0.0))
        system_offset = EVENT_ACTION_OFFSET.get(etype, 0.4)
        total_offset = system_offset + offset_override

        if eid in result_map and result_map[eid]["matched"]:
            r = result_map[eid]
            fire_s = r["seg_end_s"] + total_offset
        else:
            fire_s = event["time_offset_ms"] / 1000

        resolved[eid] = fire_s
        new_events.append({**event, "time_offset_ms": max(0, int(fire_s * 1000))})

    new_events.sort(key=lambda e: e["time_offset_ms"])
    return {
        **timeline,
        "events": new_events,
        "narration_locked": True,
        "total_duration_ms": max(e["time_offset_ms"] for e in new_events) + 4000,
    }


@click.command()
@click.argument("card_path")
@click.option("--audio", default=None)
@click.option("--threshold", default=None, type=float)
@click.option("--verify", is_flag=True)
def align(card_path, audio, threshold, verify):
    """Align narration to timeline using variable silence-cue detection."""

    card_path = Path(card_path)
    lesson_dir = card_path.parent

    console.print(f"\n[bold green]WSDA Aligner v3 — Variable Cue Detection[/bold green]\n")

    with open(card_path) as f:
        card = yaml.safe_load(f)

    timeline_path = lesson_dir / "lesson_timeline.json"
    meta_path = lesson_dir / "narration_meta.json"
    audio_path = Path(audio) if audio else lesson_dir / "narration.wav"

    for p, name in [(timeline_path, "timeline"), (meta_path, "narration_meta"), (audio_path, "audio")]:
        if not p.exists():
            console.print(f"[red]Missing {name}: {p}[/red]"); return

    with open(timeline_path) as f:
        timeline = json.load(f)
    with open(meta_path) as f:
        meta = json.load(f)

    segments = meta["segments"]

    # Analyze audio
    console.print("[bold]Step 1 — Audio analysis[/bold]")
    samples, sr = read_wav(audio_path)
    duration_s = len(samples) / sr
    console.print(f"  Duration: {duration_s:.1f}s  |  {len(segments)} segments expected")

    windows = rms_windows(samples, sr)
    thr = threshold or auto_threshold(windows)
    console.print(f"  Silence threshold: {thr:.4f} (auto-calibrated)")

    min_silence = min(s["cue_silence_ms"] for s in segments) * 0.35
    silences = detect_silences(windows, thr, min_ms=int(min_silence))
    console.print(f"  Silence regions: {len(silences)} detected, {len(segments)} expected")

    # Match
    console.print(f"\n[bold]Step 2 — Cue matching[/bold]")
    results = match_segments(silences, segments)

    # Verify
    matched = [r for r in results if r["matched"]]
    avg_conf = sum(r["confidence"] for r in matched) / len(matched) if matched else 0
    low = [r for r in matched if r["confidence"] < MIN_CONFIDENCE]
    unmatched = [r for r in results if not r["matched"]]
    passed = len(unmatched) <= 1 and len(low) == 0

    # Display
    table = Table(title="Alignment", header_style="bold cyan")
    table.add_column("Event", style="dim")
    table.add_column("Type")
    table.add_column("Transition")
    table.add_column("Seg ends")
    table.add_column("Action fires")
    table.add_column("Conf")
    table.add_column("✓")

    for r in results:
        etype = r["event_type"]
        offset = EVENT_ACTION_OFFSET.get(etype, 0.4) + r.get("offset_override", 0.0)
        seg_end = r["seg_end_s"]
        fire_s = seg_end + offset
        mm, ss = divmod(fire_s, 60)

        seg_str = f"{int(seg_end//60):02d}:{seg_end%60:04.1f}" if seg_end else "—"
        fire_str = f"{int(mm):02d}:{ss:04.1f}"

        c = r["confidence"]
        if c >= MIN_CONFIDENCE:
            cs, st = f"[green]{c:.0%}[/green]", "[green]✓[/green]"
        elif c > 0:
            cs, st = f"[yellow]{c:.0%}[/yellow]", "[yellow]~[/yellow]"
        else:
            cs, st = "[red]—[/red]", "[red]✗[/red]"

        table.add_row(r["event_id"], etype, r["transition"], seg_str, fire_str, cs, st)

    console.print(table)

    status = "[green]PASSED[/green]" if passed else "[red]FAILED[/red]"
    console.print(f"\n  {status}  |  {len(matched)}/{len(results)} matched  |  avg confidence {avg_conf:.0%}")

    if not passed:
        console.print("\n[red]Alignment failed. Options:[/red]")
        console.print("  1. Re-generate audio (re-run narration/generate.py)")
        console.print(f"  2. Try --threshold {thr*0.75:.4f}")
        return

    # Lock and save
    console.print(f"\n[bold]Step 3 — Locking timeline[/bold]")
    locked = lock_timeline(timeline, results, card)

    locked_path = lesson_dir / "lesson_timeline_narrated.json"
    with open(locked_path, "w") as f:
        json.dump(locked, f, indent=2)

    with open(lesson_dir / "narration_alignment.json", "w") as f:
        json.dump({"results": results, "avg_confidence": avg_conf, "passed": passed}, f, indent=2)

    total_s = locked["total_duration_ms"] / 1000
    console.print(f"[green]✓[/green] Lesson: {total_s:.1f}s  |  Saved: [cyan]{locked_path}[/cyan]")
    console.print(f"\nRecord: [bold]python3 run.py {card_path} --narrated[/bold]")


if __name__ == "__main__":
    align()
