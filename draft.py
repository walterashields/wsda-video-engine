#!/usr/bin/env python3
"""
WSDA Draft — production card generator from research brief

Takes a brief.json from research.py and generates:
  - A production card (production_card.yml) for each lesson
  - SQL or other asset files based on scene requirements
  - A course manifest listing all lessons in order

Usage:
  python3 draft.py research/ai_for_beginners/brief.json
  python3 draft.py research/ai_for_beginners/brief.json --lesson 1
"""

import json
import re
import sys
from pathlib import Path

import click
import yaml
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel

console = Console()
client = Anthropic()

ROOT = Path(__file__).parent


DRAFT_SYSTEM = """You are a senior instructional designer and technical course author
for the WSDA Video Engine system.

You write production cards — YAML files that control automated lesson recording.
You know every rule of the system and never break them.

LOCKED RULES:
1. Narration lives on highlight_section and show_result events ONLY.
   Never on run_query. Never on standalone pause events.
2. Every narration event is followed immediately by a pause event.
   Pause duration = (word count / 145 * 60) + 8 seconds, rounded up.
3. Numbers in narration must match what the SQL viewer displays (2 decimal places).
4. No em dashes anywhere. Use commas instead.
5. Write S-Q-L not SQL so it pronounces as letters.
6. Over-explain. Read numbers aloud. Say what table, what column, what result means.
7. Set up BEFORE: on highlight_section, describe the query before it runs.
8. Explain AFTER: on show_result, read and explain what the learner sees.
9. clears: ["result"] on highlight_section when switching to a new query.
10. Event IDs must be unique strings: e01, e01_pause, e02, e02_pause, etc.

You always respond with valid YAML only. No markdown fences. No preamble. Just YAML."""


DRAFT_PROMPT = """Generate a complete production card for this lesson.

Lesson brief:
{lesson_json}

Course context:
- Topic: {topic}
- Target learner: {target_learner}
- Tone: {tone}
- Complexity: {complexity}

Database available: {database}
SQL file will be: {sql_file}

Generate a production card YAML with:
1. schema_version, lesson_id, title, course, assets
2. All events following the locked rules above
3. Rich, over-explained narration that reads every number on screen
4. Pause durations calculated from word counts
5. Natural transitions between scenes

The narration should sound like an expert instructor speaking conversationally,
not reading from a script. Warm, direct, specific.

Return ONLY valid YAML."""


SQL_DRAFT_SYSTEM = """You are a SQL instructor and database designer.

Generate clean, educational SQL queries for a lesson.
Each query must:
- Be syntactically correct SQLite
- Demonstrate one clear concept
- Use realistic column and table names
- Include a comment explaining what it demonstrates
- Be formatted clearly for on-screen display

Return ONLY the SQL file content with -- [section_name] headers.
No markdown. No explanation. Just SQL."""


SQL_DRAFT_PROMPT = """Generate SQL queries for this lesson.

Lesson: {lesson_title}
Database tables available: {tables}
Scenes that need SQL:
{scene_sql_needs}

Format each query as:
-- [query_name]
-- Brief comment explaining what this demonstrates
SELECT ...;

Return only the SQL file content."""


def estimate_pause(narration_text: str) -> float:
    words = len(narration_text.split())
    return round((words / 145 * 60) + 8, 0)


def draft_lesson_card(lesson: dict, brief: dict, course_dir: Path) -> Path:
    lesson_num = lesson['lesson_number']
    lesson_id = f"video_{brief.get('lesson_prefix', '1')}_{lesson_num}"
    lesson_dir = course_dir / lesson_id
    lesson_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = lesson_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    db_name = f"{brief.get('slug', 'lesson')}.db"
    sql_name = f"lesson_{lesson_num}_queries.sql"

    prod_notes = brief.get('production_notes', {})

    # Generate production card via Claude
    console.print(f"  Drafting production card for lesson {lesson_num}...")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=DRAFT_SYSTEM,
        messages=[{
            "role": "user",
            "content": DRAFT_PROMPT.format(
                lesson_json=json.dumps(lesson, indent=2),
                topic=brief['topic'],
                target_learner=brief['market_analysis']['target_learner'],
                tone=prod_notes.get('tone', 'conversational'),
                complexity=prod_notes.get('complexity', 'beginner'),
                database=db_name,
                sql_file=sql_name,
            )
        }]
    )

    card_yaml = response.content[0].text.strip()
    card_yaml = re.sub(r'^```ya?ml\s*', '', card_yaml)
    card_yaml = re.sub(r'\s*```$', '', card_yaml)

    card_path = lesson_dir / "production_card.yml"
    card_path.write_text(card_yaml)

    # Generate SQL file if lesson uses sql_viewer
    scenes = lesson.get('scenes', [])
    sql_scenes = [s for s in scenes if s.get('visual_type') == 'sql_viewer']

    if sql_scenes:
        console.print(f"  Drafting SQL queries for lesson {lesson_num}...")

        scene_needs = '\n'.join([
            f"- Scene {s['scene_number']}: {s['scene_title']} — {s['what_learner_sees']}"
            for s in sql_scenes
        ])

        sql_response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=SQL_DRAFT_SYSTEM,
            messages=[{
                "role": "user",
                "content": SQL_DRAFT_PROMPT.format(
                    lesson_title=lesson['title'],
                    tables="(will be defined in database — use realistic names for the topic)",
                    scene_sql_needs=scene_needs,
                )
            }]
        )

        sql_content = sql_response.content[0].text.strip()
        sql_content = re.sub(r'^```sql\s*', '', sql_content)
        sql_content = re.sub(r'\s*```$', '', sql_content)

        sql_path = assets_dir / sql_name
        sql_path.write_text(sql_content)
        console.print(f"  [green]✓[/green] SQL: {sql_path.name}")

    console.print(f"  [green]✓[/green] Card: {card_path}")
    return card_path


@click.command()
@click.argument("brief_path")
@click.option("--lesson", "lesson_num", default=None, type=int,
              help="Draft only a specific lesson number")
@click.option("--course-dir", default=None,
              help="Output directory (default: courses/SLUG/)")
def draft(brief_path, lesson_num, course_dir):
    """Generate production cards from a research brief."""

    brief_path = Path(brief_path)
    if not brief_path.exists():
        console.print(f"[red]Brief not found: {brief_path}[/red]")
        sys.exit(1)

    with open(brief_path) as f:
        brief = json.load(f)

    slug = re.sub(r'[^a-z0-9]+', '_', brief['topic'].lower()).strip('_')[:40]
    brief['slug'] = slug
    brief['lesson_prefix'] = '1'

    if course_dir:
        out_dir = Path(course_dir)
    else:
        out_dir = ROOT / "courses" / slug

    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold]WSDA Draft[/bold]\n"
        f"Topic:  [cyan]{brief['topic']}[/cyan]\n"
        f"Format: [cyan]{brief['format']}[/cyan]\n"
        f"Output: [cyan]{out_dir}[/cyan]",
        border_style="green"
    ))

    lessons = brief['content_structure']['lessons']
    if lesson_num:
        lessons = [l for l in lessons if l['lesson_number'] == lesson_num]
        if not lessons:
            console.print(f"[red]Lesson {lesson_num} not found in brief[/red]")
            sys.exit(1)

    cards = []
    for lesson in lessons:
        console.print(f"\n[bold]Lesson {lesson['lesson_number']}:[/bold] {lesson['title']}")
        card_path = draft_lesson_card(lesson, brief, out_dir)
        cards.append(card_path)

    # Write course manifest
    manifest = {
        "course": brief['topic'],
        "format": brief['format'],
        "slug": slug,
        "lessons": [str(c) for c in cards],
        "hook": brief['content_structure']['hook'],
        "core_promise": brief['content_structure']['core_promise'],
    }
    manifest_path = out_dir / "course_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    console.print(Panel(
        f"[bold green]Draft complete.[/bold green]\n\n"
        f"Lessons drafted: {len(cards)}\n"
        f"Output: [cyan]{out_dir}[/cyan]\n\n"
        f"Next steps:\n"
        f"1. Review each production_card.yml\n"
        f"2. Run check_numbers.py on each card\n"
        f"3. Run produce.py on each card\n\n"
        f"Or produce all lessons:\n"
        f"  for card in {out_dir}/*/production_card.yml; do\n"
        f"    python3 produce.py $card\n"
        f"  done",
        title="Draft Complete",
        border_style="green"
    ))


if __name__ == "__main__":
    draft()
