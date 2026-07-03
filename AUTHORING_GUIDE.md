# WSDA Video Engine — Course Authoring Guide

## What this system does

You write a production card (a YAML file). The engine records a lesson video,
adds your cloned voice narration, checks sync and timing automatically, and
delivers a finished MP4. One command.

```bash
python3 produce.py courses/YOUR_COURSE/YOUR_VIDEO/production_card.yml
```

---

## Before you write a production card

### 1. Prepare your assets

You need three files in your lesson's `assets/` folder:

| File | What it is | Example |
|------|-----------|---------|
| `your_lesson.db` | SQLite database the lesson queries | `novabridge.db` |
| `your_queries.sql` | SQL queries shown on screen | `mapping_queries.sql` |

### 2. Name your SQL sections correctly

The SQL file must use this exact format for section headers:

```sql
-- [query_1]
SELECT ...;

-- [query_2]
SELECT ...;
```

The name inside `[ ]` is what you reference in the production card.
No spaces. Lowercase. Underscores only.

### 3. Run the number pre-check before writing narration

```bash
python3 narration/check_numbers.py courses/YOUR_COURSE/YOUR_VIDEO/production_card.yml
```

This shows you exactly what numbers will appear on screen (rounded to 2 decimal
places by the viewer). Write your narration to match these displayed values —
not the raw database values.

---

## The production card format

```yaml
schema_version: "3.0"
lesson_id: "video_X_Y"          # must be unique, no spaces
title: "Your Lesson Title"
course: "Your Course Name"

assets:
  database: "assets/your_lesson.db"
  sql_file:  "assets/your_queries.sql"

events:
  - id: "e01"
    type: open_database
    ...
```

---

## Event types reference

### Opening events (load content)

```yaml
- id: "e01"
  type: "open_database"
  target: "sql_viewer"
  asset: "assets/your_lesson.db"
  transition: "new_concept"
  narration: >
    Your opening narration here.
```

```yaml
- id: "e02"
  type: "open_file"
  target: "sql_viewer"
  asset: "assets/your_queries.sql"
  transition: "new_concept"
```

```yaml
- id: "e03"
  type: "show_schema"
  target: "sql_viewer"
  transition: "new_concept"
  narration: >
    Describe the schema to the learner.
```

### SQL events (the core teaching sequence)

```yaml
# Step 1: Highlight the query — SQL pane auto-expands to full height
- id: "e04"
  type: "highlight_section"
  target: "sql_viewer"
  section: "query_1"             # must match -- [query_1] in SQL file
  transition: "new_concept"
  clears: []                     # use ["result"] to clear previous result
  narration: >
    Describe what this query does BEFORE running it.
    Set up what the learner is about to see.

- id: "e04_pause"
  type: "pause"
  duration: 12.0                 # must be >= narration speech time + 2s buffer
  transition: "continuation"

# Step 2: Run the query
- id: "e05"
  type: "run_query"
  target: "sql_viewer"
  query_ref: "query_1"           # must match section name

- id: "e05_pause"
  type: "pause"
  duration: 3.0
  transition: "continuation"

# Step 3: Show result and explain — results pane auto-restores
- id: "e06"
  type: "show_result"
  target: "sql_viewer"
  transition: "continuation"
  narration: >
    Read the result out loud. Explain what it means.
    Explain why it matters. Connect it to the lesson.
    Over-explain rather than under-explain.

- id: "e06_pause"
  type: "pause"
  duration: 20.0                 # must be >= narration speech time + 2s buffer
  transition: "continuation"
```

### Layout events (compare multiple results)

```yaml
- id: "e12_layout"
  type: "set_layout"
  target: "sql_viewer"
  transition: "new_concept"
  clears: ["result"]             # clear current result before switching layout
  narration: "Now let me show you all three results at once."

- id: "e12_pause"
  type: "pause"
  duration: 6.0
  transition: "continuation"

- id: "e12"
  type: "compare_results"
  target: "sql_viewer"
  targets: ["query_1", "query_2", "query_3"]
  transition: "emphasis"
  narration: >
    Describe what the learner sees across all panels.
```

### Closing events

```yaml
- id: "e_final"
  type: "zoom_result"
  target: "sql_viewer"
  transition: "emphasis"
  narration: >
    Summary and bridge to next lesson.

- id: "e_final_pause"
  type: "pause"
  duration: 14.0
  transition: "continuation"

- id: "e_end"
  type: "fade_out"
  target: "all"
  transition: "emphasis"
```

---

## Pause sizing rule

Every narration needs a following pause sized to fit:

```
pause duration = (word count / 145) × 60 + 8 seconds
```

Example: 60-word narration = (60/145)×60 + 8 = **32.8 seconds minimum**

The QA system will auto-fix pauses that are too short, but sizing them
correctly the first time avoids an extra record cycle.

Quick reference:
| Words | Minimum pause |
|-------|--------------|
| 20    | 16s |
| 40    | 24s |
| 60    | 33s |
| 80    | 41s |
| 100   | 49s |
| 120   | 58s |

---

## Narration rules (LOCKED)

1. **Narration lives on `highlight_section` and `show_result` events only**
   Never on `run_query`. Never on standalone `pause` events.

2. **Set up before, explain after**
   - On `highlight_section`: describe the query before it runs
   - On `show_result`: read the result, explain what it means, connect to lesson

3. **Match what's on screen exactly**
   The viewer rounds all numbers to 2 decimal places.
   If the database has `0.0487`, the screen shows `0.05`.
   Your narration must say "zero point zero five" — not "zero point zero four eight seven".
   Run `check_numbers.py` to see exact displayed values before writing narration.

4. **Over-explain rather than under-explain**
   Assume the learner has never seen this data before.
   Read numbers out loud. Explain what columns mean.
   Say why a result matters, not just what it is.

5. **No em dashes**
   Use commas instead. Em dashes break ElevenLabs rhythm.

6. **S-Q-L is three letters**
   Write "S-Q-L" not "SQL" so ElevenLabs pronounces it correctly.

7. **Contrast numbers are allowed**
   "Not one hundred and fifty-eight" is correct — it's instructional,
   not a number mismatch error.

---

## The full pipeline

```bash
# 1. Pre-check numbers (do this while still writing the card)
python3 narration/check_numbers.py courses/COURSE/VIDEO/production_card.yml

# 2. Produce (record + narrate + QA + trim in one command)
python3 produce.py courses/COURSE/VIDEO/production_card.yml
```

`produce.py` will:
- Run the number pre-check and abort if mismatches found
- Record the silent video
- Synthesize ElevenLabs narration
- Run QA — auto-fix timing and retry once if needed
- Trim blank opening and dead tail
- Report the final MP4 path

Set credentials once per session:
```bash
export ELEVENLABS_API_KEY=your_key
export ELEVENLABS_VOICE_ID=your_voice_id
```

---

## Folder structure for a new lesson

```
courses/
  your_course/
    video_1_1/
      assets/
        your_lesson.db
        your_queries.sql
      production_card.yml
```

Copy an existing lesson folder as a starting point:
```bash
cp -r courses/novabridge/video_1_1 courses/your_course/video_1_1
```

Then replace the assets and rewrite the production card.

---

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Narration on `run_query` event | Move to `highlight_section` or `show_result` |
| Numbers don't match screen | Run `check_numbers.py`, use displayed values |
| Audio cut off | Pause too short — use word count formula above |
| Next visual appears mid-narration | Pause too short — add 8s buffer |
| "SQL" mispronounced | Write "S-Q-L" in narration text |
| Em dash in narration | Replace with comma |
| Highlight box cut off at top | Engine handles this automatically via scroll |
| Results pane blocks long SQL | Engine handles this automatically via expand |
