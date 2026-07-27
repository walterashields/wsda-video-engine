#!/usr/bin/env python3
"""
WSDA Draft — production card generator from research brief

Takes a brief.json from research.py and generates validated,
engine-correct production cards ready to run through produce.py.

Usage:
  python3 draft.py research/ai_for_beginners/brief.json
  python3 draft.py research/ai_for_beginners/brief.json --lesson 1
"""

import csv
import json
import re
import sqlite3
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

SCOPE CONSISTENCY — if this lesson only has queries for SOME of the
possible causes/angles a topic could cover (the SQL was capped to keep this
lesson focused), your narration's framing must match exactly what you
actually built, not the original broader idea. Never say a cause is
"fixed", "matched", "handled", or "checked" unless there's a real query in
this lesson that demonstrates it. If your intro or closing checklist lists
N steps/culprits/causes, you must have built a real query for every single
one of them — don't list a step you didn't actually build just because it
was part of the original concept. Two well-demonstrated causes beats three
where one is just asserted.

PRONUNCIATION — say identifiers the way a person would say them out loud,
never as raw code syntax. This is about spoken FORM only; the underlying
fact must still be the real, grounded name.
- snake_case columns: say the words naturally. "customer_id" -> "customer
  ID", "total_revenue" -> "total revenue", "order_date" -> "order date".
  Never say "customer underscore id" or run it together as one mangled word.
- Table names: same treatment. "order_summary" -> "order summary table".
- Numbers: ALWAYS spell them out in words, never write raw digit strings.
  Write "ninety-four thousand eight hundred seventy point zero zero", not
  "94,870.00". This is not optional. Comma-separated digit strings with
  decimals are read aloud unreliably by the voice engine — it can mangle or
  distort them. Spelled-out words read cleanly every time. This applies to
  every number in narration: dollar amounts, row counts, percentages, all
  of it. The exact value must still match GROUNDING RULE exactly — spelling
  it out doesn't change what number it is, only how it's written for speech.
- Exception: for dollar amounts of $100 or more, rounding to the nearest
  whole dollar is fine and expected — nobody says "eleven thousand eight
  hundred forty eight dollars and seventy five cents" out loud. Say "eleven
  thousand eight hundred forty eight dollars." Cents only matter for
  amounts under $100 where they're a meaningful fraction of the total.

PACING — this is instructional video, not a lecture. Keep it moving.
- Prefer shorter narration blocks over long explanatory ones. If a sentence
  isn't doing real work (advancing the point or reacting to the data), cut it.
- Don't over-explain a concept the learner just watched happen on screen.
  Show it, name it once, move on — don't re-describe what's visually obvious.
- Transitions between actions (opening a file, running a query, switching
  screens) should feel brisk. Narration covering a transition should be
  short enough that the pause never feels like dead air waiting for talking
  to catch up to the action.

RESULT-SET NARRATION — never read out every row and column of a query
result. The viewer can already see the table on screen; your job is to
point out what MATTERS, not transcribe what's visible.
- Call out 1-2 representative or most-notable rows by name/value, describe
  the overall pattern or takeaway, and move on. "Five rows here, and every
  one comes in higher than we'd expect" beats reading all five rows' every
  column aloud.
- This applies doubly to any counting claim ("X rows have Y") — state it
  once, confidently, and don't re-verify it by re-reading each row's value
  aloud as proof.

VISUAL PROGRESSION — every time narration introduces a new point ("trap
two", "here's another issue with this same query"), something on screen
must actually change to go with it. Never write a highlight_section event
that targets the exact same section as the previous one with nothing in
between — that produces zero visual change while the viewer hears entirely
new content, and it reads as the video being frozen or broken.
If you want to make a second or third analytical point using data that's
already displayed (e.g. pointing out something else in a result set
already on screen), use zoom_result or compare_results to visually shift
emphasis — never just repeat the same highlight_section call.

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

CLARITY TECHNIQUE — REQUIRED — before any query or number, translate the
technical concept into a plain, physical, everyday image in the SAME
breath you introduce it. Never state a technical term and move on assuming
it lands. "GROUP BY collapses rows that share a value" means nothing to
someone learning it — "GROUP BY is basically dumping everyone with the
same last name into one pile" does. If a sentence has a technical term in
it, the next clause (not the next sentence, the same sentence) should
translate it into something physical: piles, buckets, a shared group
chat, a receipt, a lineup, a filing cabinet. This is not optional
decoration — it's the actual mechanism by which a viewer understands the
concept. A lesson can be funny and still confusing; it can also be totally
serious and still clear. Clarity comes from the analogy, not the jokes.

STATE THE ACTUAL THRESHOLD — if a WHERE clause or filter has a specific
value that decides what's included or excluded (a cutoff date, a row
count, a dollar amount), that value MUST be spoken explicitly at least
once — never just "the cutoff" or "the threshold" with no actual number
attached. A viewer who can't hear the boundary value can't verify the
classification logic themselves; they just have to trust you. If the SQL
says `< '2023-01-01'`, narration must say something like "before January
2023" — not just "before the cutoff."

WIT AND PERSONALITY — narration must have an opinion and a sense of humor,
not just accurately describe what's on screen. Flat, competent-but-boring
narration is a failure state even if every fact is correct and even if it
technically contains an analogy. Concrete mechanisms that actually work:
- React to the data like a person would, not a script. Instead of "Row one:
  Greenfield Industries, total spend 23950.00" try "Greenfield Industries
  is out here spending like it's going out of style — 23950.00 in 2024 alone."
- Editorialize honestly. If a number is surprising, say so ("that's almost
  8 grand more than the next customer"). If a query result confirms
  something, have a small moment of satisfaction, not a flat "the numbers
  match."
- Treat the bug/problem like a character: give it a personality, catch it
  in the act, let the narrator be a little smug when they nail it.
- Self-aware asides land well in short-form: "yes, again," "shocking, I
  know," "you saw this coming." Use sparingly — one per lesson, not one
  per sentence.
- Understatement beats exaggeration. "That's... not great" lands harder
  than "This is a DISASTER."
- Vary sentence rhythm. Don't narrate every table row in the same
  "Name, region, count, total" cadence — that's what makes it feel like a
  script being read, not a person talking.
- Still every fact must obey the GROUNDING RULE above. Wit is in the
  delivery, never in the numbers.

WORKED EXAMPLE — this is the target voice, not a topic to copy. Notice the
analogy lands in the SAME breath as the technical term, the hook is a
scenario not a topic statement, and the humor comes from character/timing,
not jokes bolted onto the end:

"Okay so your JOIN just invited someone to the party who wasn't on the
list. Every order in this table is about to get matched to a customer —
except one of them doesn't have a match, so SQL just shrugs and hands it a
name tag that says NULL. Watch: nine orders go in... [run query]
...and one of them comes back with no customer name at all. That's not a
bug, that's LEFT JOIN doing exactly what you asked — keep every order,
even the friendless ones. The bug is if you didn't know that was coming."

Notice: "invited someone to the party who wasn't on the list" IS the
analogy for an unmatched join key — it's not a joke added after the
explanation, it replaces the dry technical explanation entirely.

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
8. Don't mix a grand-total/summary row into the same result set as detail
   rows (e.g. a UNION ALL adding a "TOTAL" row at the bottom). If a query
   is meant to show individual rows and someone will count how many have a
   property (like NULL in some column), a summary row can itself show NULL
   in that column and get miscounted as a real row. Keep detail queries and
   aggregate/summary queries as separate sections.

Return ONLY the SQL file content. No markdown. No explanation."""


SQL_PROMPT = """Generate a complete, self-contained SQL file for this lesson.

Lesson: {lesson_title}
Scenes needing SQL:
{scene_needs}

This file must include CREATE TABLE statements, INSERT statements with
realistic seed data, and the teaching queries with -- [section_name] headers.
Nothing exists unless you create it in this file. Use realistic column and
table names appropriate for the topic.

HARD LIMIT: no more than 4 teaching query sections total, regardless of how
many scenes are listed above or how many distinct causes/angles the topic
could touch on. If this topic could plausibly have several different root
causes (e.g. a data mismatch could come from duplicate joins, OR null
handling, OR timezone/date-boundary drift), do NOT build a query for each
one. Pick the SINGLE clearest, most illustrative cause and build the whole
lesson around just that one: show the wrong result, isolate why it's wrong,
show the fix. A short lesson teaches one thing well — covering every
possible cause turns a 5-minute lesson into a 20-minute one. If the scenes
list above implies more than 4 distinct query moments, consolidate or cut
rather than generating all of them.

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
                if not display_rows:
                    errors.append(
                        f"Query '{name}' ran successfully but returned ZERO rows. "
                        f"An empty result set demonstrates nothing to a viewer - this "
                        f"is a real failure even though it's not a SQL error. Fix the "
                        f"seed data or the query so it returns actual rows."
                    )
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

    Only sql_viewer and chat_demo are real, built adapters. If a lesson's
    own scenes explicitly call for a tool with no adapter (excel, powerbi,
    python, terminal), silently falling back to chat_demo would produce a
    lesson where the screen shows a chat interface while narration
    describes clicking through completely different software - a direct
    content-accuracy mismatch. Fail loudly instead so this gets caught at
    draft time, not discovered by a viewer.
    """
    scenes = lesson.get('scenes', [])
    visual_types = [s.get('visual_type', '') for s in scenes]
    title = lesson.get('title', '').lower()
    objective = lesson.get('learning_objective', '').lower()

    # SQL viewer: explicit SQL content
    if 'sql_viewer' in visual_types:
        return 'sql_viewer'

    # No adapter exists for these yet - fail loudly rather than silently
    # substituting a mismatched visual.
    unbuilt_adapters = {'excel', 'powerbi', 'power_bi', 'python', 'terminal'}
    unbuilt_requested = [v for v in visual_types if v in unbuilt_adapters]
    if unbuilt_requested:
        raise RuntimeError(
            f"This lesson's scenes call for {unbuilt_requested}, but no "
            f"adapter exists for {unbuilt_requested} yet — only sql_viewer "
            f"and chat_demo are built. Producing this lesson would show a "
            f"chat interface or SQL viewer on screen while narration "
            f"describes different software, which is a real accuracy "
            f"mismatch, not a cosmetic one. Choose a topic that uses SQL or "
            f"ChatGPT, or wait until an adapter for "
            f"{unbuilt_requested[0]} is built."
        )

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

    # Check for frozen-screen repeats: a highlight_section that targets the
    # SAME section as the previous "screen-setting" action, with no
    # run_query/show_result/zoom_result/compare_results in between, produces
    # zero visual change even though narration introduces new content. This
    # is exactly the "screen never shifts" bug — the model wrote a new
    # analytical point without building any new visual for it.
    screen_setting_types = {
        'highlight_section', 'run_query', 'show_result',
        'zoom_result', 'compare_results', 'highlight_result',
    }
    last_section_target = None
    for i, e in enumerate(events):
        etype = e.get('type')
        if etype not in screen_setting_types:
            continue
        if etype == 'highlight_section':
            target = e.get('section')
            if target is not None and target == last_section_target:
                errors.append(
                    f"Event {e['id']}: highlight_section repeats the same "
                    f"target ('{target}') as the previous screen-setting "
                    f"event, with no run_query/show_result/zoom_result in "
                    f"between — this produces NO visual change on screen. "
                    f"If this narration makes a new point using data already "
                    f"shown, use zoom_result or compare_results instead of "
                    f"re-highlighting the same section."
                )
            last_section_target = target
        else:
            # Any other screen-setting action resets the repeat tracker,
            # since it DID produce a real visual change.
            last_section_target = None

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

    Splits on punctuation FIRST (commas, periods, semicolons, colons) so a
    number-word run never crosses a real sentence/list boundary. Without
    this, "order 1001, eighty-four forty-nine" reads as two adjacent
    numbers in the vocabulary with nothing (after stripping punctuation)
    to separate them, and gets merged into one garbage number
    (1001 -> "one thousand one", 84.49 -> "eighty four point four nine",
    concatenated into 1085.49). Punctuation is the boundary; losing it
    before scanning caused this.
    """
    vocab = set(_NUMBER_WORDS) | set(_MAGNITUDE_WORDS) | {'and', 'point'}
    results = []

    for segment in re.split(r'[,.;:]', text.lower()):
        words = re.findall(r"[a-zA-Z']+", segment)
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
                    # Skip trivial single small-number words (too many false
                    # positives, e.g. "two tables", "step one") — only flag
                    # numbers that look like they're reporting a real figure.
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


_COVERAGE_CONCEPTS = {
    'fan-out': ['fan-out', 'fanout', 'fan out', 'duplicate row', 'duplicate join'],
    'filters': ['filter', 'where clause', 'test account', 'test order', 'refunded'],
    'nulls': ['null', 'coalesce'],
    'timezone': ['time zone', 'timezone', 'utc', 'eastern', 'boundary'],
    'metric definition': ['metric definition', 'revenue definition', 'line item'],
}

_COVERAGE_CLAIM_VERBS = ('matched', 'fixed', 'handled', 'solved', 'resolved',
                          'done', 'covered', 'addressed', 'checked')


REVIEW_SYSTEM = """You are a ruthless content-accuracy reviewer for short instructional videos.
Your ONLY job is to find real, concrete mismatches between what a lesson
claims to teach and what it actually demonstrates. You are not a copy
editor and you don't care about style, wit, prose quality, or pacing -
only fidelity between claim and demonstration.

Check specifically for:
- Does every SQL construct or technique the title, hook, or narration says
  it will show ACTUALLY appear in the real SQL and get demonstrated?
- Does the visual sequence (schema, queries, results) match what the
  narration describes happening, in the right order?
- Are there any claims of "the fix" or "here's what changed" where the
  actual before/after queries don't show a meaningful, real difference?
- Is there any point where narration promises something is coming next
  that never actually appears anywhere in the lesson?
- Is the core teaching point (the title's claim) actually, clearly proven
  by the real query results a viewer will see on screen?
- If the SQL has a WHERE clause or filter with a specific threshold value
  that determines what gets included or excluded (a cutoff date, a row
  count, a dollar amount), is that ACTUAL value ever explicitly stated in
  narration — not just referenced abstractly as "the cutoff" or "the
  threshold"? A viewer can't verify classification logic they can't see
  the boundary of. Be careful here: a coincidentally similar-looking value
  appearing elsewhere (e.g. an example row's date happening to fall in the
  same year as the cutoff) does NOT count as stating the threshold — the
  actual boundary value itself must be spoken.

Do NOT flag: writing style, humor choices, pacing, whether it's funny
enough, or minor phrasing. Only flag concrete mismatches between what's
claimed and what's actually demonstrated.

If you find real issues, list each as a single concise sentence, one per
line. If there are truly no issues, respond with exactly: NONE"""


REVIEW_PROMPT = """Lesson title: {title}
Hook: {hook}
Key takeaway: {key_takeaway}

REAL SQL FILE (this is the only thing that will actually execute):
{sql_content}

FULL NARRATION (in order):
{narration_text}

Does this lesson's SQL and narration actually deliver on what the title,
hook, and key takeaway promise? List concrete mismatches only, one per
line. If none, respond with exactly: NONE"""


def review_lesson_fidelity(lesson_title: str, hook: str, key_takeaway: str,
                            sql_content: str, card_yaml: str) -> list:
    """
    A holistic quality check, distinct from every other check in this file.
    The number/concept/section checks above are all narrow pattern-matchers
    for specific failure modes already observed - each one only catches the
    exact thing it was written for. This is different: it asks a fresh
    model to actually read the lesson as a skeptical viewer would and judge
    whether it delivers on its own promise, catching mismatches nobody
    specifically anticipated. This costs one extra API call per attempt -
    worth it because "does this lesson actually teach what it claims to"
    is the single most important question and nothing else here asks it.
    """
    parsed = yaml.safe_load(card_yaml)
    narration_text = '\n'.join(
        f"[{e.get('id')}] {e.get('narration')}"
        for e in parsed.get('events', []) if e.get('narration')
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        system=REVIEW_SYSTEM,
        messages=[{
            "role": "user",
            "content": REVIEW_PROMPT.format(
                title=lesson_title, hook=hook, key_takeaway=key_takeaway,
                sql_content=sql_content, narration_text=narration_text,
            )
        }]
    )
    text = response.content[0].text.strip()
    if not text or text.upper().startswith("NONE"):
        return []
    return [line.lstrip('-• ').strip() for line in text.splitlines() if line.strip()]


def check_unbuilt_concept_claims(card_yaml: str) -> list:
    """
    Catches a specific failure mode a numeric section-count check can't see:
    narration asserting a concept is "matched"/"fixed"/"handled" (e.g. "fan-out's
    fixed, filters are matched") when no real query anywhere in the lesson
    actually covers that concept. This happens when scope-capping forces
    dropping a cause's query, but transitional/closing narration still
    references it as if it were taught. Counting real query sections doesn't
    catch this: a lesson can have 4 real sections that only cover 2 concepts,
    while still claiming a 3rd.
    """
    parsed = yaml.safe_load(card_yaml)
    events = parsed.get('events', [])

    # Narration tied to an actual run_query (i.e., backed by a real, verified
    # query) vs. all narration (which includes intro/transition/closing text
    # that isn't necessarily backed by anything real).
    query_backed_narration = []
    for i, e in enumerate(events):
        if e.get('type') == 'run_query':
            # narration usually lives on the following show_result event
            for j in range(i, min(i + 3, len(events))):
                if events[j].get('narration'):
                    query_backed_narration.append(events[j]['narration'].lower())

    query_backed_text = ' '.join(query_backed_narration)
    all_text = ' '.join((e.get('narration') or '') for e in events).lower()

    issues = []
    claim_pattern = re.compile(
        r'([a-z][a-z \-]{2,30}?)(?:\'s|\s+is|\s+are|\s+was|\s+were)?\s+(?:' +
        '|'.join(_COVERAGE_CLAIM_VERBS) + r')\b'
    )

    for concept, keywords in _COVERAGE_CONCEPTS.items():
        # Is this concept CLAIMED as handled anywhere in the full narration?
        claimed = any(
            re.search(rf'\b{re.escape(kw)}s?\b.{{0,20}}\b(?:' + '|'.join(_COVERAGE_CLAIM_VERBS) + r')\b', all_text)
            or re.search(rf'\b(?:' + '|'.join(_COVERAGE_CLAIM_VERBS) + rf')\b.{{0,20}}\b{re.escape(kw)}s?\b', all_text)
            for kw in keywords
        )
        if not claimed:
            continue
        # Is it actually backed by a real query anywhere?
        backed = any(re.search(rf'\b{re.escape(kw)}s?\b', query_backed_text) for kw in keywords)
        if not backed:
            issues.append(
                f"Narration claims '{concept}' is matched/fixed/handled, but no "
                f"run_query event's narration actually demonstrates it — this "
                f"concept was referenced as covered without a real query behind "
                f"it. Either add a real query for it, or remove the claim."
            )
    return issues


def check_number_mismatches(card_yaml: str, query_results: dict) -> list:
    """
    Compare narration in a drafted card against REAL, verified query results.

    A number is valid if it matches the CURRENT event's own query, OR any
    query already revealed earlier in the timeline — "diagnose then fix"
    lessons legitimately compare a new result to an earlier one ("compare
    that to the $X we saw before"), and that's not an error. What's actually
    wrong is a number that doesn't match anything real yet shown, or that
    only exists in a query that hasn't been revealed yet (a forward
    reference the viewer can't have seen).
    """
    query_display_values = {}
    for name, data in query_results.items():
        vals = set()
        for row in data['rows']:
            for v in row:
                if isinstance(v, (int, float)):
                    vals.add(round(float(v), 2))
        query_display_values[name] = vals

    parsed = yaml.safe_load(card_yaml)
    events = parsed.get('events', [])
    issues = []
    approx_qualifiers = ('almost', 'about', 'roughly', 'nearly', 'around',
                          'approximately', 'just over', 'just under', 'give or take')

    revealed_so_far = set()  # cumulative query_refs shown up to this point

    for i, e in enumerate(events):
        if e.get('query_ref') and e['query_ref'] in query_display_values:
            revealed_so_far.add(e['query_ref'])

        narr = (e.get('narration') or '').strip()
        if not narr:
            continue

        # Values from every query already revealed by this point in the
        # timeline are all fair game for comparative narration.
        allowed_values = set()
        for ref in revealed_so_far:
            allowed_values |= query_display_values[ref]

        if not allowed_values:
            continue  # nothing revealed yet (e.g. intro) - nothing to check

        mentions = _extract_decimal_mentions(narr) + extract_spelled_number_mentions(narr)
        narr_lower = narr.lower()

        for raw_text, num in mentions:
            idx = narr_lower.find(raw_text.lower())
            preceding = narr_lower[max(0, idx - 25):idx] if idx >= 0 else ''
            if any(q in preceding for q in approx_qualifiers):
                continue
            if not any(abs(num - v) < (1.0 if abs(v) >= 100 else 0.01) for v in allowed_values):
                issues.append(
                    f"Event {e.get('id')}: narration says '{raw_text}' ({num}) "
                    f"but this doesn't match any query result revealed so far "
                    f"({sorted(allowed_values)}) — likely a fabricated number "
                    f"or a reference to a query that hasn't been shown yet."
                )
    return issues


_TOPIC_SQL_CONSTRUCTS = {
    'where': (r'\bwhere\b', 'WHERE clause'),
    'join': (r'\bjoin\b', 'JOIN'),
    'left join': (r'\bleft\s+join\b', 'LEFT JOIN'),
    'group by': (r'\bgroup\s+by\b', 'GROUP BY'),
    'having': (r'\bhaving\b', 'HAVING'),
    'distinct': (r'\bdistinct\b', 'DISTINCT'),
    'union': (r'\bunion\b', 'UNION'),
    'subquery': (r'\bselect\b[\s\S]*\bselect\b', 'a subquery'),
    'case when': (r'\bcase\s+when\b', 'CASE WHEN'),
    'window function': (r'\bover\s*\(', 'a window function'),
    'null': (r'\bis\s+null\b|\bcoalesce\b', 'NULL handling'),
    'duplicate': (r'\bcount\s*\(', 'a COUNT to reveal duplicates'),
}


_ONES_WORDS_REV = {v: k for k, v in _NUMBER_WORDS.items() if v < 20}
_TENS_WORDS_REV = {v: k for k, v in _NUMBER_WORDS.items() if v >= 20 and v < 100}


def _int_to_words_0_99(n: int) -> str:
    if n < 20:
        return _ONES_WORDS_REV.get(n, str(n))
    tens = (n // 10) * 10
    ones = n % 10
    tens_word = _TENS_WORDS_REV.get(tens, str(tens))
    return f"{tens_word} {_ONES_WORDS_REV[ones]}" if ones else tens_word


def _year_spoken_forms(year: int) -> list:
    """All plausible ways a person would actually say a year aloud."""
    forms = [str(year)]
    if 2000 <= year < 2100:
        remainder = year - 2000
        if remainder == 0:
            forms.append("two thousand")
        else:
            forms.append(f"twenty {_int_to_words_0_99(remainder)}")
            forms.append(f"two thousand {_int_to_words_0_99(remainder)}")
            forms.append(f"two thousand and {_int_to_words_0_99(remainder)}")
    return forms


def check_where_date_literals_mentioned(sql_content: str, card_yaml: str) -> list:
    """
    If a WHERE clause hinges on a specific date cutoff/threshold, that date
    must actually be spoken in narration somewhere — not just referenced
    abstractly ("the cutoff", "before that date"). A threshold that defines
    the entire lesson's logic but is never stated leaves viewers unable to
    verify the reasoning themselves; they just have to trust the narrator
    that the classification is correct.
    """
    where_clauses = re.findall(
        r'\bWHERE\b(.*?)(?:;|--\s*\[|\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|$)',
        sql_content, re.IGNORECASE | re.DOTALL
    )
    years_found = set()
    for clause in where_clauses:
        for m in re.finditer(r"'(\d{4})-(\d{2})-(\d{2})'", clause):
            years_found.add(int(m.group(1)))

    if not years_found:
        return []

    parsed = yaml.safe_load(card_yaml)
    all_narration = ' '.join((e.get('narration') or '') for e in parsed.get('events', [])).lower()
    all_narration = all_narration.replace('-', ' ')

    issues = []
    for year in years_found:
        forms = _year_spoken_forms(year)
        if not any(f in all_narration for f in forms):
            issues.append(
                f"The SQL's WHERE clause uses a cutoff date in {year}, but "
                f"no spoken form of that year ever appears in the narration. "
                f"A threshold this central to the lesson's logic must "
                f"actually be stated ('before January 2023' or similar), not "
                f"just referenced abstractly as 'the cutoff' — otherwise the "
                f"viewer can't verify the classification themselves."
            )
    return issues


def check_sql_matches_topic(sql_content: str, lesson_title: str, hook: str = "") -> list:
    """
    If the lesson's own title/hook centers on a specific SQL construct
    (e.g. "why your WHERE clause...", "LEFT JOIN traps"), the generated SQL
    must actually contain that construct. Catches lessons that claim to
    teach one thing but only build a query demonstrating something else
    entirely (e.g. a "WHERE clause" lesson whose query has no WHERE clause,
    just a GROUP BY).
    """
    text = f"{lesson_title} {hook}".lower()
    sql_lower = sql_content.lower()
    issues = []
    for keyword, (pattern, label) in _TOPIC_SQL_CONSTRUCTS.items():
        if keyword in text:
            if not re.search(pattern, sql_lower):
                issues.append(
                    f"The lesson title/hook centers on '{keyword}', but the "
                    f"generated SQL doesn't actually contain {label} anywhere. "
                    f"The SQL must demonstrate the exact construct the lesson "
                    f"claims to teach."
                )
    return issues


def build_verified_sql_and_db(lesson: dict, lesson_title: str, assets_dir: Path,
                               db_name: str, sql_name: str, max_sections: int = 4,
                               hook: str = "") -> tuple:
    """
    Generate a self-contained SQL file, execute it to build a REAL database,
    run every teaching query against it, and return (sql_content, db_path,
    query_results). Retries generation if the SQL fails to build or run.
    Raises RuntimeError if it can't produce a working database after retries.
    max_sections caps how many teaching queries are allowed - scaled down
    for micro-format lessons where even 4 queries is far too much content
    for a 1-3 minute video.
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

        topic_issues = check_sql_matches_topic(sql_content, lesson_title, hook)
        if topic_issues:
            prior_errors = topic_issues
            console.print(f"  [yellow]Warning - SQL doesn't match the lesson's own topic:[/yellow]")
            for iss in topic_issues:
                console.print(f"    - {iss}")
            continue

        sections = parse_sql_sections(sql_content)
        if not sections:
            prior_errors = ["No -- [section_name] teaching queries found in the file."]
            console.print(f"  [yellow]Warning - no teaching query sections found[/yellow]")
            continue

        if len(sections) > max_sections:
            prior_errors = [
                f"Generated {len(sections)} teaching query sections "
                f"({', '.join(sections.keys())}) — this exceeds the "
                f"{max_sections}-section limit. This is almost always a scope "
                f"problem, not a SQL problem: pick ONE clear root cause / "
                f"narrative thread for this lesson and consolidate down to at "
                f"most {max_sections} queries total. Do not try to cover every possible angle."
            ]
            console.print(
                f"  [yellow]Warning - too many query sections ({len(sections)}), "
                f"lesson is over-scoped[/yellow]"
            )
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


def generate_exercise_files(sql_content: str, db_path: Path, output_dir: Path,
                             hands_on_style: str) -> list:
    """
    Produce real, downloadable exercise materials when hands_on_style is
    'moderate' or 'heavy' - a CSV export of the lesson's actual verified
    dataset, a starter SQL file with the teaching queries blanked out
    (schema and seed data intact, so the learner practices on the exact
    same real data shown in the video), and an answer key.

    'light' produces nothing - selecting it means no exercise materials,
    not just softer narration. Before this function existed, EVERY
    hands-on selection produced zero actual files regardless of choice;
    this is what makes "heavy" mean something concrete.
    """
    if hands_on_style not in ('moderate', 'heavy'):
        return []

    exercise_dir = output_dir / "exercise"
    exercise_dir.mkdir(exist_ok=True)
    created = []

    conn = sqlite3.connect(str(db_path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        for t in tables:
            csv_path = exercise_dir / f"{t}.csv"
            cursor = conn.execute(f"SELECT * FROM {t}")
            cols = [d[0] for d in cursor.description]
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(cursor.fetchall())
            created.append(csv_path)
    finally:
        conn.close()

    sections = parse_sql_sections(sql_content)
    starter_content = sql_content
    for name, body in sections.items():
        starter_content = starter_content.replace(
            body, f"-- Your turn: write the query for '{name}' here\n"
        )
    starter_path = exercise_dir / "practice_starter.sql"
    starter_path.write_text(starter_content)
    created.append(starter_path)

    answer_path = exercise_dir / "answer_key.sql"
    answer_path.write_text(sql_content)
    created.append(answer_path)

    return created


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
    lesson_format = brief.get("format", "course")

    db_name = f"{slug}.db" if adapter_type == 'sql_viewer' else 'none'
    sql_name = f"lesson_{lesson_num}_queries.sql" if adapter_type == 'sql_viewer' else 'none'

    console.print(f"  Adapter: [cyan]{adapter_type}[/cyan]")

    # STEP 1: for SQL lessons, build the REAL database and run the REAL
    # queries FIRST. Narration gets written only after we know exactly what
    # will be on screen. This is the fix for the narration-visual disconnect.
    query_results = {}
    verified_data_block = ""
    sql_content = ""
    if adapter_type == 'sql_viewer':
        max_sections = 1 if lesson_format == "micro" else 4
        sql_content, db_path, query_results = build_verified_sql_and_db(
            lesson, lesson['title'], assets_dir, db_name, sql_name,
            max_sections=max_sections, hook=brief.get('hook', ''),
        )
        schema = get_real_schema(db_path)
        verified_data_block = format_verified_data_block(schema, query_results)

        hands_on_style = brief.get('hands_on_style', 'moderate')
        exercise_files = generate_exercise_files(
            sql_content, db_path, lesson_dir, hands_on_style
        )
        if exercise_files:
            console.print(
                f"  [green]OK[/green] Exercise files ({hands_on_style}): "
                f"{', '.join(f.name for f in exercise_files)}"
            )
        else:
            console.print(f"  [dim]No exercise files (hands-on: {hands_on_style})[/dim]")

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
    if lesson_format == "micro":
        lesson_context_parts.append(
            "CRITICAL - THIS IS A MICRO/SHORT-FORM VIDEO (1-3 minutes total, feed-scroll "
            "context - TikTok/Reels/Shorts). Everything about this lesson must be built "
            "for extreme brevity without losing clarity:\n"
            "- ONE idea, one payoff. Not a framework, not a checklist, not multiple causes. "
            "Pick the single most surprising or useful angle and build the whole thing "
            "around just that.\n"
            "- Hook in the first 3 seconds - no warm-up, no 'let's start by...', open on "
            "the surprising thing itself.\n"
            "- Every sentence has to earn its place. If a sentence doesn't advance the "
            "point or land the joke, cut it, even if it feels informative.\n"
            "- Funny and fast beats thorough. This is entertainment-shaped education, not "
            "a tutorial. A viewer should smile or go 'oh no' at least once.\n"
            "- No recap, no checklist ending. Land the point and get out. If there's a "
            "closing line, it's a punchline or a sharp final beat, not a summary.\n"
            "- Never sacrifice the GROUNDING RULE for brevity - it's fine to show fewer "
            "numbers, but every number you do show must still be exactly real.\n"
            "- Brevity pressure is exactly when clarity gets sacrificed first - don't let "
            "it. The CLARITY TECHNIQUE (translate the technical term into a physical "
            "image in the same breath) matters MORE here, not less, because there's no "
            "time for a second explanation if the first one doesn't land."
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
        concept_issues = check_unbuilt_concept_claims(raw) if query_results else []
        date_issues = check_where_date_literals_mentioned(sql_content, raw) if query_results else []
        number_issues = number_issues + concept_issues + date_issues

        # Holistic fidelity review - a fresh model reads the lesson as a
        # skeptical viewer and judges whether it delivers on its own title/
        # hook/takeaway. Only run once the cheaper checks above pass, since
        # this costs an extra API call and there's no point spending it on
        # a card that's already going to be rejected for other reasons.
        if not number_issues and query_results:
            fidelity_issues = review_lesson_fidelity(
                lesson['title'], brief.get('hook', ''),
                lesson.get('key_takeaway', ''), sql_content, raw,
            )
            number_issues = number_issues + fidelity_issues

        if number_issues:
            console.print(f"  [yellow]Warning - issues found (attempt {attempt}):[/yellow]")
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
            "micro": 3, "short-video": 5, "tutorial": 12,
            "lesson": 10, "course": 15,
        }
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
