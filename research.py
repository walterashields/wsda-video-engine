#!/usr/bin/env python3
"""
WSDA Research — niche and content brief generator

Given a topic and format, searches current market data and returns
a structured content brief: what to cover, in what order, why it
will perform, and how many scenes per lesson.

Usage:
  python3 research.py "AI for beginners" --format course
  python3 research.py "Excel pivot tables" --format short-video
  python3 research.py "SQL for data analysts" --format tutorial
  python3 research.py "Python automation" --format lesson

Formats:
  course        Full multi-lesson course (8-15 lessons)
  short-video   Single 3-5 minute video (4-6 scenes)
  tutorial      Single hands-on tutorial (6-10 scenes)
  lesson        One lesson from a larger course (4-8 scenes)

Output:
  research/TOPIC_SLUG/brief.json    Machine-readable brief for draft.py
  research/TOPIC_SLUG/brief.md      Human-readable summary
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import click
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()
client = Anthropic()

ROOT = Path(__file__).parent


RESEARCH_SYSTEM = """You are a senior content strategist and instructional designer
specializing in technical education for digital platforms.

Your job is to analyze a topic and produce a precise, market-informed content brief
that will guide the production of high-quality educational video content.

You have deep knowledge of:
- What technical topics are in high demand right now (AI, data, automation, productivity)
- What makes learners engage and complete courses (hands-on exercises, clear outcomes, 
  progressive difficulty, real-world scenarios)
- How content performs differently across platforms (LinkedIn Learning, YouTube, Udemy,
  internal training, social short-form)
- What exercise files and supporting materials make lessons memorable
- How to structure content for the target learner's level and goals

You always respond in valid JSON only. No markdown fences. No preamble. Just JSON.
Never use apostrophes inside JSON string values — use "do not" not "don't".
Never truncate the response. Complete the full JSON structure."""


RESEARCH_PROMPT = """Analyze this content request and produce a detailed brief.

Topic: {topic}
Format: {format}
Target platform context: {platform_notes}

Return a JSON object with this exact structure:

{{
  "topic": "exact topic string",
  "format": "course|short-video|tutorial|lesson",
  "market_analysis": {{
    "demand_level": "high|medium|low",
    "why_now": "1-2 sentences on why this topic is relevant right now",
    "target_learner": "specific description of who this is for",
    "learner_goal": "what the learner wants to be able to DO after watching",
    "competition_gap": "what existing content misses that this should nail",
    "platform_fit": "best platform(s) for this content and why"
  }},
  "content_structure": {{
    "hook": "the opening line or question that makes someone click/watch",
    "core_promise": "one sentence: what the learner will be able to do",
    "lessons": [
      {{
        "lesson_number": 1,
        "title": "Lesson title — specific and outcome-focused",
        "duration_minutes": 5,
        "learning_objective": "By the end of this lesson the learner will be able to...",
        "scenes": [
          {{
            "scene_number": 1,
            "scene_title": "Short scene name",
            "duration_seconds": 90,
            "visual_type": "sql_viewer|browser|terminal|slides|excel|pdf|screen_demo",
            "what_learner_sees": "Exact description of what is on screen",
            "what_learner_hears": "Summary of narration",
            "exercise_file": "filename.ext or null",
            "transition_to_next": "brief transition note"
          }}
        ],
        "exercise_files": ["file1.ext", "file2.ext"],
        "key_takeaway": "the one thing the learner must remember"
      }}
    ]
  }},
  "exercise_file_plan": [
    {{
      "filename": "exact filename with extension",
      "type": "sql|csv|xlsx|txt|pdf|db|py",
      "purpose": "what the learner does with this file",
      "lesson_used_in": [1, 2]
    }}
  ],
  "production_notes": {{
    "tone": "conversational|professional|energetic|calm",
    "pacing": "fast|moderate|deliberate",
    "complexity": "beginner|intermediate|advanced",
    "hands_on_ratio": "percentage of time learner is doing vs watching",
    "adapters_needed": ["sql_viewer", "excel", "browser", "terminal", "slides"]
  }}
}}

Limit to a maximum of 5 lessons for a course, 1 lesson for other formats. Each lesson has 3-5 scenes maximum. Keep descriptions concise. Scene durations should add up to lesson duration.
Exercise files should be things a real learner would actually use.
The hook must be compelling enough to make someone stop scrolling.
Adapters needed must only include: sql_viewer, excel, browser, terminal, slides."""


FORMAT_PLATFORM_NOTES = {
    "course": "LinkedIn Learning or Udemy — learners pay for structured progression, expect certificates, need exercise files",
    "short-video": "YouTube or LinkedIn feed — must deliver value in under 5 minutes, hook in first 10 seconds, one clear takeaway",
    "tutorial": "YouTube or blog embed — hands-on from minute one, learner follows along with their own files, practical outcome",
    "lesson": "Part of a larger course — assumes prior context, builds on previous lesson, bridges to next",
}


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:40]


def run_research(topic: str, format: str) -> dict:
    platform_notes = FORMAT_PLATFORM_NOTES.get(format, FORMAT_PLATFORM_NOTES["course"])

    console.print(f"\n[bold cyan]Researching:[/bold cyan] {topic}")
    console.print(f"[dim]Format: {format} | {platform_notes}[/dim]\n")

    # Use web search to ground the research in current market data
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8000,
        system=RESEARCH_SYSTEM,
        messages=[{
            "role": "user",
            "content": RESEARCH_PROMPT.format(
                topic=topic,
                format=format,
                platform_notes=platform_notes,
            )
        }]
    )

    raw = response.content[0].text.strip()

    # Strip any accidental markdown fences
    raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```$', '', raw.strip())

    # Extract just the JSON object if there's surrounding text
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group(0)

    # Fix common JSON issues: trailing commas before } or ]
    raw = re.sub(r',\s*([}\]])', r'', raw)

    return json.loads(raw)


def save_brief(brief: dict, topic: str) -> tuple[Path, Path]:
    slug = slugify(topic)
    out_dir = ROOT / "research" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = out_dir / "brief.json"
    json_path.write_text(json.dumps(brief, indent=2))

    # Markdown summary
    md_lines = [
        f"# Content Brief: {brief['topic']}",
        f"\n**Format:** {brief['format']}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "\n---\n",
        "## Market Analysis",
        f"**Demand:** {brief['market_analysis']['demand_level'].upper()}  ",
        f"**Why now:** {brief['market_analysis']['why_now']}  ",
        f"**Target learner:** {brief['market_analysis']['target_learner']}  ",
        f"**Learner goal:** {brief['market_analysis']['learner_goal']}  ",
        f"**Gap this fills:** {brief['market_analysis']['competition_gap']}  ",
        f"**Best platform:** {brief['market_analysis']['platform_fit']}",
        "\n---\n",
        "## Content Hook",
        f"> {brief['content_structure']['hook']}",
        f"\n**Core promise:** {brief['content_structure']['core_promise']}",
        "\n---\n",
        "## Lesson Structure",
    ]

    total_scenes = 0
    for lesson in brief['content_structure']['lessons']:
        md_lines.append(f"\n### Lesson {lesson['lesson_number']}: {lesson['title']}")
        md_lines.append(f"**Duration:** {lesson['duration_minutes']} min  ")
        md_lines.append(f"**Objective:** {lesson['learning_objective']}  ")
        md_lines.append(f"**Key takeaway:** {lesson['key_takeaway']}")
        md_lines.append(f"\n**Scenes ({len(lesson['scenes'])}):**")
        for scene in lesson['scenes']:
            total_scenes += 1
            md_lines.append(
                f"- Scene {scene['scene_number']}: **{scene['scene_title']}** "
                f"({scene['duration_seconds']}s) — {scene['visual_type']}"
            )
            if scene.get('exercise_file'):
                md_lines.append(f"  - Exercise file: `{scene['exercise_file']}`")

    md_lines += [
        "\n---\n",
        "## Exercise Files",
    ]
    for f in brief.get('exercise_file_plan', []):
        md_lines.append(
            f"- `{f['filename']}` ({f['type']}) — {f['purpose']} "
            f"[Lessons {f['lesson_used_in']}]"
        )

    prod = brief.get('production_notes', {})
    md_lines += [
        "\n---\n",
        "## Production Notes",
        f"**Tone:** {prod.get('tone', '?')}  ",
        f"**Pacing:** {prod.get('pacing', '?')}  ",
        f"**Complexity:** {prod.get('complexity', '?')}  ",
        f"**Hands-on ratio:** {prod.get('hands_on_ratio', '?')}  ",
        f"**Adapters needed:** {', '.join(prod.get('adapters_needed', []))}",
        "\n---\n",
        f"*Total scenes: {total_scenes}*  ",
        f"*Run `python3 draft.py research/{slugify(topic)}/brief.json` to generate production cards.*",
    ]

    md_path = out_dir / "brief.md"
    md_path.write_text('\n'.join(md_lines))

    return json_path, md_path


@click.command()
@click.argument("topic")
@click.option("--format", "fmt", default="course",
              type=click.Choice(["course", "short-video", "tutorial", "lesson"]),
              help="Content format")
@click.option("--open-brief", is_flag=True, help="Open the markdown brief after generation")
def research(topic, fmt, open_brief):
    """Research a topic and generate a content brief for draft.py."""

    console.print(Panel(
        f"[bold]WSDA Research[/bold]\n"
        f"Topic:  [cyan]{topic}[/cyan]\n"
        f"Format: [cyan]{fmt}[/cyan]",
        border_style="green"
    ))

    for attempt in range(1, 3):
        try:
            brief = run_research(topic, fmt)
            break
        except json.JSONDecodeError as e:
            if attempt == 2:
                console.print(f"[red]Failed to parse JSON after 2 attempts: {e}[/red]")
                sys.exit(1)
            console.print(f"[yellow]JSON parse error on attempt {attempt}, retrying...[/yellow]")
        except Exception as e:
            console.print(f"[red]Research failed: {e}[/red]")
            sys.exit(1)

    json_path, md_path = save_brief(brief, topic)

    # Print summary
    ma = brief['market_analysis']
    cs = brief['content_structure']
    lessons = cs['lessons']
    total_scenes = sum(len(l['scenes']) for l in lessons)
    total_mins = sum(l['duration_minutes'] for l in lessons)
    adapters = brief.get('production_notes', {}).get('adapters_needed', [])

    console.print(Panel(
        f"[bold green]Brief complete.[/bold green]\n\n"
        f"Demand:       [cyan]{ma['demand_level'].upper()}[/cyan]\n"
        f"Lessons:      {len(lessons)}\n"
        f"Total scenes: {total_scenes}\n"
        f"Total time:   ~{total_mins} minutes\n"
        f"Adapters:     {', '.join(adapters)}\n\n"
        f"Hook: [italic]{cs['hook']}[/italic]\n\n"
        f"Brief saved to:\n"
        f"  [cyan]{json_path}[/cyan]\n"
        f"  [cyan]{md_path}[/cyan]\n\n"
        f"Next step:\n"
        f"  python3 draft.py {json_path}",
        title="Research Complete",
        border_style="green"
    ))

    if open_brief:
        import subprocess
        subprocess.run(["open", str(md_path)])


if __name__ == "__main__":
    research()
