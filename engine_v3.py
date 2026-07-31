#!/usr/bin/env python3
"""
WSDA v3 -- Real-Time Video Engine with Audio
"""

import asyncio
import os
import shutil
import logging
import socket
import subprocess
import sys
import time
import re
from pathlib import Path
from typing import List
from playwright.async_api import async_playwright
from config import VideoConfig, SCENES_CONFIG
from browser_controller import BrowserController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("wsda.engine")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class FlaskAppServer:
    def __init__(self, app_path: Path):
        self.app_path = app_path
        self.port = None
        self.url = None
        self.proc = None

    def start(self):
        env = os.environ.copy()
        env["FLASK_RUN_PORT"] = "0"
        env["FLASK_ENV"] = "development"

        strategies = [
            {"cmd": ["python", str(self.app_path)], "cwd": ".", "desc": "python web/app.py"},
            {"cmd": ["python", "-m", "flask", "--app", str(self.app_path), "run"], "cwd": ".", "desc": "flask --app web/app.py run"},
        ]

        for strategy in strategies:
            try:
                logger.info(f"Trying: {strategy['desc']}")
                self.proc = subprocess.Popen(
                    strategy["cmd"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    cwd=strategy["cwd"],
                )
                port, url = self._detect_port(timeout=15)
                if port:
                    self.port = port
                    self.url = url
                    logger.info(f"App started: {self.url}")
                    return
                self._kill_proc()
            except Exception as e:
                logger.warning(f"Strategy failed: {strategy['desc']} -- {e}")
                self._kill_proc()
                continue

        raise RuntimeError("Could not start web/app.py. Start it manually and set ide_url in config.py.")

    def _detect_port(self, timeout: float):
        import select
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            if self.proc.poll() is not None:
                remaining = self.proc.stdout.read()
                logger.error(f"App crashed. Output:\n{buffer}{remaining}")
                return None, None
            readable, _, _ = select.select([self.proc.stdout], [], [], 0.5)
            if readable:
                line = self.proc.stdout.readline()
                if line:
                    buffer += line
                    for pattern in [r"Running on (http://[\d\.]+:(\d+))", r"Uvicorn running on (http://[\d\.]+:(\d+))"]:
                        match = re.search(pattern, line)
                        if match:
                            url, port_str = match.group(1), match.group(2)
                            port = int(port_str)
                            if self._is_port_open(port):
                                return port, url
            if time.time() - start > 3:
                for test_port in [5000, 8000, 3000, 8080, 5050]:
                    if self._is_port_open(test_port):
                        return test_port, f"http://127.0.0.1:{test_port}"
        return None, None

    def _is_port_open(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False

    def _kill_proc(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def stop(self):
        self._kill_proc()
        logger.info("App server stopped")


class WSDAEngineV3:
    def __init__(self, config: VideoConfig):
        self.config = config
        self.temp_dir = Path(config.temp_dir)
        self.server = None

    async def run(self):
        try:
            self._setup_temp()
            ide_url = await self._resolve_ide_url()

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    record_video_dir=str(self.temp_dir / "recordings"),
                    viewport={"width": self.config.width, "height": self.config.height}
                )
                page = await context.new_page()
                await page.goto(ide_url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                controller = BrowserController(page)
                audio_clips = []
                cumulative_time = 0.0

                for scene in self.config.scenes:
                    narration = " ".join([
                        o.content for o in scene.overlays
                        if o.type in ("text", "badge", "highlight", "comparison")
                    ])

                    audio_path = self.temp_dir / "audio" / f"{scene.id}.mp3"
                    audio_duration = 0.0
                    
                    if narration.strip():
                        logger.info(f"Generating TTS for [{scene.id}]: '{narration[:60]}...'")
                        from tts_engine import generate_narration
                        generate_narration(narration.strip(), str(audio_path))
                        audio_duration = self._get_audio_duration(str(audio_path))
                        logger.info(f"  Audio duration: {audio_duration:.2f}s")
                    else:
                        logger.info(f"Scene [{scene.id}] has no narration text")

                    action_time = self._estimate_action_time(scene)
                    scene_duration = max(audio_duration, action_time, scene.duration)
                    logger.info(f"Scene [{scene.id}] final duration: {scene_duration:.1f}s")

                    audio_clips.append({
                        "path": str(audio_path) if narration.strip() and audio_path.exists() else None,
                        "start": cumulative_time,
                        "duration": scene_duration
                    })

                    await controller.clear_overlays()

                    elapsed = 0.0
                    for action in scene.ui_actions:
                        if action.action == "load_db":
                            await controller.load_db(action.value)
                            elapsed += 1.5
                        elif action.action == "open_schema":
                            await controller.open_schema()
                            elapsed += 2.0
                        elif action.action == "clear_query":
                            await controller.clear_editor()
                            elapsed += 0.3
                        elif action.action == "type_query":
                            type_time = min(scene_duration * 0.6, len(action.value) * 0.035)
                            await controller.type_query(action.value, type_time)
                            elapsed += type_time
                        elif action.action == "run_query":
                            await controller.run_query()
                            elapsed += 2.5
                        elif action.action == "wait":
                            await asyncio.sleep(action.delay_after)
                            elapsed += action.delay_after

                    if scene.bg_fade_opacity and scene.bg_fade_opacity >= 0.9:
                        await controller.show_title_card(scene.model_dump())
                    else:
                        for overlay in scene.overlays:
                            await controller.show_overlay(overlay.model_dump())

                    remaining = scene_duration - elapsed
                    if remaining > 0:
                        await asyncio.sleep(remaining)

                    cumulative_time += scene_duration

                await context.close()
                await browser.close()

                recordings = list((self.temp_dir / "recordings").glob("*.webm"))
                if not recordings:
                    raise RuntimeError("No video recording found")
                raw_video = recordings[0]

                self._mux_audio(raw_video, audio_clips, cumulative_time)
                logger.info(f"SUCCESS: {self.config.output_path}")

        except Exception as e:
            logger.exception("Engine failed")
            raise
        finally:
            await self._cleanup()

    async def _resolve_ide_url(self) -> str:
        configured = self.config.ide_url
        try:
            import urllib.request
            req = urllib.request.Request(configured, method="HEAD")
            with urllib.request.urlopen(req, timeout=2):
                logger.info(f"Using existing IDE at {configured}")
                return configured
        except Exception:
            pass

        app_py = Path("web/app.py")
        if app_py.exists():
            self.server = FlaskAppServer(app_py)
            self.server.start()
            return self.server.url
        raise FileNotFoundError("Could not find web/app.py")

    def _setup_temp(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True)
        (self.temp_dir / "audio").mkdir()
        (self.temp_dir / "recordings").mkdir()

    def _estimate_action_time(self, scene) -> float:
        total = 0.0
        for action in scene.ui_actions:
            if action.action == "load_db":
                total += 1.5
            elif action.action == "open_schema":
                total += 2.0
            elif action.action == "clear_query":
                total += 0.3
            elif action.action == "type_query":
                total += min(8.0, len(action.value) * 0.035)
            elif action.action == "run_query":
                total += 2.5
            elif action.action == "wait":
                total += action.delay_after
        return total

    def _get_audio_duration(self, path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, check=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _mux_audio(self, raw_video: Path, audio_clips: List[dict], total_duration: float):
        # Step 1: Transcode WebM to H.264 MP4
        video_mp4 = self.temp_dir / "video_h264.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(raw_video),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an",
            "-movflags", "+faststart",
            str(video_mp4)
        ], check=True, capture_output=True)
        logger.info("Transcoded video to H.264")

        valid_clips = [c for c in audio_clips if c["path"] and Path(c["path"]).exists()]
        logger.info(f"Valid audio clips: {len(valid_clips)} / {len(audio_clips)}")
        
        if not valid_clips:
            shutil.copy(video_mp4, self.config.output_path)
            logger.warning("No audio clips found -- output is silent")
            return

        # Step 2: Mux audio
        inputs = []
        for clip in valid_clips:
            inputs.extend(["-i", clip["path"]])
            logger.info(f"  Audio: {clip['path']} at {clip['start']:.1f}s")
        inputs.extend(["-i", str(video_mp4)])

        video_idx = len(valid_clips)

        if len(valid_clips) == 1:
            delay_ms = int(valid_clips[0]["start"] * 1000)
            filter_complex = f"[0:a]adelay={delay_ms}|{delay_ms}[aout]"
        else:
            filter_parts = []
            amix_inputs = []
            for i, clip in enumerate(valid_clips):
                delay_ms = int(clip["start"] * 1000)
                filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
                amix_inputs.append(f"[a{i}]")
            mix = "".join(amix_inputs)
            filter_complex = ";".join(filter_parts) + f";{mix}amix=inputs={len(valid_clips)}:duration=longest[aout]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"{video_idx}:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            self.config.output_path
        ]

        logger.info("Running ffmpeg mux...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ffmpeg stderr: {result.stderr}")
            raise RuntimeError(f"ffmpeg failed: {result.returncode}")
        logger.info(f"Done: {self.config.output_path}")

    async def _cleanup(self):
        if self.server:
            self.server.stop()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    config = VideoConfig(**SCENES_CONFIG)
    engine = WSDAEngineV3(config)
    asyncio.run(engine.run())
