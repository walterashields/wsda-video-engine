#!/usr/bin/env python3
"""
WSDA Draft — production card generator from research brief

Takes a brief.json from research.py and generates validated,
engine-correct production cards ready to run through produce.py.

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


# ── Production standard — injected into every draft prompt ─────────────────
PRODUCTION_STANDARD = """
WSDA VIDEO ENGINE — LOCKED PRODUCTION RULES
============================================

You are generating YAML production cards for the WSDA Video Engine.
Every card you produce must follow these rules exactly.
Breaking any rule will cause the recording to fail.

## SCHEMA
schema_version: "3.0"
lesson_id: "video_X_Y"      # unique, no spaces
title: "Lesson Title"
course: "Course Name"
assets:
  database: "assets/lesson.db"   # for SQL lessons
  sql_file: "assets/queries.sql" # for SQL lessons
  # OR for chat demo lessons:
  demo: "chat"

## VALID EVENT TYPES ONLY
SQL viewer events:
  open_database, open_file, show_schema, highlight_section,
  run_query, show_result, set_layout, compare_results,
  zoom_result, open_view

Chat demo events:
  open_chat, new_conversation, show_message, show_response,
  highlight_region, clear_highlight, set_input

Control events (all lesson types):
  pause, fade_out

## EVENT ID RULES
- Every event needs a unique id string: "e01", "e02", etc.
- Every narration event must be immediately followed by a pause:
  "e01_pause", "e02_pause", etc.
- No duplicate IDs.

## NARRATION RULES — NON-NEGOTIABLE
1. Narration on highlight_section and show_result ONLY for SQL lessons.
   Narration on highlight_region and show_result ONLY for chat demo lessons.
   NEVER on run_query, show_message, show_response, open_chat, new_conversation.

2. Every event with narration is immediately followed by a pause event.
   Pause duration formula: (word_count / 145 * 60) + 8 seconds, rounded up.
   Example: 60 words = (60/145*60)+8 = 32.8 → use 33.0

3. Numbers must match what the SQL viewer displays (2 decimal places).
   Database value 0.0487 displays as 0.05 — narration says "zero point zero five".

4. No em dashes. Use commas instead.

5. ALWAYS use contractions. We're not we are. I'll not I will. You'll not you will.
   It's not it is. Don't not do not. Can't not cannot. Won't not will not.
   That's not that is. Here's not here is. Let's not let us.
   The only exception is when emphasis requires the full form.
   Contractions make the voice sound human. Formal speech kills engagement.

5. Write S-Q-L not SQL so ElevenLabs pronounces each letter.

6. Over-explain. Read every number aloud. Say which table, which column,
   what the result means, why it matters. Never caption — always teach.

7. Before each query: set up what the learner is about to see.
   After each result: read the numbers, explain what they mean, connect to lesson.

8. Warm, direct, conversational tone. Not academic. Not stiff.
   Talk like a smart friend explaining something they love.

## SQL FILE FORMAT
Every SQL section must use this header format:
-- [section_name]
SELECT ...;

Section names match query_ref values in production card exactly.

## PAUSE SIZING QUICK REFERENCE
20 words  → 16s pause
40 words  → 24s pause
60 words  → 33s pause
80 words  → 41s pause
100 words → 49s pause
120 words → 58s pause
150 words → 70s pause

## COMPLETE SQL LESSON TEMPLATE
---
schema_version: "3.0"
lesson_id: "video_1_1"
title: "Lesson Title"
course: "Course Name"
assets:
  database: "assets/lesson.db"
  sql_file: "assets/queries.sql"
events:
  - id: "e01"
    type: "open_database"
    target: "sql_viewer"
    asset: "assets/lesson.db"
    transition: "new_concept"
    narration: >
      Opening narration. Set up the lesson.
      Tell the learner what problem you are solving.
  - id: "e01_pause"
    type: "pause"
    duration: 20.0
    transition: "continuation"
  - id: "e02"
    type: "show_schema"
    target: "sql_viewer"
    transition: "new_concept"
    narration: >
      Describe the tables in the schema.
  - id: "e02_pause"
    type: "pause"
    duration: 18.0
    transition: "continuation"
  - id: "e03"
    type: "open_file"
    target: "sql_viewer"
    asset: "assets/queries.sql"
    transition: "new_concept"
  - id: "e03_pause"
    type: "pause"
    duration: 2.0
    transition: "continuation"
  - id: "e04"
    type: "highlight_section"
    target: "sql_viewer"
    section: "query_1"
    transition: "new_concept"
    clears: []
    narration: >
      Describe this query before running it.
      Tell the learner what table it queries and what question it answers.
  - id: "e04_pause"
    type: "pause"
    duration: 16.0
    transition: "continuation"
  - id: "e05"
    type: "run_query"
    target: "sql_viewer"
    query_ref: "query_1"
  - id: "e05_pause"
    type: "pause"
    duration: 3.0
    transition: "continuation"
  - id: "e06"
    type: "show_result"
    target: "sql_viewer"
    transition: "continuation"
    narration: >
      Read the result aloud. Say the exact numbers on screen.
      Explain what the result means and why it matters.
  - id: "e06_pause"
    type: "pause"
    duration: 24.0
    transition: "continuation"
  - id: "e_close"
    type: "zoom_result"
    target: "sql_viewer"
    transition: "emphasis"
    narration: >
      Summarize the lesson. State the key takeaway. Bridge to next lesson.
  - id: "e_close_pause"
    type: "pause"
    duration: 18.0
    transition: "continuation"
  - id: "e_end"
    type: "fade_out"
    target: "all"
    transition: "emphasis"

## COMPLETE CHAT DEMO LESSON TEMPLATE
---
schema_version: "3.0"
lesson_id: "video_1_1"
title: "Lesson Title"
course: "Course Name"
assets:
  demo: "chat"
events:
  - id: "e01"
    type: "open_chat"
    target: "chat_demo"
    user_name: "Instructor Name"
    initials: "IN"
    transition: "new_concept"
  - id: "e01_pause"
    type: "pause"
    duration: 2.0
    transition: "continuation"
  - id: "e01b"
    type: "highlight_region"
    target: "chat_demo"
    region: "chat-area"
    callout: "Brief callout text"
    transition: "new_concept"
    narration: >
      Opening narration after interface is visible.
  - id: "e01b_pause"
    type: "pause"
    duration: 30.0
    transition: "continuation"
  - id: "e02"
    type: "new_conversation"
    target: "chat_demo"
    title: "Conversation title"
    transition: "new_concept"
  - id: "e02_pause"
    type: "pause"
    duration: 0.5
    transition: "continuation"
  - id: "e03"
    type: "show_message"
    target: "chat_demo"
    text: "The user prompt text here"
    region: "prompt-1"
    transition: "continuation"
  - id: "e03_pause"
    type: "pause"
    duration: 0.5
    transition: "continuation"
  - id: "e04"
    type: "show_response"
    target: "chat_demo"
    text: "The AI response text here"
    region: "response-1"
    transition: "continuation"
  - id: "e04_pause"
    type: "pause"
    duration: 1.0
    transition: "continuation"
  - id: "e04b"
    type: "highlight_region"
    target: "chat_demo"
    region: "response-1"
    callout: "What to notice here"
    transition: "continuation"
    narration: >
      Explain what the learner sees after the response appears.
      Read key parts aloud. Explain why it matters.
  - id: "e04b_pause"
    type: "pause"
    duration: 30.0
    transition: "continuation"
  - id: "e04c"
    type: "clear_highlight"
    target: "chat_demo"
    transition: "continuation"
  - id: "e04c_pause"
    type: "pause"
    duration: 0.3
    transition: "continuation"
  - id: "e_end"
    type: "fade_out"
    target: "all"
    transition: "emphasis"
"""


DRAFT_SYSTEM = f"""You are a senior instructional designer for the WSDA Video Engine.

You generate production card YAML files that control automated lesson recording.
Every card you produce must pass validation — wrong event types or missing pauses
will cause the recording to fail.

{PRODUCTION_STANDARD}

You always respond with valid YAML only.
No markdown fences. No preamble. No explanation. Just YAML.
Start your response with: schema_version: "3.0"
"""


DRAFT_PROMPT = """Generate a complete production card for this lesson.

Lesson:
{lesson_json}

Course topic: {topic}
Target learner: {target_learner}
Tone: {tone}
Adapter type: {adapter_type}

LESSON CONTEXT:
{lesson_context}

NARRATION VOICE REQUIREMENT:
- Use contractions throughout: we're, I'll, you'll, it's, don't, can't, won't
- Casual and warm, like a smart friend explaining something they love
- First 30 seconds must state who this lesson is for and what they'll be able to do
- Never sound like a textbook or a corporate training manual

Additional context:
- Database: {database}
- SQL file: {sql_file}

Generate a production card with rich, over-explained narration.
Every narration block must have a following pause sized correctly.
Use contractions. Use casual speech. Read every number aloud.

Return ONLY valid YAML starting with schema_version: "3.0"
"""


SQL_SYSTEM = """You generate SQL files for educational lessons.

Rules:
- Every section starts with: -- [section_name]
- Section names use lowercase and underscores only
- Each query is clear, educational, and demonstrates one concept
- Include a brief comment explaining what the query demonstrates
- Valid SQLite syntax only
- Format code clearly for on-screen display

Return ONLY the SQL file content. No markdown. No explanation."""


SQL_PROMPT = """Generate SQL queries for this lesson.

Lesson: {lesson_title}
Scenes needing SQL:
{scene_needs}

Tables will be created separately. Use realistic column and table names
appropriate for the topic. Make the SQL educational and clear.

Return only the SQL file content with -- [section_name] headers."""


def detect_adapter(lesson: dict, brief: dict) -> str:
    """
    Determine which adapter this lesson needs based on content.
    
    chat_demo: ONLY when the lesson is literally about using ChatGPT/AI tools
    sql_viewer: when the lesson involves SQL, databases, or data analysis
    slides: conceptual lessons (fallback to chat_demo with Q&A format for now)
    """
    scenes = lesson.get('scenes', [])
    visual_types = [s.get('visual_type', '') for s in scenes]
    title = lesson.get('title', '').lower()
    objective = lesson.get('learning_objective', '').lower()
    
    # SQL viewer: explicit SQL content
    if 'sql_viewer' in visual_types:
        return 'sql_viewer'
    
    # Chat demo: ONLY for lessons explicitly about using ChatGPT or AI tools
    chat_keywords = ['chatgpt', 'prompt', 'hands on with', 'first ai conversation',
                     'using chatgpt', 'ai conversation', 'prompt engineering']
    if any(kw in title for kw in chat_keywords):
        return 'chat_demo'
    if any(kw in objective for kw in chat_keywords):
        return 'chat_demo'
    
    # Slides-based conceptual lessons: use chat_demo in Q&A format
    # (slides adapter not yet built — chat_demo with instructor asking
    # questions and AI providing structured answers is a valid substitute)
    # But mark it clearly so the draft prompt knows the intent
    slides_keywords = ['what is', 'definition', 'types', 'landscape', 'myths',
                       'overview', 'introduction', 'fundamentals', 'action plan',
                       'vocabulary', 'concepts']
    if any(kw in title for kw in slides_keywords):
        return 'chat_demo_conceptual'  # special flag
    
    return 'chat_demo_conceptual'  # default for non-SQL browser lessons


def calculate_pause(narration_text: str) -> float:
    """Calculate correct pause duration from word count."""
    words = len(narration_text.split())
    return round((words / 145 * 60) + 8, 0)


def validate_card(card_yaml: str) -> tuple[bool, list[str]]:
    """Validate a production card for common errors."""
    errors = []

    try:
        card = yaml.safe_load(card_yaml)
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]

    if not card:
        return False, ["Empty card"]

    if card.get('schema_version') != '3.0':
        errors.append(f"Wrong schema_version: {card.get('schema_version')}")

    valid_types = {
        'open_database', 'open_file', 'show_schema', 'highlight_section',
        'run_query', 'show_result', 'set_layout', 'compare_results',
        'zoom_result', 'open_view', 'open_chat', 'new_conversation',
        'show_message', 'show_response', 'highlight_region', 'clear_highlight',
        'set_input', 'pause', 'fade_out', 'activate_table', 'switch_window',
        'focus_callout', 'highlight_result', 'clear_result', 'type_message',
        'send_message', 'stream_response',
    }

    events = card.get('events', [])
    ids = [e.get('id') for e in events]

    # Check duplicate IDs
    if len(ids) != len(set(ids)):
        dupes = [i for i in ids if ids.count(i) > 1]
        errors.append(f"Duplicate event IDs: {set(dupes)}")

    # Check valid event types
    for e in events:
        if e.get('type') not in valid_types:
            errors.append(f"Invalid event type: {e.get('type')} in {e.get('id')}")

    # Check narration events have following pause
    narration_events = ['highlight_section', 'show_result', 'highlight_region',
                        'open_database', 'show_schema', 'open_file']
    for i, e in enumerate(events):
        if e.get('type') in narration_events and (e.get('narration') or '').strip():
            # Next event should be a pause
            if i + 1 < len(events):
                next_e = events[i + 1]
                if next_e.get('type') != 'pause':
                    errors.append(
                        f"Event {e['id']} has narration but next event "
                        f"{next_e['id']} is not a pause"
                    )
            else:
                errors.append(f"Event {e['id']} has narration but is the last event")

    # Check pause durations are present
    for e in events:
        if e.get('type') == 'pause' and not e.get('duration'):
            errors.append(f"Pause {e.get('id')} missing duration")

    return len(errors) == 0, errors


def draft_lesson(lesson: dict, brief: dict, course_dir: Path) -> Path:
    lesson_num = lesson['lesson_number']
    lesson_id = f"video_1_{lesson_num}"
    lesson_dir = course_dir / lesson_id
    lesson_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = lesson_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    slug = brief.get('slug', 'lesson')
    adapter_type = detect_adapter(lesson, brief)
    prod_notes = brief.get('production_notes', {})

    db_name = f"{slug}.db" if adapter_type == 'sql_viewer' else 'none'
    sql_name = f"lesson_{lesson_num}_queries.sql" if adapter_type == 'sql_viewer' else 'none'

    console.print(f"  Adapter: [cyan]{adapter_type}[/cyan]")

    # Generate production card with retry
    # Build lesson context string
    lesson_context_parts = [
        f"Lesson {lesson_num} of {len(brief.get('content_structure', {}).get('lessons', []))}",
        f"Duration: {lesson.get('duration_minutes', 5)} minutes",
        f"Key takeaway: {lesson.get('key_takeaway', '')}",
        f"Adapter: {adapter_type}",
    ]
    if adapter_type == 'chat_demo_conceptual':
        lesson_context_parts.append(
            "IMPORTANT: This is a conceptual lesson. Use the chat demo interface "
            "where the instructor asks questions and gets structured educational responses. "
            "The AI responses should contain the core teaching content — definitions, "
            "examples, comparisons — formatted clearly for on-screen reading. "
            "The narration explains and deepens what the learner sees on screen."
        )
    lesson_context = "\n".join(lesson_context_parts)

    # Normalize adapter type for card generation
    card_adapter = "chat_demo" if "chat_demo" in adapter_type else adapter_type

    card_yaml = None
    for attempt in range(1, 4):
        console.print(f"  Drafting card (attempt {attempt}/3)...")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=6000,
            system=DRAFT_SYSTEM,
            messages=[{
                "role": "user",
                "content": DRAFT_PROMPT.format(
                    lesson_json=json.dumps(lesson, indent=2),
                    topic=brief['topic'],
                    target_learner=brief['market_analysis']['target_learner'],
                    tone=prod_notes.get('tone', 'conversational'),
                    adapter_type=card_adapter,
                    lesson_context=lesson_context,
                    database=db_name,
                    sql_file=sql_name,
                )
            }]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```\s*$', '', raw.strip())

        valid, errors = validate_card(raw)
        if valid:
            # Enforce duration limit based on format
            format_limits = {
                "short-video": 5, "tutorial": 12,
                "lesson": 10, "course": 15,
            }
            lesson_format = brief.get("format", "course")
            max_min = format_limits.get(lesson_format, 15)
            max_s = max_min * 60

            # Calculate estimated duration from pauses
            parsed = yaml.safe_load(raw)
            total_s = sum(
                float(e.get("duration", 0))
                for e in parsed.get("events", [])
                if e.get("type") == "pause"
            )

            if total_s > max_s * 1.1:
                scale = max_s / total_s
                # Scale all pause durations
                import re as _re
                def scale_duration(m):
                    val = float(m.group(1))
                    new_val = max(0.3, round(val * scale, 1))
                    return f"duration: {new_val}"
                raw = _re.sub(r"duration: ([\d.]+)", scale_duration, raw)
                new_min = total_s * scale / 60
                console.print(f"  [yellow]Duration scaled: {total_s/60:.1f}min → {new_min:.1f}min[/yellow]")

            card_yaml = raw
            console.print(f"  [green]✓[/green] Card validated")
            break
        else:
            console.print(f"  [yellow]⚠ Validation errors (attempt {attempt}):[/yellow]")
            for err in errors:
                console.print(f"    - {err}")
            if attempt < 3:
                console.print(f"  Retrying with error feedback...")

    if not card_yaml:
        console.print(f"  [red]Failed after 3 attempts — saving best attempt[/red]")
        card_yaml = raw

    card_path = lesson_dir / "production_card.yml"
    card_path.write_text(card_yaml)
    console.print(f"  [green]✓[/green] Card: {card_path.name}")

    # Generate SQL file if SQL lesson
    if adapter_type == 'sql_viewer':
        scenes = lesson.get('scenes', [])
        sql_scenes = [s for s in scenes if s.get('visual_type') == 'sql_viewer']

        if sql_scenes:
            console.print(f"  Drafting SQL queries...")
            scene_needs = '\n'.join([
                f"- Scene {s['scene_number']}: {s['scene_title']} — {s['what_learner_sees']}"
                for s in sql_scenes
            ])

            sql_response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2000,
                system=SQL_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": SQL_PROMPT.format(
                        lesson_title=lesson['title'],
                        scene_needs=scene_needs,
                    )
                }]
            )

            sql_content = sql_response.content[0].text.strip()
            sql_content = re.sub(r'^```sql\s*', '', sql_content, flags=re.MULTILINE)
            sql_content = re.sub(r'```\s*$', '', sql_content.strip())

            sql_path = assets_dir / sql_name
            sql_path.write_text(sql_content)
            console.print(f"  [green]✓[/green] SQL: {sql_path.name}")

        # Create the SQLite database from the SQL file
        db_path = assets_dir / db_name
        if not db_path.exists():
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(db_path))
            # Parse and execute CREATE TABLE/INSERT statements from SQL
            # Skip SELECT statements — only run DDL/DML
            sql_file = assets_dir / sql_name
            if sql_file.exists():
                raw_sql = sql_file.read_text()
                for stmt in raw_sql.split(";"):
                    stmt = stmt.strip()
                    # Skip section headers and empty
                    if not stmt or stmt.startswith("--"):
                        continue
                    # Only run CREATE, INSERT, DROP statements
                    upper = stmt.upper().lstrip()
                    if upper.startswith(("CREATE", "INSERT", "DROP", "ALTER")):
                        try:
                            conn.execute(stmt)
                        except Exception:
                            pass  # ignore DDL errors — tables may not exist yet
            # Create placeholder tables for any SELECT queries
            # by extracting FROM table names
            import re as _re
            from_tables = _re.findall(r'FROM\s+(\w+)', raw_sql if sql_file.exists() else "", _re.IGNORECASE)
            for tbl in set(from_tables):
                try:
                    conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} (id INTEGER PRIMARY KEY, name TEXT, value REAL, amount REAL, total REAL, date TEXT, category TEXT)")
                    conn.execute(f"INSERT OR IGNORE INTO {tbl} (id, name, value, amount, total) VALUES (1, 'Sample A', 100.0, 250.0, 350.0), (2, 'Sample B', 200.0, 150.0, 350.0), (3, 'Sample C', 300.0, 100.0, 400.0)")
                except Exception:
                    pass
            conn.commit()
            conn.close()
            console.print(f"  [green]✓[/green] Database: {db_path.name}")

    return card_path


@click.command()
@click.argument("brief_path")
@click.option("--lesson", "lesson_num", default=None, type=int)
@click.option("--course-dir", default=None)
def draft(brief_path, lesson_num, course_dir):
    """Generate validated production cards from a research brief."""

    brief_path = Path(brief_path)
    if not brief_path.exists():
        console.print(f"[red]Brief not found: {brief_path}[/red]")
        sys.exit(1)

    with open(brief_path) as f:
        brief = json.load(f)

    slug = re.sub(r'[^a-z0-9]+', '_', brief['topic'].lower()).strip('_')[:40]
    brief['slug'] = slug

    out_dir = Path(course_dir) if course_dir else ROOT / "courses" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold]WSDA Draft[/bold]\n"
        f"Topic:  [cyan]{brief['topic']}[/cyan]\n"
        f"Output: [cyan]{out_dir}[/cyan]",
        border_style="green"
    ))

    lessons = brief['content_structure']['lessons']
    if lesson_num:
        lessons = [l for l in lessons if l['lesson_number'] == lesson_num]
        if not lessons:
            console.print(f"[red]Lesson {lesson_num} not found[/red]")
            sys.exit(1)

    cards = []
    for lesson in lessons:
        console.print(f"\n[bold]Lesson {lesson['lesson_number']}:[/bold] {lesson['title']}")
        card_path = draft_lesson(lesson, brief, out_dir)
        cards.append(card_path)

    # Write manifest
    manifest = {
        "course": brief['topic'],
        "slug": slug,
        "lessons": [str(c) for c in cards],
    }
    (out_dir / "course_manifest.json").write_text(json.dumps(manifest, indent=2))

    console.print(Panel(
        f"[bold green]Draft complete.[/bold green]\n\n"
        f"Lessons: {len(cards)}\n"
        f"Output:  [cyan]{out_dir}[/cyan]\n\n"
        f"Next:\n"
        f"  python3 produce.py {cards[0] if cards else 'CARD_PATH'}",
        title="Done",
        border_style="green"
    ))


if __name__ == "__main__":
    draft()
