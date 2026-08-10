"""
WSDA Lesson Generator — AI Prompts

Engineered prompts for consistent, high-quality lesson generation.
"""

CONCEPT_DESIGN = """You are an expert data analytics instructor designing a 90-second video lesson.

TOPIC: {topic}

Design a lesson that teaches this SQL concept through **ambiguity and contrast**.
The student should see the SAME question answered THREE different ways,
and understand WHY the answers differ.

Output JSON:
{{
  "title": "Compelling 5-7 word title",
  "lesson_id": "{course_id}-{lesson_num:02d}",
  "hook": "One sentence that creates curiosity (e.g., 'Three analysts ran the same report. Three got different numbers.')",
  "stakes": "One sentence on why this matters (e.g., 'Your CEO doesn't care whose query is right. She cares that revenue is wrong.')",
  "concept": "The SQL concept being taught",
  "question": "The business question being asked (e.g., 'What is our total revenue by region?')",
  "tables_needed": 3,
  "table_descriptions": [
    {{
      "name": "table_name",
      "purpose": "What this table represents and why it exists",
      "columns": ["col1 TYPE", "col2 TYPE"],
      "row_count": 20
    }}
  ],
  "query_variants": [
    {{
      "ref": "query_1",
      "name": "Short descriptive name",
      "approach": "Which table/columns it uses and why",
      "insight": "What result it produces and the trap",
      "sql": "The actual SQL query"
    }}
  ]
}}

Rules:
- Each query must use a DIFFERENT table or join strategy
- The results must be NUMERICALLY DIFFERENT (not just formatted differently)
- The third query should be the "correct" or most complete one
- Include at least one JOIN, one aggregate (SUM/COUNT), and one GROUP BY
"""

SCHEMA_DESIGN = """You are a database architect. Given this lesson concept, design a SQLite schema.

CONCEPT:
{concept_json}

Generate:
1. CREATE TABLE statements (SQLite syntax)
2. INSERT statements with realistic data (at least 20 rows per table)
3. All three queries from the concept, verified to run against this data

Requirements:
- Use INTEGER, REAL, TEXT types only
- Include PRIMARY KEY and FOREIGN KEY where appropriate
- Data should be realistic (real company names, regions, dollar amounts)
- Query results must be DIFFERENT from each other
- Include a subtle data quality issue (duplicate, null, or mismatch) that causes the ambiguity

Output as JSON:
{{
  "create_statements": ["CREATE TABLE..."],
  "insert_statements": ["INSERT INTO..."],
  "verified_queries": [
    {{
      "ref": "query_1",
      "sql": "SELECT...",
      "columns": ["region", "total_revenue"],
      "rows": [["North", 125000.50], ...]
    }}
  ]
}}
"""

NARRATION_SCRIPT = """You are a video scriptwriter for data analytics education.

Write narration for a 90-second video lesson. Each line will be spoken by ElevenLabs TTS.

LESSON:
{concept_json}

QUERIES AND RESULTS:
{query_results_json}

Write narration as a JSON array of events. Each event has:
- id: unique identifier
- type: event type
- narration: what the narrator says (natural, conversational, no filler words)
- params: event parameters

Event types available:
- show_title_card: badge, headline, sub, stakes
- hide_title_card
- open_database: asset path to .db file
- show_schema
- expand_schema
- open_file: asset path to .sql file
- highlight_section: section name (e.g., "query_1")
- run_query: query_ref
- show_result: (no params needed, just emphasizes current results)
- highlight_row: row_index, color ("red" for wrong, "green" for right)
- annotate_cell: row_index, col_index, text
- clear_highlights
- set_layout: mode ("single" or "compare")
- compare_results: targets [query refs]
- zoom_results
- fade_out
- pause: duration in seconds

Rules:
- Total narration should be ~400-500 words (90 seconds at ~300 wpm)
- Use contractions and natural speech patterns
- Build tension: "Same question. Different answer. What's going on?"
- The narrator is a mentor, not a lecturer
- Include strategic pauses (pause events) for visual processing
- The compare_results event should come AFTER set_layout to compare mode
- End with a clear takeaway the student can apply immediately

Output JSON array of events.
"""
