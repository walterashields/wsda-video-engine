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

import asyncio
import json, os, re, struct, subprocess, sys, wave
from pathlib import Path
import click, yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))
console = Console()
SAMPLE_RATE = 44100

ELEVENLABS_CONFIG_PATH = Path(__file__).parent.parent / "config" / "elevenlabs.yml"


def _load_elevenlabs_config() -> dict:
    """Root-caused 2026-08-16: a render fell back to edge-tts even though
    ElevenLabs was "configured" -- the ELEVENLABS_API_KEY environment
    variable held a stale/invalid key (confirmed directly against
    ElevenLabs' own API: 401 Unauthorized, "Invalid API key"), while
    config/elevenlabs.yml -- a file that already exists in this repo,
    with a header comment stating it's specifically "for narration" --
    held a DIFFERENT, currently-valid key the whole time, confirmed live
    with a real 200 response and real audio bytes back. The code never
    actually read this file; only the environment variable (or an
    explicit CLI flag) was ever checked, so a correct, working credential
    sitting right there in the repo was silently ignored in favor of
    whatever the shell environment happened to hold. This is the reason
    the file exists at all -- wiring it up here, not just fixing the one
    stale env var for this one shell session, so the same drift (a
    correct key in the file, a stale one in whatever environment
    actually runs this) doesn't silently recur the next time the
    environment differs from the file."""
    if not ELEVENLABS_CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(ELEVENLABS_CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError:
        return {}


def get_video_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def synthesize(text: str, path: Path, voice: str, rate: int,
               el_key=None, el_voice=None) -> str:
    """Synthesize a WAV clip. ElevenLabs is tried first; if it fails, fall
    back to edge-tts, then to macOS say. Returns which tier actually
    produced the audio ("elevenlabs" | "edge-tts" | "say") so a caller can
    log what really happened for this clip instead of assuming the
    preferred tier worked. If every tier fails, raises RuntimeError with
    all three failure reasons -- this must never return silently without
    either a tier name or an exception, since a caller treating "no
    exception" as "audio exists" is exactly how a silent clip slips
    through into a "successful" render."""
    failures = []

    if el_key and el_voice:
        try:
            import urllib.request, json as _j
            payload = _j.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
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
            return "elevenlabs"
        except Exception as e:
            failures.append(f"ElevenLabs: {e}")
            console.print(f"  [yellow]ElevenLabs failed ({e}), trying fallback...[/yellow]")

    # Fallback 1: edge-tts (cross-platform, no API key)
    try:
        import edge_tts
        # edge-tts default speed is roughly 180 wpm; express requested rate as %
        rate_pct = int(round((rate - 180) / 180 * 100))
        edge_voice = voice if voice and "-" in voice else "en-US-AriaNeural"
        communicate = edge_tts.Communicate(text, edge_voice, rate=f"{rate_pct:+d}%")
        mp3 = path.with_suffix(".mp3")
        asyncio.run(communicate.save(str(mp3)))
        subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-ar", str(SAMPLE_RATE),
                        "-ac", "1", str(path)], check=True, capture_output=True)
        mp3.unlink(missing_ok=True)
        return "edge-tts"
    except Exception as e:
        failures.append(f"edge-tts: {e}")

    # Fallback 2: macOS say
    try:
        aiff = path.with_suffix(".aiff")
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff), "-ar", str(SAMPLE_RATE),
                        "-ac", "1", str(path)], check=True, capture_output=True)
        aiff.unlink(missing_ok=True)
        return "say"
    except Exception as e:
        failures.append(f"say: {e}")

    raise RuntimeError("all TTS tiers failed -- " + "; ".join(failures))


def _verify_audio(path: Path) -> tuple[bool, str]:
    """Confirm the rendered file actually has audible sound, not just an
    audio stream that exists but is silent. A muxed AAC track full of
    zeros (e.g. every clip failed synthesis in a way that didn't raise,
    or build_track()'s buffer never got any clips placed into it) would
    still probe as "has an audio stream" and exit ffmpeg 0 -- this checks
    the actual signal, which is the only thing that tells you whether a
    viewer will hear anything."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if not probe.stdout.strip():
        return False, "no audio stream found in the output file"

    vol = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)\s*dB", vol.stderr)
    if not m or m.group(1) == "-inf":
        return False, "audio stream is present but completely silent (mean volume -inf dB)"
    mean_db = float(m.group(1))
    if mean_db < -50.0:
        return False, f"audio stream is present but near-silent (mean volume {mean_db:.1f} dB)"
    return True, f"mean volume {mean_db:.1f} dB"


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
    # Priority: explicit CLI flag, then config/elevenlabs.yml (this
    # project's own dedicated credential file -- see
    # _load_elevenlabs_config's docstring for why this is checked before
    # the environment), then the environment variables as a last resort.
    _el_config = _load_elevenlabs_config()
    _el_key   = el_key   or _el_config.get("api_key")   or _os.environ.get("ELEVENLABS_API_KEY")
    _el_voice = el_voice or _el_config.get("voice_id")  or _os.environ.get("ELEVENLABS_VOICE_ID")
    if elevenlabs and not (_el_key and _el_voice):
        console.print("[red]--elevenlabs requires an API key and voice ID, from --el-key/--el-voice, "
                       f"{ELEVENLABS_CONFIG_PATH}, or ELEVENLABS_API_KEY/ELEVENLABS_VOICE_ID[/red]")
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
    synth_failures = []
    tier_counts = {"elevenlabs": 0, "edge-tts": 0, "say": 0}

    # Parallelized 2026-08-16 (real bottleneck, confirmed by measuring a
    # real render's timing breakdown, not guessed): each clip's synthesis
    # is a blocking network call to ElevenLabs/edge-tts/say, and clips are
    # fully independent of each other -- text and target wav path are
    # per-clip, nothing shared. Running them one at a time in a for loop
    # meant total synthesis time was the SUM of every clip's network
    # latency; a thread pool (these are I/O-bound calls, not CPU-bound)
    # cuts that to roughly the slowest clip plus overhead. Capped at 4
    # concurrent workers deliberately, not unbounded -- firing 10+
    # simultaneous requests at ElevenLabs risks tripping a rate limit
    # that firing them one at a time never would, and this is a real
    # speedup either way. Results are collected keyed by index and
    # printed back out in original schedule order afterward, so the
    # console output and tier-usage summary are unchanged in shape from
    # the sequential version -- only the wall-clock time changes.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _synth_one(i, entry):
        wav = work_dir / f"clip_{i:03d}_{entry['event_id']}.wav"
        tier = synthesize(entry["text"], wav, voice, rate,
                           el_key=_el_key if use_el else None,
                           el_voice=_el_voice if use_el else None)
        return i, wav, tier

    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_synth_one, i, entry): (i, entry) for i, entry in enumerate(schedule)}
        for future in as_completed(futures):
            i, entry = futures[future]
            try:
                _, wav, tier = future.result()
                results[i] = (wav, tier, None)
            except Exception as e:
                results[i] = (None, None, e)

    for i, entry in enumerate(schedule):
        wav, tier, error = results[i]
        if error is None:
            tier_counts[tier] += 1
            entry["wav_path"] = str(wav)
            entry["tier"] = tier
            dur = wav_duration_s(wav)
            words = len(entry["text"].split())
            console.print(
                f"  {entry['start_s']:5.1f}s  {dur:.1f}s  "
                f"[dim]{words}w[/dim]  [cyan]{tier:>10}[/cyan]  {entry['text'][:45]}"
            )
        else:
            console.print(f"  [red]Failed {entry['event_id']}: {error}[/red]")
            synth_failures.append((entry['event_id'], str(error)))

    # Which tier actually produced this run's audio, not just which one was
    # requested -- ElevenLabs being configured doesn't mean it's the tier
    # that fired for any given clip.
    console.print(
        f"\n[bold]TTS tier usage:[/bold] "
        f"ElevenLabs {tier_counts['elevenlabs']}, "
        f"edge-tts {tier_counts['edge-tts']}, "
        f"say {tier_counts['say']}, "
        f"failed {len(synth_failures)} (of {len(schedule)} clips)"
    )

    # A completely (or mostly) silent video that still reports "Production
    # complete" is worse than an obvious crash — it wastes a full recording
    # cycle and looks like success until someone actually watches it. Halt
    # here instead of proceeding to render.
    if synth_failures:
        failure_rate = len(synth_failures) / len(schedule)
        if failure_rate >= 0.5:
            console.print(Panel(
                f"[bold red]Narration synthesis failed for {len(synth_failures)} "
                f"of {len(schedule)} clips ({failure_rate:.0%}).[/bold red]\n\n"
                f"This would produce a silent or near-silent video. Halting "
                f"instead of rendering one and calling it complete.\n\n"
                f"First failure: {synth_failures[0][0]} — {synth_failures[0][1]}\n\n"
                + ("This looks like an ElevenLabs authentication or quota "
                   "problem (check your API key and account) — it's an "
                   "account issue, not a code bug."
                   if "401" in synth_failures[0][1] or "Unauthorized" in synth_failures[0][1]
                   else "Check the errors above for the specific cause."),
                title="Narration synthesis failed",
                border_style="red",
            ))
            sys.exit(1)
        else:
            console.print(
                f"  [yellow]Warning: {len(synth_failures)} of {len(schedule)} "
                f"clips failed to synthesize. Proceeding, but this video will "
                f"have gaps of silence at: {', '.join(f[0] for f in synth_failures)}[/yellow]"
            )

    # Build and render
    # ── Auto QA before render ──────────────────────────────────
    console.print(f"\n[bold]Running QA checks...[/bold]")
    from narration.qa import qa as run_qa
    from click.testing import CliRunner
    runner_cli = CliRunner()
    fmt = card.get("format", "lesson")
    qa_result = runner_cli.invoke(run_qa, [
        str(audit_path),
        str(card_path),
        "--work-dir", str(work_dir),
        "--fix",
        "--format", fmt,
    ])
    console.print(qa_result.output)

    # Check if QA found CRITICAL timing issues.
    # Minor overruns (<5s) on a MID-lesson event are allowed -- the audio
    # bleeds slightly into the following event's own dead air, which is
    # recoverable. That tolerance does NOT apply to the lesson's last
    # narrated event (root-caused 2026-08-16, "video cut off at the end"):
    # there is no following dead air to bleed into there, only the actual
    # end of the recorded video -- render()'s ffmpeg call hard-caps
    # output length to the raw recording's real duration, so ANY overrun
    # on the closing line gets silently sliced off mid-sentence rather
    # than "mostly working." Confirmed live: a 1.7s overrun (well under
    # the general 5s tolerance) on a lesson's closing clip still produced
    # a video that stopped before the lesson's actual ending, with no
    # warning at all under the old blanket 5s rule.
    last_narrated_id = next(
        (e.get("id") for e in reversed(card_events) if (e.get("narration") or "").strip()),
        None,
    )
    import re as _re
    critical = False
    for m in _re.finditer(r'\[TIMING\] (\S+)\s*\n\s*Problem: .*? by ([\d.]+)s', qa_result.output):
        event_id, overrun = m.group(1), float(m.group(2))
        if overrun > 5.0 or (event_id == last_narrated_id and overrun > 0):
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

    # A "successful" render with no audible sound is worse than a crash:
    # it exits 0, looks complete, and wastes a full recording cycle before
    # anyone notices by actually watching it. Verify the muxed output for
    # real instead of trusting ffmpeg's exit code alone.
    console.print(f"\n[bold]Verifying rendered audio...[/bold]")
    audio_ok, audio_detail = _verify_audio(output)
    if not audio_ok:
        console.print(Panel(
            f"[bold red]Render completed but the output has no audible "
            f"audio track.[/bold red]\n\n"
            f"{audio_detail}\n\n"
            f"This is a hard failure, not a warning -- not reporting "
            f"success for a silent video.",
            title="Audio verification failed", border_style="red",
        ))
        sys.exit(1)

    console.print(Panel(
        f"[bold green]Done.[/bold green]\n\nVideo: [cyan]{output}[/cyan]\n"
        f"Audio: [green]{audio_detail}[/green]",
        title="Complete", border_style="green"
    ))


if __name__ == "__main__":
    cli()
