#!/usr/bin/env python3
"""
WSDA Lesson Generator — CLI Entry Point

Usage:
    python3 generate.py --topic "SQL JOINs" --course sql-fundamentals --lesson 3
    python3 generate.py --topic "Window Functions in SQL" --course advanced-sql --lesson 1

Environment:
    OPENAI_API_KEY    required
    ELEVENLABS_API_KEY    optional (for rendering)
    ELEVENLABS_VOICE_ID   optional (for rendering)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from generator.lesson_generator import LessonGenerator


def main():
    parser = argparse.ArgumentParser(description="Generate WSDA video lessons")
    parser.add_argument("--topic", required=True, help="Lesson topic (e.g., 'SQL JOINs')")
    parser.add_argument("--course", required=True, help="Course ID (e.g., 'sql-fundamentals')")
    parser.add_argument("--lesson", type=int, required=True, help="Lesson number")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model (default: gpt-4o)")
    parser.add_argument("--output", default="./courses", help="Output directory")
    parser.add_argument("--render", action="store_true", help="Auto-render to MP4 after generation")
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    # Generate
    async def run():
        gen = LessonGenerator(model=args.model)
        result = await gen.generate(
            topic=args.topic,
            course_id=args.course,
            lesson_num=args.lesson,
            output_dir=Path(args.output)
        )

        # Optionally render
        if args.render:
            print("\n[render] Starting video render...")
            from renderer import render_card
            viewer_path = Path(__file__).parent / "viewer.html"
            if not viewer_path.exists():
                viewer_path = Path(__file__).parent / "web" / "templates" / "viewer.html"
            viewer_html = viewer_path.read_text()
            output_dir = result["lesson_dir"].parent.parent / "output" / result["lesson_dir"].name
            await render_card(result["production_card"], viewer_html, output_dir)

    asyncio.run(run())


if __name__ == "__main__":
    main()
