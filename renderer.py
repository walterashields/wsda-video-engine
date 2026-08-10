#!/usr/bin/env python3
"""
WSDA v4 Renderer — State-Driven, Scales to Any Topic

The viewer is a state machine. The renderer sends declarative state objects.
The viewer decides how to render based on mode, query count, viewport.

No per-video CSS. No hardcoded pixel math.
"""

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import yaml
from pathlib import Path
from playwright.async_api import async_playwright

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class EdgeTTS:
    def __init__(self, voice: str = "en-US-AriaNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate
    async def synthesize(self, text: str, out_path: Path):
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await communicate.save(str(out_path))


class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str,
                 model: str = "eleven_multilingual_v2"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    async def synthesize(self, text: str, out_path: Path):
        if not HAS_AIOHTTP:
            raise RuntimeError("pip install aiohttp")
        import aiohttp
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {"text": text, "model_id": self.model,
                   "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"ElevenLabs {resp.status}: {body}")
                out_path.write_bytes(await resp.read())


def _get_tts(voice: str = None) -> tuple:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
    if api_key and voice_id:
        print(f"[TTS] ElevenLabs: {voice_id}")
        return ElevenLabsTTS(api_key, voice_id), "elevenlabs"
    if HAS_EDGE_TTS:
        v = voice or "en-US-AriaNeural"
        print(f"[TTS] edge-tts: {v}")
        return EdgeTTS(voice=v), "edge"
    return None, "none"


def _extract_queries(sql_text: str) -> dict:
    queries = {}
    pattern = r"-- \[(query_\w+)\](.*?)(?=-- \[query_\w+\]|\Z)"
    for m in re.finditer(pattern, sql_text, re.DOTALL):
        ref = m.group(1).strip()
        body = m.group(2).strip()
        sql_start = re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP)\b',
                              body, re.IGNORECASE)
        if not sql_start:
            print(f"[sql-parser] {ref}: no SQL keyword")
            continue
        sql = body[sql_start.start():].strip()
        sql = sql.rstrip(';').strip()
        sql = re.sub(r"\s*--[^\n]*", "", sql)
        sql = "\n".join(line for line in sql.splitlines() if line.strip())
        if sql:
            queries[ref] = {"sql": sql, "columns": [], "rows": []}
            print(f"[sql-parser] {ref}: {sql.replace(chr(10), ' ')[:80]}...")
    return queries


class Renderer:
    def __init__(self, headless: bool = True, viewport: tuple = (1920, 1080),
                 voice: str = None):
        self.headless = headless
        self.vw, self.vh = viewport
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._elapsed = 0.0
        self._audio_segments = []
        self._current_db = None
        self._query_cache = {}
        self._sql_text = ""
        self.tts, self.tts_label = _get_tts(voice)

        # Viewer state
        self._state = {
            "mode": "single",
            "activeQuery": None,
            "dbName": None,
            "schema": [],
            "queries": {},
            "schemaExpanded": False,
            "activeTable": None,
            "callouts": [],
            "highlightedRows": []
        }

    def _state_diff(self, updates: dict) -> dict:
        """Merge updates into state and return the full state for the viewer."""
        self._state.update(updates)
        if "queries" in updates:
            self._state["queries"].update(updates["queries"])
        return self._state

    async def _send_state(self, updates: dict = None):
        """Send current state to viewer."""
        state = self._state_diff(updates or {})
        await self.page.evaluate(f"setScreenState({json.dumps(state)})")

    async def start(self, viewer_html: str, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": self.vw, "height": self.vh},
            record_video_dir=str(output_dir),
            record_video_size={"width": self.vw, "height": self.vh},
        )
        self.page = await self.context.new_page()
        await self.page.set_content(viewer_html)
        await self.page.wait_for_selector("#app", state="visible", timeout=5000)
        await asyncio.sleep(0.3)
        self._elapsed = 0.0
        self._audio_segments = []
        self._current_db = None
        self._query_cache = {}
        self._sql_text = ""
        self._state = {
            "mode": "single", "activeQuery": None, "dbName": None,
            "schema": [], "queries": {}, "schemaExpanded": False,
            "activeTable": None, "callouts": [], "highlightedRows": []
        }

    async def stop(self) -> Path:
        video_path = Path(await self.page.video.path())
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()
        return video_path

    def _read_schema(self, db_path: str) -> list:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = []
            for (name,) in cur.fetchall():
                cur.execute(f"PRAGMA table_info({name})")
                cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
                tables.append({"name": name, "columns": cols})
            conn.close()
            return tables
        except Exception as e:
            print(f"[schema] error: {e}")
            return []

    def _execute_sql(self, query: str) -> tuple:
        if not self._current_db:
            print("[sql] no DB")
            return [], []
        try:
            conn = sqlite3.connect(self._current_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            data = [[row[c] for c in columns] for row in rows]
            conn.close()
            print(f"[sql] {len(data)} rows")
            return columns, data
        except Exception as e:
            print(f"[sql] error: {e}")
            return [], []

    async def _speak(self, text: str, seg_dir: Path) -> Path:
        if not self.tts or not text:
            return None
        seg_path = seg_dir / f"seg_{len(self._audio_segments):03d}.mp3"
        await self.tts.synthesize(text, seg_path)
        return seg_path

    async def execute(self, event: dict, base_dir: Path, seg_dir: Path):
        etype = event.get("type", "")
        params = {k: v for k, v in event.items()
                  if k not in ("id", "type", "narration", "transition", "clears")}
        narration = event.get("narration", "")
        clears = event.get("clears", [])

        # Process clears — visual state only, NEVER wipe stored query data
        # (data is needed for compare_results later)
        if clears:
            for item in clears:
                if item == "result":
                    # Just deactivate current query visually; data stays in state
                    pass  # Viewer shows "No results" when activeQuery has no rows
                elif item == "highlight":
                    self._state["highlightedRows"] = []
                elif item == "annotations":
                    self._state["callouts"] = []
                elif item == "all":
                    self._state["highlightedRows"] = []
                    self._state["callouts"] = []
            await self._send_state()
            await asyncio.sleep(0.3)

        # Audio
        if narration and self.tts:
            audio_path = await self._speak(narration, seg_dir)
            if audio_path:
                self._audio_segments.append((self._elapsed, audio_path))

        sleep_dur = 0.2

        if etype == "show_title_card":
            await self.page.evaluate(f"""showTitleCard(
                {json.dumps(params.get('badge','SQL Lesson'))},
                {json.dumps(params.get('headline',''))},
                {json.dumps(params.get('sub',''))},
                {json.dumps(params.get('stakes',''))}
            )""")
            sleep_dur = 0.6

        elif etype == "hide_title_card":
            await self.page.evaluate("hideTitleCard()")
            sleep_dur = 0.6

        elif etype == "open_database":
            asset = params.get("asset", "")
            db_path = base_dir / asset if not Path(asset).is_absolute() else Path(asset)
            self._current_db = str(db_path)
            db_name = db_path.name
            schema = self._read_schema(self._current_db)
            await self._send_state({
                "dbName": db_name,
                "schema": schema
            })
            await self.page.evaluate(f"loadDatabase({json.dumps(db_name)})")
            if schema:
                await self.page.evaluate(f"renderSchema({json.dumps(schema)})")
            sleep_dur = 0.5

        elif etype == "show_schema":
            await self._send_state({"schemaExpanded": True})
            await self.page.evaluate("expandSchema()")
            sleep_dur = 0.8

        elif etype == "expand_schema":
            await self._send_state({"schemaExpanded": True})
            await self.page.evaluate("expandSchema()")
            sleep_dur = 0.4

        elif etype == "collapse_schema":
            await self._send_state({"schemaExpanded": False})
            await self.page.evaluate("collapseSchema()")
            sleep_dur = 0.4

        elif etype == "activate_table":
            name = params.get("table_name", "") or params.get("table", "")
            await self._send_state({"activeTable": name})
            await self.page.evaluate(f"activateTable({json.dumps(name)})")
            sleep_dur = 0.3

        elif etype == "open_file":
            asset = params.get("asset", "")
            sql_path = base_dir / asset if not Path(asset).is_absolute() else Path(asset)
            self._sql_text = sql_path.read_text()
            self._query_cache = _extract_queries(self._sql_text)
            await self._send_state({"queries": self._query_cache})
            await self.page.evaluate(f"setSQL({json.dumps(self._sql_text)})")
            sleep_dur = 0.5

        elif etype == "highlight_section":
            section = params.get("section", "")
            if section.startswith("query_"):
                await self._send_state({"activeQuery": section, "mode": "single"})
            sleep_dur = 0.3

        elif etype == "run_query":
            query_ref = params.get("query_ref", "")
            if query_ref:
                await self._send_state({"activeQuery": query_ref, "mode": "single"})

            cols, rows = [], []
            if query_ref and query_ref in self._query_cache:
                cols, rows = self._execute_sql(self._query_cache[query_ref]["sql"])
            elif params.get("columns") is not None:
                cols = params.get("columns", [])
                rows = params.get("rows", [])

            if query_ref and query_ref in self._state["queries"]:
                self._state["queries"][query_ref]["columns"] = cols
                self._state["queries"][query_ref]["rows"] = rows
                await self._send_state()
            sleep_dur = 0.8

        elif etype == "show_result":
            # If data provided, update; otherwise just emphasize current
            if params.get("columns") is not None and params.get("rows") is not None:
                qn = params.get("query_name", "")
                if qn and qn in self._state["queries"]:
                    self._state["queries"][qn]["columns"] = params["columns"]
                    self._state["queries"][qn]["rows"] = params["rows"]
                    await self._send_state()
            sleep_dur = 0.5

        elif etype == "highlight_row":
            self._state["highlightedRows"] = [{
                "index": params.get("row_index", 0),
                "color": params.get("color", "blue")
            }]
            await self._send_state()
            sleep_dur = 0.3

        elif etype == "annotate_cell":
            self._state["callouts"] = [{
                "row": params.get("row_index", 0),
                "col": params.get("col_index", 0),
                "text": params.get("text", "")
            }]
            await self._send_state()
            sleep_dur = 0.4

        elif etype == "clear_highlights":
            self._state["highlightedRows"] = []
            await self._send_state()
            sleep_dur = 0.2

        elif etype == "clear_annotations":
            self._state["callouts"] = []
            await self._send_state()
            sleep_dur = 0.2

        elif etype == "zoom_results":
            await self.page.evaluate("zoomResults()")
            sleep_dur = 0.4

        elif etype == "reset_zoom":
            await self.page.evaluate("resetZoom()")
            sleep_dur = 0.3

        elif etype == "fade_out":
            await self.page.evaluate("fadeOut()")
            sleep_dur = 1.5

        elif etype == "pause":
            sleep_dur = float(params.get("duration", 1.0))

        elif etype == "set_layout":
            mode = params.get("mode", "single")
            updates = {"mode": mode}
            # When switching to compare, include all query data so results
            # are visible immediately when narration says "show all three"
            if mode == "compare":
                updates["queries"] = dict(self._state["queries"])
                updates["activeQuery"] = None
            await self._send_state(updates)
            sleep_dur = 0.3

        elif etype == "compare_results":
            targets = params.get("targets", [])
            # Debug: show what data we have
            for ref in targets:
                q = self._state["queries"].get(ref, {})
                print(f"  [compare] {ref}: {len(q.get('rows', []))} rows, cols={q.get('columns', [])}")
            # Explicitly include all query data in state update
            await self._send_state({
                "mode": "compare",
                "activeQuery": None,
                "queries": dict(self._state["queries"])
            })
            sleep_dur = 1.0

        elif etype == "focus_callout":
            self._state["callouts"] = [{
                "row": params.get("row_index", 0),
                "col": params.get("col_index", 0),
                "text": params.get("text", "")
            }]
            await self._send_state()
            sleep_dur = 0.4

        else:
            print(f"[warn] unknown event type: {etype}")
            sleep_dur = 0.2

        await asyncio.sleep(sleep_dur)
        self._elapsed += sleep_dur


async def _build_audio_track(segments, seg_dir: Path, output_dir: Path) -> Path:
    if not segments:
        return None
    out_audio = output_dir / "narration.mp3"
    wav_files = []
    for i, (start, path) in enumerate(segments):
        wav = seg_dir / f"norm_{i:03d}.wav"
        subprocess.run(["ffmpeg", "-y", "-i", str(path), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True, capture_output=True)
        wav_files.append((start, wav))
    final_wavs = []
    prev_end = 0.0
    for start, wav in wav_files:
        gap = max(0.0, start - prev_end)
        if gap > 0.05:
            silence = seg_dir / f"sil_{len(final_wavs):03d}.wav"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(gap), "-acodec", "pcm_s16le", str(silence)], check=True, capture_output=True)
            final_wavs.append(silence)
        final_wavs.append(wav)
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(wav)], capture_output=True, text=True, check=True)
        prev_end = start + float(result.stdout.strip())
    list_file = output_dir / "wav_list.txt"
    list_file.write_text("\n".join(f"file '{w}'" for w in final_wavs))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "2", str(out_audio)], check=True, capture_output=True)
    return out_audio


async def render_card(card_path: Path, viewer_html: str, output_dir: Path,
                      headless: bool = True, voice: str = None) -> Path:
    with open(card_path) as f:
        card = yaml.safe_load(f)
    base_dir = card_path.parent
    events = card.get("events", [])
    print(f"\nWSDA v4 — {card.get('title', 'Untitled')}")
    print(f"Events: {len(events)} | Output: {output_dir}")
    seg_dir = output_dir / ".audio_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(headless=headless, voice=voice)
    await renderer.start(viewer_html, output_dir)
    for i, event in enumerate(events):
        eid = event.get("id", f"evt_{i}")
        etype = event.get("type", "")
        narr = event.get("narration", "")[:50]
        print(f"  {i+1:02d}/{len(events)} {eid:<20} {etype:<20} {narr}...")
        await renderer.execute(event, base_dir, seg_dir)
    webm_path = await renderer.stop()
    print(f"\nVideo recorded: {webm_path}")
    if renderer.tts and renderer._audio_segments:
        print(f"Building audio ({len(renderer._audio_segments)} segments)...")
        audio_path = await _build_audio_track(renderer._audio_segments, seg_dir, output_dir)
    else:
        audio_path = None
    mp4_path = output_dir / f"{card.get('lesson_id', 'lesson')}.mp4"
    if audio_path and audio_path.exists():
        subprocess.run(["ffmpeg", "-y", "-i", str(webm_path), "-i", str(audio_path), "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-shortest", str(mp4_path)], check=True, capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", str(webm_path), "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4_path)], check=True, capture_output=True)
    webm_path.unlink()
    print(f"MP4 saved: {mp4_path}")
    return mp4_path
