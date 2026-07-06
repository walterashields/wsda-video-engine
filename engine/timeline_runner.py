"""
WSDA Video Engine — Timeline Runner v9

Rule: Visual fires. Visual settles. Audio plays.

Execution per event:
  1. Approach (cursor moves)
  2. Clear stale state
  3. Focus (highlight)
  4. Action (run query, switch layout, etc.)
  5. Visual settle — fixed pause so learner sees it
  6. RECORD: current timestamp → this is where audio segment goes
  7. Continue to next event

After recording:
  Runner writes sync.json: [{event_id, segment_starts_at_ms, segment_file}]
  mix.py uses FFmpeg adelay to place each segment at exact timestamp
  run.py calls FFmpeg to mix assembled audio into MP4
"""

import asyncio
import json
import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

from engine.schemas import (
    LessonTimeline, TimelineEvent, AuditLog, EventResult,
    EVENT_APPROACH_LEAD,
)
from adapters.sql_viewer_adapter import SQLViewerAdapter
from adapters.chat_demo_adapter import ChatDemoAdapter

console = Console()

PREROLL_TYPES = {"open_database", "open_file", "show_schema"}

# How long after visual action before narration begins (seconds)
# This is the "let it land" pause the learner needs
VISUAL_SETTLE = {
    "open_view":          1.2,
    "highlight_section": 0.6,
    "run_query":         1.0,
    "show_result":       0.5,
    "compare_results":   1.2,
    "zoom_result":       0.5,
    "set_layout":        0.8,
    "highlight_result":  0.5,
    "focus_callout":     0.4,
    "fade_out":          0.0,
    "pause":             0.0,
    "activate_table":    0.4,
}


def extract_segment_wav(
    full_wav: Path,
    seg_start_ms: int,
    seg_end_ms: int,
    out_path: Path,
) -> bool:
    """Extract one narration segment from the combined WAV file."""
    try:
        with wave.open(str(full_wav), 'rb') as w:
            sr  = w.getframerate()
            sw  = w.getsampwidth()
            nc  = w.getnchannels()
            all_pcm = w.readframes(w.getnframes())

        start_byte = int(seg_start_ms / 1000 * sr) * sw * nc
        end_byte   = int(seg_end_ms   / 1000 * sr) * sw * nc
        seg_pcm    = all_pcm[start_byte:end_byte]

        with wave.open(str(out_path), 'wb') as w:
            w.setnchannels(nc)
            w.setsampwidth(sw)
            w.setframerate(sr)
            w.writeframes(seg_pcm)
        return True
    except Exception as e:
        console.print(f"[yellow]⚠ Could not extract segment: {e}[/yellow]")
        return False


class TimelineRunner:

    def __init__(
        self,
        timeline: LessonTimeline,
        rehearsal: bool = False,
        speed: float = 1.0,
        resume_from: str | None = None,
        settings: dict | None = None,
        audio_path: Path | None = None,
    ):
        self.timeline    = timeline
        self.rehearsal   = rehearsal
        self.speed       = 2.0 if rehearsal else speed
        self.resume_from = resume_from
        self.settings    = settings or {}
        self.audio_path  = audio_path

        self.audit = AuditLog(
            lesson_id=timeline.lesson_id,
            run_started=datetime.now().isoformat(),
            rehearsal_mode=rehearsal,
            total_events=len(timeline.events),
        )

        self._adapter: SQLViewerAdapter | ChatDemoAdapter | None = None
        self._adapter_type: str = "sql_viewer"
        self._flask: subprocess.Popen | None = None
        self._t0: float = 0.0
        self._video_dir: Path | None = None
        self._recorded_video_path: Path | None = None

        # Sync data — written after recording
        self._sync_entries: list[dict] = []

    @property
    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    async def run(self) -> AuditLog:
        mode = "[yellow]REHEARSAL[/yellow]" if self.rehearsal else "[green]RECORDING[/green]"
        console.print(Panel(
            f"[bold]{self.timeline.title}[/bold]\n"
            f"Mode: {mode}  |  Events: {len(self.timeline.events)}",
            title="WSDA Video Engine v9",
            border_style="green",
        ))
        try:
            await self._start_flask()
            await self._run_browser()
        except Exception as e:
            console.print(f"\n[red bold]Run failed:[/red bold] {e}")
            raise
        finally:
            await self._stop_flask()
            self._finalize_audit()
        return self.audit

    async def _start_flask(self):
        console.print("\n[dim]Starting SQL viewer...[/dim]")
        web_app = Path(__file__).parent.parent / "web" / "app.py"
        import tempfile
        self._flask_log = tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False)
        self._flask = subprocess.Popen(
            [sys.executable, str(web_app)],
            stdout=self._flask_log,
            stderr=self._flask_log,
        )
        await asyncio.sleep(3.0)  # extra time for chat demo
        # Check Flask is actually running
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:5050/", timeout=2)
            console.print("[green]✓[/green] SQL viewer ready")
        except Exception as fe:
            log_content = open(self._flask_log.name).read()
            console.print(f"[red]Flask failed to start: {fe}[/red]")
            console.print(f"[red]Flask log:\n{log_content}[/red]")
            raise RuntimeError(f"Flask startup failed: {log_content[:500]}")

    async def _stop_flask(self):
        if self._flask:
            self._flask.terminate()
            self._flask = None

    async def _run_browser(self):
        cfg = self.settings.get("browser", {})
        vw  = cfg.get("viewport_width", 1280)
        vh  = cfg.get("viewport_height", 720)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            all_events = self.timeline.events
            preroll    = [e for e in all_events if e.type in PREROLL_TYPES]
            lesson     = [e for e in all_events if e.type not in PREROLL_TYPES]

            # ── Pre-roll ────────────────────────────────────────
            console.print("\n[dim]Pre-roll: loading lesson state...[/dim]")
            ctx  = await browser.new_context(viewport={"width": vw, "height": vh})
            page = await ctx.new_page()
            if self.timeline.adapter_type == "chat_demo":
                self._adapter = ChatDemoAdapter(page)
                self._adapter_type = "chat_demo"
            else:
                self._adapter = SQLViewerAdapter(page, rehearsal=self.rehearsal)
                self._adapter_type = "sql_viewer"
            await self._adapter.navigate()
            for e in preroll:
                await self._adapter.action(e.type, e.params)
                await asyncio.sleep(0.3)
            console.print("[green]✓[/green] Pre-roll complete")
            await asyncio.sleep(0.3)
            await ctx.close()

            # ── Recording context ───────────────────────────────
            rec_args = {"viewport": {"width": vw, "height": vh}}
            if self._video_dir:
                rec_args["record_video_dir"]  = str(self._video_dir)
                rec_args["record_video_size"] = {"width": vw, "height": vh}

            rec_ctx  = await browser.new_context(**rec_args)
            rec_page = await rec_ctx.new_page()
            if self.timeline.adapter_type == "chat_demo":
                self._adapter = ChatDemoAdapter(rec_page)
                self._adapter_type = "chat_demo"
            else:
                self._adapter = SQLViewerAdapter(rec_page, rehearsal=self.rehearsal)
                self._adapter_type = "sql_viewer"
            await self._adapter.navigate()

            # Restore state quickly
            for e in preroll:
                await self._adapter.action(e.type, e.params)

            # Hold so first recorded frame is meaningful
            await asyncio.sleep(1.5)

            # ── t=0 ─────────────────────────────────────────────
            self._t0 = time.monotonic()
            console.print("[green]▶[/green] Recording started — t=0")

            await self._execute_lesson(lesson)

            # End: brief hold then stop
            await asyncio.sleep(1.5)

            if self._video_dir:
                self._recorded_video_path = await rec_page.video.path()

            await rec_ctx.close()
            await browser.close()

    async def _execute_lesson(self, events: list[TimelineEvent]):
        """
        Visual-first execution.
        For each event:
          fire visual → settle → record audio timestamp → continue
        """
        # Load narration metadata
        seg_map = self._load_segment_map()
        total   = len(events)

        if seg_map:
            console.print(f"  [dim]Narration segments available: {list(seg_map.keys())}[/dim]")
        else:
            console.print(f"  [yellow]⚠ No narration segment map loaded[/yellow]")

        for i, event in enumerate(events):
            t = self._elapsed_ms / 1000
            mm, ss = divmod(t, 60)
            console.print(
                f"  [dim]{i+1:02d}/{total}[/dim] "
                f"[cyan]{int(mm):02d}:{ss:04.1f}[/cyan] "
                f"[bold]{event.type}[/bold]"
                + (f" → {event.target}" if event.target else "")
            )

            started_ms = self._elapsed_ms
            success    = True
            error_msg  = None

            try:
                # Approach
                await self._phase_approach(event)

                # Clear stale state
                if event.clears:
                    await self._adapter.clear(event.clears)
                    await asyncio.sleep(0.1)

                # Focus + Action
                await self._phase_focus(event)
                await self._phase_action(event)

                # For pause events, sleep the full duration
                if event.type == "pause":
                    duration = event.params.get("duration", 0)
                    if duration and duration > 0:
                        await asyncio.sleep(float(duration) / self.speed)

                # Visual settle — learner sees it
                settle = VISUAL_SETTLE.get(event.type, 0.4) / self.speed
                if settle > 0:
                    await asyncio.sleep(settle)

                # Record timestamp — this is where audio goes
                audio_start_ms = self._elapsed_ms

                # Log narration timing
                if event.narration and seg_map and event.id in seg_map:
                    seg = seg_map[event.id]
                    seg_dur_ms = seg["seg_end_ms"] - seg["seg_start_ms"]
                    self._sync_entries.append({
                        "event_id":             event.id,
                        "segment_starts_at_ms": audio_start_ms,
                        "seg_start_ms":         seg["seg_start_ms"],
                        "seg_end_ms":           seg["seg_end_ms"],
                        "seg_duration_ms":      seg_dur_ms,
                    })
                    console.print(
                        f"         [dim]audio @ {audio_start_ms/1000:.1f}s "
                        f"({seg_dur_ms/1000:.1f}s)[/dim]"
                    )
                    # Wait for narration duration before next event
                    await asyncio.sleep(seg_dur_ms / 1000 / self.speed)

                # Brief breath between events
                await asyncio.sleep(0.3 / self.speed)

            except Exception as e:
                success   = False
                error_msg = str(e)
                console.print(f"         [yellow]⚠ {e}[/yellow]")

            self.audit.events.append(EventResult(
                event_id=event.id,
                type=event.type,
                started_at_ms=started_ms,
                completed_at_ms=self._elapsed_ms,
                success=success,
                error=error_msg,
            ))
            if success:
                self.audit.successful_events += 1
            else:
                self.audit.failed_events += 1

    def _load_segment_map(self) -> dict | None:
        """Load narration segment boundaries from metadata."""
        if not self.audio_path or self.rehearsal:
            return None
        meta_path = self.audio_path.parent / "narration_meta.json"
        if not meta_path.exists():
            return None
        with open(meta_path) as f:
            meta = json.load(f)
        return {s["event_id"]: s for s in meta.get("segments", [])}

    def write_sync_file(self, sync_path: Path, seg_dir: Path) -> Path | None:
        """
        Extract individual segment WAVs and write sync.json.
        Called by run.py after recording completes.
        """
        if not self._sync_entries or not self.audio_path:
            return None

        seg_dir.mkdir(exist_ok=True)
        output_entries = []

        for entry in self._sync_entries:
            seg_path = seg_dir / f"seg_{entry['event_id']}.wav"
            ok = extract_segment_wav(
                self.audio_path,
                entry["seg_start_ms"],
                entry["seg_end_ms"],
                seg_path,
            )
            if ok:
                output_entries.append({
                    "event_id":             entry["event_id"],
                    "segment_starts_at_ms": entry["segment_starts_at_ms"],
                    "segment_file":         str(seg_path),
                })

        if not output_entries:
            return None

        with open(sync_path, "w") as f:
            json.dump(output_entries, f, indent=2)

        console.print(f"[green]✓[/green] Sync file: {len(output_entries)} segments")
        return sync_path

    async def _phase_approach(self, event: TimelineEvent):
        target_map = {
            "highlight_section": f"sql_{event.params.get('section', 'query_1')}",
            "run_query":         "results_area",
            "show_result":       "results_top",
            "highlight_result":  "results_top",
            "compare_results":   "compare_panel_2",
            "zoom_result":       "results_center",
            "set_layout":        "neutral",
            "activate_table":    "schema_panel",
        }
        target = target_map.get(event.type)
        if target:
            lead = EVENT_APPROACH_LEAD.get(event.type, 0.4) / self.speed
            await self._adapter.approach(target, lead)

    async def _phase_focus(self, event: TimelineEvent):
        await self._adapter.focus(event.target or "", {
            "type":      event.type,
            "section":   event.params.get("section", ""),
            "query_ref": event.params.get("query_ref", ""),
            "table":     event.params.get("target", ""),
        })

    async def _phase_action(self, event: TimelineEvent):
        await self._adapter.action(event.type, event.params)

    def _finalize_audit(self):
        self.audit.run_completed = datetime.now().isoformat()
        console.print(
            f"\n[bold]Complete.[/bold] "
            f"{self.audit.successful_events}/{self.audit.total_events} events"
        )
