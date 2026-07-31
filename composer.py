"""
WSDA v3 — Video Composer
Renders overlays in PIL, assembles final video with FFmpeg.
"""

import os
import shutil
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Optional
import ffmpeg
import logging

logger = logging.getLogger("wsda.composer")


class VideoComposer:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._font_cache: Dict[int, ImageFont.FreeTypeFont] = {}

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self._font_cache:
            paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
            for p in paths:
                if os.path.exists(p):
                    try:
                        self._font_cache[key] = ImageFont.truetype(p, size)
                        break
                    except Exception:
                        continue
            else:
                self._font_cache[key] = ImageFont.load_default()
        return self._font_cache[key]

    def composite_frame(
        self,
        base_path: str,
        output_path: str,
        overlays: List[Dict],
        bg_dim: Optional[float] = None
    ):
        base = Image.open(base_path).convert("RGBA")
        if base.size != (self.width, self.height):
            base = base.resize((self.width, self.height), Image.LANCZOS)

        # Optional background dim for overlay scenes
        if bg_dim is not None:
            overlay = Image.new("RGBA", base.size, (11, 12, 16, int(255 * bg_dim)))
            base = Image.alpha_composite(base, overlay)

        for ov in overlays:
            img = self._render_overlay(ov)
            if img:
                pos = self._calculate_position(ov.get("position", [0.5, 0.5]), img.size)
                base = self._paste_centered(base, img, pos)

        base.convert("RGB").save(output_path, quality=95, optimize=True)

    def _render_overlay(self, ov: Dict) -> Optional[Image.Image]:
        otype = ov["type"]
        content = ov["content"]
        style = ov.get("style", {})

        if otype == "text":
            return self._render_text(content, style)
        elif otype == "badge":
            return self._render_badge(content, style)
        elif otype in ("highlight", "comparison"):
            return self._render_highlight(content, style)
        return None

    def _render_text(self, text: str, style: Dict) -> Image.Image:
        font_size = style.get("font_size", 48)
        color = style.get("color", "#FFFFFF")
        bg = style.get("bg_color", "#0B0C10")
        pad = style.get("padding", 40)

        font = self._get_font(font_size, bold=True)
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        w, h = tw + pad * 2, th + pad * 2
        img = Image.new("RGBA", (w, h), bg + "E6")
        draw = ImageDraw.Draw(img)
        draw.text((pad, pad), text, font=font, fill=color)
        return img

    def _render_badge(self, text: str, style: Dict) -> Image.Image:
        font_size = style.get("font_size", 20)
        color = style.get("color", "#FFFFFF")
        bg = style.get("bg_color", "#333333")
        pad_x, pad_y = 24, 12

        font = self._get_font(font_size)
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        w, h = tw + pad_x * 2, th + pad_y * 2
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w, h], radius=16, fill=bg + "DD")
        draw.text((pad_x, pad_y), text, font=font, fill=color)
        return img

    def _render_highlight(self, text: str, style: Dict) -> Image.Image:
        font_size = style.get("font_size", 24)
        color = style.get("color", "#FFFFFF")
        bg = style.get("bg_color", "#2D5A3D")
        pad = style.get("padding", 30)

        font = self._get_font(font_size, bold=True)
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        w, h = tw + pad * 2, th + pad * 2
        img = Image.new("RGBA", (w, h), bg + "CC")
        draw = ImageDraw.Draw(img)
        draw.text((pad, pad), text, font=font, fill=color)
        return img

    def _calculate_position(self, pos: List[float], overlay_size: Tuple[int, int]) -> Tuple[int, int]:
        x = int(pos[0] * self.width)
        y = int(pos[1] * self.height)
        return (x, y)

    def _paste_centered(self, base: Image.Image, overlay: Image.Image, center: Tuple[int, int]) -> Image.Image:
        x = center[0] - overlay.width // 2
        y = center[1] - overlay.height // 2
        base.paste(overlay, (x, y), overlay)
        return base

    def assemble(self, frame_glob: str, output_path: str, duration: float):
        logger.info(f"Assembling video: {output_path} ({duration}s)")
        try:
            (
                ffmpeg
                .input(frame_glob, framerate=self.fps, pattern_type="glob")
                .output(
                    output_path,
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    preset="slow",
                    crf=17,
                    movflags="+faststart",
                    t=duration
                )
                .overwrite_output()
                .run(quiet=True)
            )
            logger.info("Assembly complete")
        except ffmpeg.Error as e:
            stderr = e.stderr.decode() if e.stderr else "unknown"
            logger.error(f"FFmpeg failed: {stderr}")
            raise
