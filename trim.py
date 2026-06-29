#!/usr/bin/env python3
"""
WSDA Trim
Post-processing: trim blank opening and dead tail from a narrated video.
Uses the audio track to find where speech actually starts and ends.
"""

import subprocess, sys, wave, struct, math
from pathlib import Path

def get_audio_bounds(mp4: Path) -> tuple[float, float]:
    """Find first and last second with speech."""
    wav = mp4.with_suffix(".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp4), "-vn", "-ar", "16000", "-ac", "1", str(wav)],
        capture_output=True, check=True
    )
    with wave.open(str(wav), 'rb') as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    wav.unlink(missing_ok=True)

    samples = [s/32768.0 for s in struct.unpack(f"<{len(raw)//2}h", raw)]
    window = sr
    rms_by_second = []
    for i in range(0, len(samples) - window, window):
        chunk = samples[i:i+window]
        rms = math.sqrt(sum(s*s for s in chunk) / len(chunk))
        rms_by_second.append(rms)

    THRESHOLD = 0.008
    speech_seconds = [i for i, r in enumerate(rms_by_second) if r > THRESHOLD]

    if not speech_seconds:
        return 0.0, len(rms_by_second)

    first = max(0, speech_seconds[0] - 1)   # 1s before first speech
    last  = min(len(rms_by_second), speech_seconds[-1] + 3)  # 3s after last speech
    return float(first), float(last)


def trim(mp4: Path, output: Path):
    start, end = get_audio_bounds(mp4)
    duration = end - start
    print(f"  Speech: {start:.1f}s — {end:.1f}s  ({duration:.1f}s)")

    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(mp4),
        "-t", str(duration),
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-acodec", "aac", "-ab", "192k",
        "-movflags", "+faststart",
        str(output)
    ], check=True, capture_output=True)
    print(f"  Output: {output}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trim.py input.mp4 [output.mp4]")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else \
          inp.parent / f"{inp.stem}_trimmed.mp4"

    print(f"Trimming: {inp.name}")
    trim(inp, out)
    print("Done.")
