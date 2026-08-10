#!/usr/bin/env python3
"""
WSDA Lesson Director
Coordinates every visual event to the narration timeline.
Ensures video duration >= audio duration so lessons are never cut off.
"""

import asyncio
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from playwright.async_api import async_playwright, Page


@dataclass
class LessonStep:
    time: float
    action: str
    params: list = field(default_factory=list)
    subtitle: str = ""


LESSON_SCRIPT: List[LessonStep] = [
    LessonStep(0.0, "showBadge", [], ""),
    LessonStep(2.0, "hideBadge", [], ""),
    LessonStep(5.0, "setSubtitle", ["We have three tables: categories, products, and sales."], ""),
    LessonStep(6.0, "expandSchema", [], ""),
    LessonStep(12.0, "setSubtitle", ["The goal: calculate total sales revenue for each category."], ""),
    LessonStep(16.0, "clearSubtitle", [], ""),
    LessonStep(20.0, "showQuery", [0], ""),
    LessonStep(22.0, "setSubtitle", ["Query One uses a nested subquery. First, it calculates per-product totals inside the inner SELECT."], ""),
    LessonStep(28.0, "highlightQuery", [0], ""),
    LessonStep(35.0, "showQuery", [1], ""),
    LessonStep(37.0, "setSubtitle", ["Query Two solves the same problem with a flat three-table JOIN. No subquery needed."], ""),
    LessonStep(44.0, "highlightQuery", [1], ""),
    LessonStep(50.0, "showQuery", [2], ""),
    LessonStep(52.0, "setSubtitle", ["Query Three also uses a subquery, but groups by category inside the inner query instead of by product."], ""),
    LessonStep(60.0, "highlightQuery", [2], ""),
    LessonStep(65.0, "setSubtitle", ["Let's execute all three and compare the results."], ""),
    LessonStep(68.0, "enableRun", [], ""),
    LessonStep(70.0, "flashRun", [], ""),
    LessonStep(71.0, "runQuery", [0], ""),
    LessonStep(75.0, "runQuery", [1], ""),
    LessonStep(79.0, "runQuery", [2], ""),
    LessonStep(85.0, "setSubtitle", ["All three return identical totals. Query Two is the most readable, but Query Three may perform better on massive datasets."], ""),
    LessonStep(100.0, "showComparison", [], ""),
    LessonStep(110.0, "setSubtitle", ["Same answer, three paths. Choose the one that balances clarity and performance for your data."], ""),
    LessonStep(120.0, "clearSubtitle", [], ""),
]


class LessonDirector:
    def __init__(
        self,
        viewer_path: str,
        output_video: str,
        audio_path: Optional[str] = None,
        width: int = 1920,
        height: int = 1080,
        end_padding: float = 4.0,
    ):
        self.viewer_path = Path(viewer_path).resolve()
        self.output_video = Path(output_video).resolve()
        self.audio_path = Path(audio_path).resolve() if audio_path else None
        self.width = width
        self.height = height
        self.end_padding = end_padding

        # Resolve audio
        self.has_audio = self.audio_path and self.audio_path.exists()
        self.audio_duration = self._get_audio_duration() if self.has_audio else 0.0
        self.script_end = max(s.time for s in LESSON_SCRIPT) if LESSON_SCRIPT else 0.0
        self.total_duration = max(self.audio_duration, self.script_end) + self.end_padding

        print(f"[Director] Viewer: {self.viewer_path}")
        print(f"[Director] Output: {self.output_video}")
        print(f"[Director] Audio: {self.audio_path} {'(FOUND)' if self.has_audio else '(NOT FOUND — will render silent video)'}")
        print(f"[Director] Audio duration: {self.audio_duration:.2f}s")
        print(f"[Director] Script end: {self.script_end:.2f}s")
        print(f"[Director] Total video duration: {self.total_duration:.2f}s")

    def _get_audio_duration(self) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(self.audio_path)],
                capture_output=True, text=True, check=True
            )
            return float(json.loads(result.stdout)["format"]["duration"])
        except Exception as e:
            print(f"[Warning] ffprobe failed: {e}")
            return 0.0

    async def run(self):
        rec_dir = self.output_video.parent / "_recordings"
        rec_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": self.width, "height": self.height},
                device_scale_factor=2,
                record_video_dir=str(rec_dir),
                record_video_size={"width": self.width, "height": self.height},
            )
            page = await context.new_page()

            await page.goto(f"file://{self.viewer_path}")
            await page.wait_for_function("window.lessonAPI !== undefined", timeout=15000)
            await page.wait_for_timeout(1500)  # Let sql.js WASM load
            await page.evaluate("() => document.body.style.cursor = 'none'")

            start_time = time.monotonic()
            step_idx = 0

            while step_idx < len(LESSON_SCRIPT):
                elapsed = time.monotonic() - start_time
                step = LESSON_SCRIPT[step_idx]
                if elapsed >= step.time:
                    await self._execute_step(page, step)
                    step_idx += 1
                else:
                    await asyncio.sleep(max(0.001, step.time - elapsed))

            remaining = self.total_duration - (time.monotonic() - start_time)
            if remaining > 0:
                print(f"[Director] Holding final frame for {remaining:.2f}s...")
                await asyncio.sleep(remaining)

            await context.close()
            await browser.close()

        # Find recorded video
        video_files = list(rec_dir.glob("*.webm"))
        if not video_files:
            raise RuntimeError("No video recording found in " + str(rec_dir))
        video_path = video_files[0]

        # Mux or copy
        if self.has_audio:
            self._mux_audio(str(video_path), str(self.output_video))
        else:
            # Re-encode webm -> mp4 even without audio for compatibility
            self._convert_silent(str(video_path), str(self.output_video))

        shutil.rmtree(rec_dir, ignore_errors=True)
        print(f"[Director] ✅ Output saved: {self.output_video}")

    async def _execute_step(self, page: Page, step: LessonStep):
        js = f"""
        () => {{
            if (window.lessonAPI && window.lessonAPI.{step.action}) {{
                window.lessonAPI.{step.action}.apply(null, {json.dumps(step.params)});
            }}
        }}
        """
        await page.evaluate(js)
        if step.subtitle:
            await page.evaluate(f"""() => window.lessonAPI.setSubtitle({json.dumps(step.subtitle)})""")
        print(f"[{step.time:06.2f}] {step.action}({', '.join(repr(p) for p in step.params)})")

    def _mux_audio(self, video_path: str, output_path: str):
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", str(self.audio_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path
        ]
        subprocess.run(cmd, check=True)

    def _convert_silent(self, video_path: str, output_path: str):
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",  # no audio
            output_path
        ]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    viewer = sys.argv[1] if len(sys.argv) > 1 else "viewer/sql_viewer.html"
    output = sys.argv[2] if len(sys.argv) > 2 else "output/sql-fundamentals-02.mp4"
    audio = sys.argv[3] if len(sys.argv) > 3 else None

    director = LessonDirector(
        viewer_path=viewer,
        output_video=output,
        audio_path=audio,
        end_padding=4.0
    )
    asyncio.run(director.run())
