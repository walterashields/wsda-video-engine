# WSDA Video Engine — New Chat Handoff Document
# Generated: 2026-07-07
# Repo: github.com/walterashields/wsda-video-engine

## What This System Is
An automated content production engine that converts topic inputs into finished
lesson videos. Input: topic, format, audience. Output: MP4 ready for Final Cut Pro.

## Current Pipeline (in order)
```
python3 studio.py              # Web UI at http://127.0.0.1:7000
  → research.py "topic"        # Claude researches niche, produces brief.json
  → draft.py brief.json        # Claude generates production_card.yml + SQL + DB
  → verify.py card.yml --fix   # Validates tables, duration, sections — auto-fixes
  → produce.py card.yml        # Records video + ElevenLabs narration + QA + trim
```

## Key Files
- `studio.py` — web UI, runs full pipeline
- `research.py` — niche research, outputs research/SLUG/brief.json
- `draft.py` — generates production cards from brief
- `verify.py` — pre-production validation (tables, duration, SQL sections)
- `produce.py` — single-command pipeline (record + narrate + QA + trim)
- `run.py` — records silent video
- `narration/audit_narrator.py` — ElevenLabs synthesis + audio mix
- `narration/qa.py` — timing QA, auto-fixes pauses
- `narration/check_numbers.py` — number accuracy pre-check
- `trim.py` — cuts blank opening and dead tail
- `AUTHORING_GUIDE.md` — complete production standard documentation
- `courses/TEMPLATE/` — production card template

## Adapters
- `adapters/sql_viewer_adapter.py` — SQL viewer (primary adapter, proven)
- `adapters/chat_demo_adapter.py` — ChatGPT demo interface

## ElevenLabs
- Voice ID: E5wNdHqDxPAZRB8qRbQh (Walter's clone)
- Model: eleven_multilingual_v2
- Settings: stability=0.5, similarity_boost=0.75, style=0.0

## Completed Lessons (NovaBridge Analytics course)
- video_1_1: Three Tables, One Question (SQL ambiguity)
- video_1_2: The Mapping Problem
- video_1_3: The Number That Made It to the Deck
- video_1_4: What AI-Ready Data Design Looks Like (canonical views)
- ai_beginners_1_3: Hands On with ChatGPT (chat demo adapter)

## Locked Production Standard
1. Narration on highlight_section and show_result ONLY (SQL)
   Narration on highlight_region and show_result ONLY (chat demo)
2. Every narration event followed immediately by pause
3. Pause duration = (words/145*60) + 8 seconds
4. Numbers match displayed values (viewer rounds to 2 decimal places)
5. No em dashes. S-Q-L not SQL. Contractions always.
6. Show first, then explain. Never talk while content appears.

## Known Issues To Fix (Priority Order)
1. NARRATION-VISUAL DISCONNECT — draft writes narration assuming things
   are on screen that may not be. Fix: draft must query the actual DB
   and build narration only from verified query results.

2. LESSON QUALITY — narration is competent but flat. Needs wit, stakes,
   personality. Fix: prompt engineering — add voice examples, require
   hooks, require specific outcomes in opening.

3. TALKING HEAD SUPPORT — need scene metadata output so FCP knows
   where to insert talking head footage. Fix: add talking_head field
   to production card events, output scene package manifest.

4. SHORT-VIDEO DURATION — draft still generates too-long lessons even
   with duration caps. Fix: verify.py duration check + draft prompt
   must count words and calculate pause durations explicitly.

5. MISSING TABLES — narration mentions tables that don't exist in DB.
   verify.py catches this but draft.py should not generate narration
   about tables it didn't create.

6. BLANK OPENING FRAME — video starts with "No database loaded" for
   1-2 seconds. Fix: trim.py needs to detect and cut based on audio,
   not a fixed time.

7. SLIDES ADAPTER — not built. Conceptual lessons use chat demo as
   workaround. Need proper slides/presentation adapter for Lesson 1,
   2, 5 of AI course.

## The Fundamental Architecture Problem
Draft writes narration BEFORE knowing what will be on screen.
The correct order is:
  1. Create database with real data
  2. Run queries and capture actual results
  3. Write narration describing those specific results
  4. Write production card events that show exactly what narration describes

This is not implemented yet. It's the most important remaining build.

## Studio UI Inputs (http://127.0.0.1:7000)
- Topic/title text field
- Format: full course / short video / tutorial / single lesson
- Audience level: beginner / intermediate / advanced
- Lesson length: short 3-5min / medium 7-10min / long 12-15min
- Tools featured: ChatGPT / Excel / SQL / Python / Power BI / none
- Target audience (text)
- Hands-on style: heavy / moderate / light
- Notes (text)

## Format Duration Caps (verify.py)
- short-video: 5 minutes max
- tutorial: 12 minutes max
- lesson: 10 minutes max
- course: 15 minutes per lesson max

## Commands Reference
```bash
# Full pipeline via UI
python3 studio.py

# Manual pipeline
python3 research.py "topic" --format course
python3 draft.py research/SLUG/brief.json --lesson 1
python3 verify.py courses/SLUG/video_1_1/production_card.yml --fix --format short-video
python3 produce.py courses/SLUG/video_1_1/production_card.yml

# Git
cd ~/Desktop/wsda-video-engine
git add -A && git commit -m "message" && git push
```

## Opening Message For New Chat
Paste this entire document plus:
"Continuing WSDA Video Engine development.
Repo: github.com/walterashields/wsda-video-engine
Read HANDOFF.md for full context.
Priority: fix the narration-visual disconnect (item 1 in Known Issues).
The draft system must query the actual database and write narration
from verified results, not assumed content."
