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

GROUNDING RULE — NON-NEGOTIABLE:
When verified data is provided in the prompt, that data is the complete and
only truth about what will appear on screen. Every table name, column name,
and number in your narration must come from that verified data, copied
exactly. Do not invent, round differently, or assume any table, column, or
number that isn't listed there. If you're unsure whether something is real,
leave it out rather than guess.

PRONUNCIATION — say identifiers the way a person would say them out loud,
never as raw code syntax. This is about spoken FORM only; the underlying
fact must still be the real, grounded name.
- snake_case columns: say the words naturally. "customer_id" -> "customer
  ID", "total_revenue" -> "total revenue", "order_date" -> "order date".
  Never say "customer underscore id" or run it together as one mangled word.
- Table names: same treatment. "order_summary" -> "order summary table".
- Numbers already covered by GROUNDING RULE, but say them in whichever form
  (digits or spelled out) reads most naturally aloud — either is fine as
  long as the value is exact.

PACING — this is instructional video, not a lecture. Keep it moving.
- Prefer shorter narration blocks over long explanatory ones. If a sentence
  isn't doing real work (advancing the point or reacting to the data), cut it.
- Don't over-explain a concept the learner just watched happen on screen.
  Show it, name it once, move on — don't re-describe what's visually obvious.
- Transitions between actions (opening a file, running a query, switching
  screens) should feel brisk. Narration covering a transition should be
  short enough that the pause never feels like dead air waiting for talking
  to catch up to the action.

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

{verified_data}

NARRATION VOICE REQUIREMENT:
- Use contractions throughout: we're, I'll, you'll, it's, don't, can't, won't
- Casual and warm, like a smart friend explaining something they love
- First 30 seconds must state who this lesson is for and what they'll be able to do
- Never sound like a textbook or a corporate training manual

WIT AND PERSONALITY — narration must have an opinion and a sense of humor,
not just accurately describe what's on screen. Flat, competent-but-boring
narration is a failure state even if every fact is correct. Concretely:
- React to the data like a person would, not a script. Instead of "Row one:
  Greenfield Industries, total spend 23950.00" try "Greenfield Industries
  is out here spending like it's going out of style — 23950.00 in 2024 alone."
- Editorialize honestly. If a number is surprising, say so ("that's almost
  8 grand more than the next customer"). If a query result confirms
  something, have a small moment of satisfaction, not a flat "the numbers
  match."
- Use a running bit or callback where natural (e.g. treating the AI's query
  like a suspect being cross-examined: "the alibi checks out").
- Vary sentence rhythm. Don't narrate every table row in the same
  "Name, region, count, total" cadence — that's what makes it feel like a
  script being read, not a person talking.
- Still every fact must obey the GROUNDING RULE above. Wit is in the
  delivery, never in the numbers.

Additional context:
- Database: {database}
- SQL file: {sql_file}

Generate a production card with rich, over-explained narration.
Every narration block must have a following pause sized correctly.
Use contractions. Use casual speech. Read every number aloud.
Every table, column, and number in the narration must come directly from
the VERIFIED DATA above — nothing assumed, nothing invented.

Return ONLY valid YAML starting with schema_version: "3.0"
"""


NUMBER_FIX_PROMPT = """Your previous production card mentioned numbers, tables,
or columns that don't match the verified data. Fix these specific issues,
keep everything else the same:

{issues}

VERIFIED DATA (the only truth):
{verified_data}

Previous card:
{previous_card}

Return the complete corrected YAML, starting with schema_version: "3.0"
"""


SQL_SYSTEM = """You generate SELF-CONTAINED SQL files for educational lessons.

The file you generate is the ONLY source of truth for the database. It will be
executed exactly as written to build a real SQLite database, and every query
result it produces will be the exact numbers shown on screen and read aloud
in narration. There is no separate schema step. If you don't create it here,
it doesn't exist.

Rules:
1. Start with CREATE TABLE statements for every table the lesson needs.
   Add a one-line comment above each table explaining what it represents.
2. Follow with INSERT statements that seed REALISTIC data. For any query
   that aggregates (SUM, AVG, GROUP BY, COUNT), seed enough rows (8-15 per
   table — no more than needed to make the result meaningful) that the
   aggregation produces a non-trivial result. Use varied, plausible values,
   not round placeholder numbers like 100/200/300. Keep row counts modest;
   this file has a limited size budget and verbose seed data isn't worth
   crowding out the teaching queries.
3. Then add the teaching queries, each in its own section:
   -- [section_name]
   SELECT ...;
   Section names use lowercase and underscores only.
4. Every table and column referenced in a teaching query MUST have been
   created in step 1, using the EXACT same column names — no exceptions.
   Before finishing, mentally re-check each teaching query against your own
   CREATE TABLE statements above: does every column name match exactly
   (same spelling, same table)? A query referencing a column your own
   CREATE TABLE didn't define is the single most common failure here —
   check this specifically before responding.
5. Valid SQLite syntax only. Format code clearly for on-screen display.
6. Include a brief comment above each teaching query explaining what it
   demonstrates.
7. If the lesson needs several distinct queries (e.g. a wrong version and
   a corrected version), keep each one focused and no longer than it needs
   to be — don't pad with extra columns or commentary that isn't essential
   to the teaching point.

Return ONLY the SQL file content. No markdown. No explanation."""


SQL_PROMPT = """Generate a complete, self-contained SQL file for this lesson.

Lesson: {lesson_title}
Scenes needing SQL:
{scene_needs}

This file must include CREATE TABLE statements, INSERT statements with
realistic seed data, and the teaching queries with -- [section_name] headers.
Nothing exists unless you create it in this file. Use realistic column and
table names appropriate for the topic.

Return only the SQL file content."""


DB_BUILD_ERROR_PROMPT = """Your previous SQL file failed to build a working database.

Previous SQL file:
{previous_sql}

Error(s):
{errors}

Fix the file. Remember: every table and column used in a teaching query must
be created and seeded earlier in the SAME file. Return the complete corrected
SQL file, nothing else."""


def parse_sql_sections(sql_content: str) -> dict:
    """Split a SQL file into named SELECT sections (marked with -- [name])."""
    sections, cur, lines = {}, None, []
    for line in sql_content.splitlines():
        m = re.match(r'--\s*\[(\w+)\]', line)
        if m:
            if cur and lines:
                sections[cur] = '\n'.join(lines).strip()
            cur, lines = m.group(1), []
        elif cur is not None:
            lines.append(line)
    if cur and lines:
        sections[cur] = '\n'.join(lines).strip()
    return sections


def build_database_from_sql(db_path: Path, sql_content: str) -> tuple[bool, str]:
    """
    Execute ONLY the DDL/DML (CREATE/INSERT/DROP/ALTER) statements from a SQL
    file to build a real database. No fallback, no placeholder tables — if
    this fails, the SQL file is wrong and must be regenerated.
    Returns (success, error_message).
    """
    import sqlite3 as _sqlite3

    if db_path.exists():
        db_path.unlink()

    conn = _sqlite3.connect(str(db_path))
    try:
        for stmt in sql_content.split(";"):
            # Strip leading full-line comments/blank lines, keep the code
            code_lines = [
                ln for ln in stmt.splitlines()
                if not ln.strip().startswith("--")
            ]
            stmt = "\n".join(code_lines).strip()
            if not stmt:
                continue
            upper = stmt.upper().lstrip()
            if upper.startswith(("CREATE", "INSERT", "DROP", "ALTER")):
                conn.execute(stmt)
        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)
    conn.close()
    return True, ""


def run_verified_queries(db_path: Path, sections: dict) -> tuple[dict, list[str]]:
    """
    Execute every named teaching query against the REAL database and capture
    the exact values that will be displayed (rounded to 2 decimals, same as
    the SQL viewer). Returns (results, errors).
    """
    import sqlite3 as _sqlite3

    results = {}
    errors = []
    conn = _sqlite3.connect(str(db_path))
    try:
        for name, sql in sections.items():
            try:
                cursor = conn.execute(sql)
                cols = [d[0] for d in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                display_rows = []
                for row in rows:
                    display_row = []
                    for val in row:
                        if isinstance(val, float):
                            display_row.append(round(val, 2))
                        else:
                            display_row.append(val)
                    display_rows.append(display_row)
                results[name] = {"columns": cols, "rows": display_rows}
            except Exception as e:
                errors.append(f"Query '{name}' failed: {e}")
    finally:
        conn.close()
    return results, errors


def get_real_schema(db_path: Path) -> dict:
    """Read the actual table/column names that exist in the built database."""
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(db_path))
    schema = {}
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        for t in tables:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
            schema[t] = cols
    finally:
        conn.close()
    return schema


def format_verified_data_block(schema: dict, query_results: dict) -> str:
    """Build the grounding context injected into the narration prompt."""
    lines = ["VERIFIED DATA — this is the ONLY database and result data that exists.",
             "Narration must ONLY reference table names, column names, and numeric",
             "values listed below. Never mention a table, column, or number that",
             "isn't listed here — it will not be on screen.",
             "",
             "REAL TABLES AND COLUMNS:"]
    for table, cols in schema.items():
        lines.append(f"- {table}({', '.join(cols)})")

    lines.append("")
    lines.append("REAL QUERY RESULTS (exact values that will appear on screen, 2 decimals):")
    for name, data in query_results.items():
        lines.append(f"[{name}] columns: {', '.join(data['columns'])}")
        for row in data['rows'][:15]:
            lines.append(f"  {row}")
        if len(data['rows']) > 15:
            lines.append(f"  ... ({len(data['rows']) - 15} more rows)")

    return "\n".join(lines)


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


_NUMERIC_TOKEN_RE = re.compile(r'\$?\d[\d,]*(?:\.\d+)?%?')


def _spoken_word_units(text: str) -> float:
    """
    Estimate how many 'spoken words' a piece of narration actually takes to
    say aloud. Plain words count as 1. Numeric tokens (dollar amounts,
    decimals, percentages) are severely undercounted by a naive word count
    ("23950.00" is one token but "twenty three thousand nine hundred fifty
    dollars" is 7 spoken words) — this is the root cause of pauses being
    too short and TTS audio getting cut off or distorted on numbers.
    """
    units = 0.0
    for tok in text.split():
        stripped = tok.strip('.,;:!?()')
        m = _NUMERIC_TOKEN_RE.fullmatch(stripped)
        if not m:
            units += 1.0
            continue
        digits = re.sub(r'[^\d]', '', stripped)
        has_decimal = '.' in stripped
        # Rough heuristic: ~1 spoken word per 1-2 digits (place-value groups
        # like "thousand", "hundred"), plus a couple words for "dollars"/
        # "percent"/decimal reading.
        word_est = max(2, (len(digits) + 1) // 2 + 1)
        if has_decimal:
            word_est += 2  # "point five zero" / "and fifty cents"
        if '%' in stripped:
            word_est += 1  # "percent"
        units += word_est
    return units


def recompute_pause_durations(raw_yaml: str) -> str:
    """
    Deterministically recalculate every pause duration from the ACTUAL
    narration text using numeric-aware word counting, overriding whatever
    the model computed. This runs before the model's own math is trusted,
    since numeric-heavy narration (dollar amounts especially) is exactly
    where naive word-count pause sizing breaks down and produces audio that
    gets cut off or distorted when the pause window is too short.
    """
    parsed = yaml.safe_load(raw_yaml)
    events = parsed.get('events', [])

    for i, e in enumerate(events):
        narr = (e.get('narration') or '').strip()
        if not narr:
            continue
        # Find the immediately following pause event
        if i + 1 < len(events) and events[i + 1].get('type') == 'pause':
            pause_event = events[i + 1]
            units = _spoken_word_units(narr)
            new_duration = round((units / 145 * 60) + 8, 1)
            pause_event['duration'] = new_duration

    return yaml.dump(parsed, sort_keys=False, allow_unicode=True, width=100)


def enforce_duration_cap(raw_yaml: str, max_s: float) -> tuple:
    """
    If total runtime exceeds the format cap, compress pauses toward their
    minimum safe floor (word-time + 1s margin) rather than uniformly scaling
    every pause by the same ratio. Uniform scaling was the root cause of
    audio getting cut off: it shrank number-dense narration blocks by the
    same percentage as simple ones, even though number-dense narration needs
    MORE time per word, not less.
    Returns (possibly-modified yaml, status message).
    """
    parsed = yaml.safe_load(raw_yaml)
    events = parsed.get('events', [])

    pause_info = []  # (pause_event_dict, floor_dur, current_dur)
    for i, e in enumerate(events):
        narr = (e.get('narration') or '').strip()
        if narr and i + 1 < len(events) and events[i + 1].get('type') == 'pause':
            pause_event = events[i + 1]
            units = _spoken_word_units(narr)
            word_time = units / 145 * 60
            floor_dur = round(word_time + 1.0, 1)
            cur_dur = float(pause_event.get('duration', floor_dur))
            pause_info.append((pause_event, floor_dur, cur_dur))

    total_s = sum(p[2] for p in pause_info)
    if total_s <= max_s * 1.1 or not pause_info:
        return raw_yaml, f"Within cap: {total_s/60:.1f}min"

    total_floor = sum(p[1] for p in pause_info)
    total_slack = sum(p[2] - p[1] for p in pause_info)
    needed_reduction = total_s - max_s

    if needed_reduction <= total_slack and total_slack > 0:
        ratio = needed_reduction / total_slack
        for pause_event, floor_dur, cur_dur in pause_info:
            slack = cur_dur - floor_dur
            pause_event['duration'] = round(cur_dur - slack * ratio, 1)
        new_total = sum(p[0]['duration'] for p in pause_info)
        return (
            yaml.dump(parsed, sort_keys=False, allow_unicode=True, width=100),
            f"Compressed buffer slack: {total_s/60:.1f}min -> {new_total/60:.1f}min",
        )
    else:
        # Can't safely compress further without risking cut-off audio again.
        for pause_event, floor_dur, cur_dur in pause_info:
            pause_event['duration'] = floor_dur
        return (
            yaml.dump(parsed, sort_keys=False, allow_unicode=True, width=100),
            (
                f"WARNING: even at minimum safe pacing this script runs "
                f"{total_floor/60:.1f}min against a {max_s/60:.1f}min cap. "
                f"Durations set to floor, but the narration TEXT needs to be "
                f"shortened - timing math alone can't fix this safely."
            ),
        )


_NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40,
    'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
}
_MAGNITUDE_WORDS = {'hundred': 100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000}


def _words_to_int(tokens: list) -> float:
    """Convert a list of number-word tokens (no 'point') to an integer value."""
    total = 0
    current = 0
    for tok in tokens:
        if tok == 'and':
            continue
        if tok in _NUMBER_WORDS:
            current += _NUMBER_WORDS[tok]
        elif tok in _MAGNITUDE_WORDS:
            if current == 0:
                # A bare magnitude word with no preceding number ("a hundred
                # percent", "thousands of rows") is not a real number phrase
                # — don't fabricate an implicit "one hundred"/"one thousand".
                continue
            mag = _MAGNITUDE_WORDS[tok]
            if mag == 100:
                current = current * 100
            else:
                total += current * mag
                current = 0
    return total + current


def extract_spelled_number_mentions(text: str) -> list:
    """
    Find spelled-out numbers in narration text, e.g. 'ninety-four thousand
    eight hundred seventy point zero zero' -> ('...', 94870.0). Hyphens
    split naturally since word tokenization only matches letters. Needed
    because narration sometimes spells out numbers instead of using digits,
    and digit-only checking (_extract_decimal_mentions) can't see those.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    vocab = set(_NUMBER_WORDS) | set(_MAGNITUDE_WORDS) | {'and', 'point'}
    results = []
    i, n = 0, len(words)
    while i < n:
        if words[i] in vocab and words[i] not in ('and', 'point'):
            j = i
            run = []
            while j < n and words[j] in vocab:
                run.append(words[j])
                j += 1
            while run and run[-1] in ('and', 'point'):
                run.pop()
                j -= 1
            if run:
                if 'point' in run:
                    idx = run.index('point')
                    whole_tokens = [t for t in run[:idx] if t != 'and']
                    dec_tokens = [t for t in run[idx + 1:]
                                  if t in _NUMBER_WORDS and t not in _MAGNITUDE_WORDS]
                    whole_val = _words_to_int(whole_tokens) if whole_tokens else 0
                    dec_digits = ''.join(str(_NUMBER_WORDS[t]) for t in dec_tokens)
                    val = float(f"{int(whole_val)}.{dec_digits}") if dec_digits else float(whole_val)
                else:
                    whole_tokens = [t for t in run if t != 'and']
                    val = float(_words_to_int(whole_tokens))
                # Skip trivial single small-number words (too many false positives,
                # e.g. "two tables", "step one") — only flag numbers that look like
                # they're reporting a real figure (3+ digits or has a decimal).
                if val >= 100 or 'point' in run:
                    results.append((' '.join(run), val))
            i = j
        else:
            i += 1
    return results


def _extract_decimal_mentions(text: str) -> list:
    """Find decimal numbers mentioned in narration text (plain or spelled out)."""
    found = []
    for m in re.finditer(r'\b0\.\d+\b', text):
        found.append((m.group(), float(m.group())))
    word_digits = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                   'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}
    for m in re.finditer(r'zero point (\w+)(?:\s+(\w+))?(?:\s+(\w+))?(?:\s+(\w+))?', text.lower()):
        digits = [word_digits.get(g) for g in m.groups() if g and g in word_digits]
        if digits:
            found.append((m.group(), float("0." + "".join(str(d) for d in digits))))
    return found


def check_number_mismatches(card_yaml: str, query_results: dict) -> list:
    """
    Compare narration in a drafted card against the REAL, verified query
    results. Returns a list of human-readable issue strings, empty if clean.
    """
    all_display_values = set()
    for data in query_results.values():
        for row in data['rows']:
            for v in row:
                if isinstance(v, (int, float)):
                    all_display_values.add(round(float(v), 2))

    parsed = yaml.safe_load(card_yaml)
    issues = []
    for e in parsed.get('events', []):
        narr = (e.get('narration') or '').strip()
        if not narr:
            continue
        mentions = _extract_decimal_mentions(narr) + extract_spelled_number_mentions(narr)
        approx_qualifiers = ('almost', 'about', 'roughly', 'nearly', 'around',
                              'approximately', 'just over', 'just under', 'give or take')
        narr_lower = narr.lower()
        for raw_text, num in mentions:
            idx = narr_lower.find(raw_text.lower())
            preceding = narr_lower[max(0, idx - 25):idx] if idx >= 0 else ''
            if any(q in preceding for q in approx_qualifiers):
                continue  # explicitly framed as an approximation, not a claimed exact value
            if not any(abs(num - v) < 0.01 for v in all_display_values):
                issues.append(
                    f"Event {e.get('id')}: narration says '{raw_text}' ({num}) "
                    f"but no verified query result matches that value."
                )
    return issues


def build_verified_sql_and_db(lesson: dict, lesson_title: str, assets_dir: Path,
                               db_name: str, sql_name: str) -> tuple:
    """
    Generate a self-contained SQL file, execute it to build a REAL database,
    run every teaching query against it, and return (sql_content, db_path,
    query_results). Retries generation if the SQL fails to build or run.
    Raises RuntimeError if it can't produce a working database after retries.
    """
    scenes = lesson.get('scenes', [])
    sql_scenes = [s for s in scenes if s.get('visual_type') == 'sql_viewer']
    scene_needs = '\n'.join([
        f"- Scene {s['scene_number']}: {s['scene_title']} - {s['what_learner_sees']}"
        for s in sql_scenes
    ]) or "- Design queries appropriate to the lesson's learning objective."

    db_path = assets_dir / db_name
    sql_content = None
    query_results = {}
    prior_errors = []

    for attempt in range(1, 4):
        console.print(f"  Drafting SQL + database (attempt {attempt}/3)...")

        if attempt == 1:
            prompt = SQL_PROMPT.format(lesson_title=lesson_title, scene_needs=scene_needs)
        else:
            prompt = DB_BUILD_ERROR_PROMPT.format(
                previous_sql=sql_content or "",
                errors="\n".join(prior_errors),
            )

        sql_response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=6000,
            system=SQL_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        sql_content = sql_response.content[0].text.strip()
        sql_content = re.sub(r'^```sql\s*', '', sql_content, flags=re.MULTILINE)
        sql_content = re.sub(r'```\s*$', '', sql_content.strip())

        ok, build_err = build_database_from_sql(db_path, sql_content)
        if not ok:
            prior_errors = [f"Database build failed: {build_err}"]
            console.print(f"  [yellow]Warning - DB build failed:[/yellow] {build_err}")
            continue

        sections = parse_sql_sections(sql_content)
        if not sections:
            prior_errors = ["No -- [section_name] teaching queries found in the file."]
            console.print(f"  [yellow]Warning - no teaching query sections found[/yellow]")
            continue

        query_results, query_errors = run_verified_queries(db_path, sections)
        if query_errors:
            prior_errors = query_errors
            console.print(f"  [yellow]Warning - query execution errors:[/yellow]")
            for err in query_errors:
                console.print(f"    - {err}")
            continue

        console.print(f"  [green]OK[/green] Database built and all queries verified")
        break
    else:
        raise RuntimeError(
            f"Could not build a working database after 3 attempts. "
            f"Last errors: {prior_errors}"
        )

    sql_path = assets_dir / sql_name
    sql_path.write_text(sql_content)
    console.print(f"  [green]OK[/green] SQL: {sql_path.name}")
    console.print(f"  [green]OK[/green] Database: {db_path.name}")

    return sql_content, db_path, query_results


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

    # STEP 1: for SQL lessons, build the REAL database and run the REAL
    # queries FIRST. Narration gets written only after we know exactly what
    # will be on screen. This is the fix for the narration-visual disconnect.
    query_results = {}
    verified_data_block = ""
    if adapter_type == 'sql_viewer':
        _, db_path, query_results = build_verified_sql_and_db(
            lesson, lesson['title'], assets_dir, db_name, sql_name
        )
        schema = get_real_schema(db_path)
        verified_data_block = format_verified_data_block(schema, query_results)

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
            "The AI responses should contain the core teaching content - definitions, "
            "examples, comparisons - formatted clearly for on-screen reading. "
            "The narration explains and deepens what the learner sees on screen."
        )
    lesson_context = "\n".join(lesson_context_parts)

    # Normalize adapter type for card generation
    card_adapter = "chat_demo" if "chat_demo" in adapter_type else adapter_type

    # STEP 2: generate narration, grounded in verified_data_block for SQL
    # lessons. Retry loop now checks BOTH schema validity AND number accuracy
    # against the real database, not just YAML shape.
    card_yaml = None
    raw = None
    number_issues = []
    for attempt in range(1, 4):
        console.print(f"  Drafting card (attempt {attempt}/3)...")

        if attempt == 1 or not number_issues:
            prompt = DRAFT_PROMPT.format(
                lesson_json=json.dumps(lesson, indent=2),
                topic=brief['topic'],
                target_learner=brief['market_analysis']['target_learner'],
                tone=prod_notes.get('tone', 'conversational'),
                adapter_type=card_adapter,
                lesson_context=lesson_context,
                verified_data=verified_data_block,
                database=db_name,
                sql_file=sql_name,
            )
        else:
            prompt = NUMBER_FIX_PROMPT.format(
                issues="\n".join(number_issues),
                verified_data=verified_data_block,
                previous_card=raw,
            )

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=6000,
            system=DRAFT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```ya?ml\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```\s*$', '', raw.strip())

        valid, errors = validate_card(raw)
        if not valid:
            console.print(f"  [yellow]Warning - validation errors (attempt {attempt}):[/yellow]")
            for err in errors:
                console.print(f"    - {err}")
            if attempt < 3:
                console.print(f"  Retrying with error feedback...")
            number_issues = []
            continue

        # Verified-number check only applies to SQL lessons with real results
        number_issues = check_number_mismatches(raw, query_results) if query_results else []
        if number_issues:
            console.print(f"  [yellow]Warning - number mismatches vs. real database (attempt {attempt}):[/yellow]")
            for iss in number_issues:
                console.print(f"    - {iss}")
            if attempt < 3:
                console.print(f"  Retrying with corrective feedback...")
            continue

        # Deterministically recompute pause durations from actual narration
        # text (numeric-aware), overriding the model's own word-count math.
        # This is the fix for audio getting cut off / distorted on numbers.
        raw = recompute_pause_durations(raw)
        console.print(f"  [green]OK[/green] Pause durations recalculated (numeric-aware)")

        # Enforce duration limit based on format — compress buffer slack only,
        # never below what the narration actually needs to be spoken safely.
        format_limits = {
            "short-video": 5, "tutorial": 12,
            "lesson": 10, "course": 15,
        }
        lesson_format = brief.get("format", "course")
        max_min = format_limits.get(lesson_format, 15)
        max_s = max_min * 60

        raw, cap_message = enforce_duration_cap(raw, max_s)
        console.print(f"  [cyan]{cap_message}[/cyan]")

        card_yaml = raw
        console.print(f"  [green]OK[/green] Card validated - schema clean, numbers verified against real database")
        break

    if not card_yaml:
        console.print(f"  [red]Failed after 3 attempts - saving best attempt (may contain unverified numbers)[/red]")
        card_yaml = raw

    card_path = lesson_dir / "production_card.yml"
    card_path.write_text(card_yaml)
    console.print(f"  [green]OK[/green] Card: {card_path.name}")

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
    failed_lessons = []
    for lesson in lessons:
        console.print(f"\n[bold]Lesson {lesson['lesson_number']}:[/bold] {lesson['title']}")
        try:
            card_path = draft_lesson(lesson, brief, out_dir)
            cards.append(card_path)
        except RuntimeError as e:
            console.print(f"[red]Lesson {lesson['lesson_number']} failed: {e}[/red]")
            console.print("[dim]Skipping this lesson, continuing with any others...[/dim]")
            failed_lessons.append(lesson['lesson_number'])

    if not cards:
        console.print(Panel(
            f"[bold red]All lessons failed.[/bold red]\n\n"
            f"Failed: {failed_lessons}\n"
            f"See errors above — most often this means the SQL generation "
            f"couldn't produce a working database after 3 attempts (schema "
            f"got too complex, or column names drifted between the CREATE "
            f"TABLE and the teaching queries). Try running again — it's a "
            f"fresh model attempt each time.",
            title="Failed",
            border_style="red",
        ))
        sys.exit(1)

    # Write manifest
    manifest = {
        "course": brief['topic'],
        "slug": slug,
        "lessons": [str(c) for c in cards],
    }
    (out_dir / "course_manifest.json").write_text(json.dumps(manifest, indent=2))

    done_msg = (
        f"[bold green]Draft complete.[/bold green]\n\n"
        f"Lessons: {len(cards)}\n"
    )
    if failed_lessons:
        done_msg += f"[yellow]Failed: {failed_lessons}[/yellow]\n"
    done_msg += (
        f"Output:  [cyan]{out_dir}[/cyan]\n\n"
        f"Next:\n"
        f"  python3 produce.py {cards[0] if cards else 'CARD_PATH'}"
    )

    console.print(Panel(
        done_msg,
        title="Done",
        border_style="green" if not failed_lessons else "yellow",
    ))

    if failed_lessons:
        sys.exit(1)


if __name__ == "__main__":
    draft()
