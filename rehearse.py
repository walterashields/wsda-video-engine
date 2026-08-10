#!/usr/bin/env python3
"""
WSDA v3 — Rehearse a lesson from a production card.

Usage:
    python3 rehearse.py courses/novabridge/video_1_1/production_card.yml

Renders the lesson visually (headless) and saves an MP4 to output/.
"""

import asyncio
import sys
from pathlib import Path

from renderer import render_card


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 rehearse.py <production_card.yml>")
        sys.exit(1)

    card_path = Path(sys.argv[1]).resolve()
    if not card_path.exists():
        print(f"Not found: {card_path}")
        sys.exit(1)

    # Find viewer.html — check common locations
    viewer_paths = [
        Path(__file__).parent / "viewer.html",
        Path(__file__).parent / "web" / "templates" / "viewer.html",
        Path(__file__).parent / "v3" / "viewer.html",
    ]
    viewer_path = None
    for p in viewer_paths:
        if p.exists():
            viewer_path = p
            break

    if not viewer_path:
        print("Error: viewer.html not found. Searched:")
        for p in viewer_paths:
            print(f"  {p}")
        sys.exit(1)

    viewer_html = viewer_path.read_text()

    output_dir = Path(__file__).parent / "output" / card_path.parent.name
    mp4_path = await render_card(card_path, viewer_html, output_dir, headless=True)
    print(f"\nDone: {mp4_path}")


if __name__ == "__main__":
    asyncio.run(main())
