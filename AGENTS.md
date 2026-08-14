# WSDA Video Engine — Agent Guide

This file is written for AI coding agents who need to understand and work on this project. It reflects the actual files and behavior in the repository, not the aspirational architecture described in older documentation.

## Project Overview

The WSDA (Walter Shields Data Academy) Video Engine is an automated instructional-video production system for data-analytics courses. It turns a YAML **production card** (lesson script + assets) into a finished MP4 lesson with synchronized narration.

The current working pipeline is:

1. Author a production card and place SQLite + SQL assets under `courses/<course>/<lesson>/assets/`.
2. Run `python3 produce.py courses/<course>/<lesson>/production_card.yml`.
3. `renderer.py` drives a headless Chromium browser through Playwright using a self-contained HTML viewer (`viewer.html`).
4. A silent MP4 is recorded; `narration/audit_narrator.py` synthesizes narration clips and mixes them into the video.
5. `trim.py` removes blank opening/dead tail, and a final MP4 is produced in `output/`.

## Technology Stack

- **Language:** Python 3.11+ (recommended; setup script checks for this).
- **Browser automation:** Playwright for Python (`playwright>=1.40.0`) with Chromium.
- **Video/audio processing:** FFmpeg (installed via Homebrew on macOS by `setup.sh`).
- **Video capture:** Playwright's built-in screen recording to WebM, then FFmpeg transcode to H.264/AAC MP4.
- **Database:** SQLite for lesson demo databases.
- **Configuration/data:** YAML production cards, JSON audit logs.
- **Validation/models:** Pydantic v2.
- **CLI/output:** Click and Rich.
- **TTS (narration):** ElevenLabs API (preferred) or macOS `say` fallback.
- **AI/LLM APIs:** OpenAI (`generator/`), Anthropic Claude (`narrator_v2.py`, `storyboard_v2.py`, `vision_sync.py`, `review/video_reviewer.py`, `draft.py`, `research.py`).
- **Web viewer:** A single static `viewer.html` (uses sql.js WASM, Prism syntax highlighting, vanilla JS/CSS); no running Flask server is required for the current renderer path.

## Repository Layout

```
.
├── adapters/
│   └── sql_viewer_adapter.py        # Legacy bridge to a Flask SQL viewer (unused by renderer.py)
├── config/
│   └── settings.yml                 # Global settings (browser, recording, rehearsal, attention)
├── courses/
│   ├── TEMPLATE/                    # Production-card template
│   ├── sql-fundamentals/            # Example generated course
│   └── {courses/                    # Legacy/copied course directory (literal "{" prefix)
├── engine/
│   └── lesson_director.py           # Standalone director for sql_viewer.html with a hard-coded script
├── generator/
│   ├── __init__.py
│   ├── db_builder.py                # Build SQLite DB from AI-generated CREATE/INSERT statements
│   ├── lesson_generator.py          # OpenAI-based end-to-end lesson generator
│   └── prompts.py                   # Prompts for concept, schema, and narration generation
├── narration/
│   ├── align.py
│   ├── audit_narrator.py            # Post-render narration mixer (used by produce.py)
│   ├── check_numbers.py             # Pre-production narration-vs-database number check
│   ├── generate.py
│   ├── mix.py
│   ├── qa.py                        # Timing QA / auto-fix for pause durations
│   └── vision_sync.py               # Claude vision-based narration from silent video frames
├── review/
│   └── video_reviewer.py            # Claude vision-based post-render visual quality gate
├── viewer/
│   └── sql_viewer.html              # Self-contained SQL demo viewer (sql.js + Prism)
├── viewer.html                      # Root copy of the viewer used by rehearse.py / renderer.py
├── browser_controller.py            # v3 real-time browser controller (legacy, used by engine_v3.py)
├── composer.py                      # v3 PIL-based overlay composer (legacy)
├── config.py                        # v3 Pydantic scene models + hard-coded SCENES_CONFIG (legacy)
├── create_db.py                     # Creates the NovaBridge demo database
├── draft.py                         # Claude-based production-card generator from research brief
├── draft_bugfix.py                  # Scratch/bugfix variant of draft.py
├── engine_v3.py                     # v3 real-time engine with inline TTS (legacy)
├── generate.py                      # CLI entry point for generator.lesson_generator
├── narrator_v2.py                   # Claude-vision narration generator from video frames
├── produce.py                       # One-command full production pipeline
├── renderer.py                      # CURRENT v4 state-driven renderer
├── rehearse.py                      # Render a production card headlessly without narration
├── research.py                      # Topic/content brief generator
├── run.py                           # v10 entry point; imports non-existent engine.compiler / timeline_runner
├── schema_fix.py                    # SQLite schema HTML injection helper
├── setup.sh                         # macOS dependency setup script
├── storyboard.py / storyboard_v2.py # Visual storyboard generators
├── studio.py                        # GUI studio (legacy/experimental)
├── test_elevenlabs.py               # Small ElevenLabs connectivity test
├── test_env.py                      # Environment readiness checker
├── tts_engine.py                    # ElevenLabs TTS wrapper
├── trim.py                          # Trim blank opening/dead tail from narrated video
├── topic_scout.py                   # Topic research helper
└── verify.py                        # Pre-production validation for production cards
```

## Current Working Pipeline (what actually runs)

### Production card format

Production cards are YAML files following schema version `"3.0"`. See `courses/TEMPLATE/video_X_Y/production_card.yml` and `AUTHORING_GUIDE.md` for the canonical format.

Key fields:

```yaml
schema_version: "3.0"
lesson_id: "sql-fundamentals-02"
title: "..."
course: "..."

assets:
  database: "assets/sql-fundamentals.db"
  sql_file: "assets/ambiguity_demo_queries.sql"

events:
  - id: "e01"
    type: "open_database"
    target: "sql_viewer"
    asset: "assets/sql-fundamentals.db"
    narration: "..."
  - id: "e01_pause"
    type: "pause"
    duration: 5.0
```

Common event types used by `renderer.py`:

- `show_title_card`, `hide_title_card`
- `open_database`, `show_schema`, `expand_schema`, `collapse_schema`, `activate_table`
- `open_file`
- `highlight_section`
- `run_query`
- `show_result`
- `highlight_row`, `annotate_cell`, `clear_highlights`, `clear_annotations`
- `set_layout`, `compare_results`, `zoom_results`, `reset_zoom`
- `fade_out`
- `pause`

SQL sections in the asset file are delimited with `-- [query_1]`, `-- [query_2]`, etc.

### Entry points

- **Full production:**
  ```bash
  python3 produce.py courses/<course>/<lesson>/production_card.yml
  ```
  This runs number pre-check → record → narrate/QA → video review → trim → report.

- **Rehearse / render silent video only:**
  ```bash
  python3 rehearse.py courses/<course>/<lesson>/production_card.yml
  ```
  Outputs an MP4 under `output/<lesson>/`.

- **Number pre-check:**
  ```bash
  python3 narration/check_numbers.py courses/<course>/<lesson>/production_card.yml
  ```

- **Verification:**
  ```bash
  python3 verify.py courses/<course>/<lesson>/production_card.yml --fix
  ```

- **Generate a new lesson from topic:**
  ```bash
  python3 generate.py --topic "SQL JOINs" --course sql-fundamentals --lesson 3
  ```
  (requires `OPENAI_API_KEY`)

- **Environment check:**
  ```bash
  python3 test_env.py
  ```

## Build and Test Commands

There is no formal test suite. Validation is done through environment checks and helper scripts:

```bash
# One-time macOS setup (Homebrew, Python, FFmpeg, Playwright Chromium)
bash setup.sh

# Check environment and required files
python3 test_env.py

# Test ElevenLabs connectivity
python3 test_elevenlabs.py

# Build the NovaBridge demo database
python3 create_db.py

# Render a silent preview
python3 rehearse.py courses/sql-fundamentals/video_2_02/production_card.yml

# Full production with narration
python3 produce.py courses/sql-fundamentals/video_2_02/production_card.yml
```

### Setup requirements

Install Python dependencies:

```bash
pip3 install -r requirements.txt
playwright install chromium
```

On macOS, grant **Screen Recording** permission to your terminal/IDE for Playwright capture.

## Code Style Guidelines

- Python files use **UTF-8**, top-of-file docstrings, and `#!/usr/bin/env python3` for CLI scripts.
- Use `pathlib.Path` for filesystem paths.
- CLI scripts prefer `click`; status output uses `rich.console.Console` and `rich.panel.Panel`.
- Async code is used for Playwright browser control (`asyncio.run(main())`).
- Constants and format specs are module-level uppercase dicts (e.g., `FORMAT_SPECS`, `NARRATION_SYSTEM`).
- Generated YAML uses `sort_keys=False` to preserve event order.
- Indentation: 4 spaces.

## Testing Instructions

No unit tests exist. Verify changes by:

1. Running `python3 test_env.py` to confirm Python/Playwright/FFmpeg/browser health.
2. Running `python3 rehearse.py courses/sql-fundamentals/video_2_02/production_card.yml` to confirm the renderer still produces a video.
3. Running `python3 narration/check_numbers.py <card>` before changing narration.
4. Running `python3 verify.py <card> --fix` for pre-production validation.
5. Running `python3 produce.py <card>` end-to-end when changing the pipeline.

## Security Considerations

- API keys are read from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`) or `.env` files in some legacy modules.
- `test_elevenlabs.py` contains a hard-coded API key fragment. Treat it as sensitive.
- The project runs subprocesses (`ffmpeg`, `say`, `flask`, `python`) with captured output; avoid passing user input directly into these commands.
- No authentication, network sandbox, or input sanitization is implemented; this is a local content-creation tool.
- `.gitignore` ignores `output/`, `__pycache__/`, and `.DS_Store` only.

## Important Architecture Notes

- **Multiple code generations coexist.** The repo contains v3 (`engine_v3.py`, `config.py`, `browser_controller.py`, `composer.py`) and v4 (`renderer.py`) renderers. The working path today is `produce.py` → `run.py`/`rehearse.py` → `renderer.py`.
- **Several files reference missing modules.** `run.py` imports `engine.compiler`, `engine.timeline_runner`, and `engine.schemas`, none of which exist. `test_env.py` checks for `web/app.py`, `web/templates/viewer.html`, `engine/compiler.py`, and `engine/timeline_runner.py`, which are also absent. Do not assume those modules exist.
- **No Flask server is required for the current renderer.** `renderer.py` loads `viewer.html` directly via `page.set_content()` and drives it through JavaScript state updates. The Flask/web-app architecture described in `README.md` is aspirational/legacy.
- **Narration is added post-render.** The preferred path is `renderer.py` records a silent video, `narration/audit_narrator.py` measures pause windows from the audit log, synthesizes audio, and mixes it in.
- **Generated lessons go under `courses/<course>/video_<N>_<NN>/`** (e.g., `courses/sql-fundamentals/video_2_02/`). The literal `{courses/` directory is a legacy copy and should not be treated as the canonical location.
- **Pause sizing rule:** `duration = (word_count / 145) * 60 + buffer`. `verify.py` and `narration/qa.py` enforce/auto-fix this. Two buffer sizes are in use as of 2026-08-14: `~8s` for longer, paragraph-length narration (the original rule), and a shorter `~1.5s` for the one-sentence "here's what I'm doing" narration described below, sized so a short line doesn't get the same padding built for a long one and leave dead air after it finishes. Introduced in `automation/metabase_driver.py`'s lesson scripts; apply the same distinction if you add short narration to the main SQL pipeline's production cards.

## Common Pitfalls

- **Narration convention (updated 2026-08-14):** two tiers, not one. Short, single-sentence "here's what I'm doing" lines belong on most action events (in the Metabase automation path: `click_new_question`, `select_table`, `add_filter`, `save_question`, `add_to_dashboard`; the equivalent in the main SQL pipeline would be `open_database`/`run_query`-adjacent action events). Longer "why this matters" narration stays on `highlight_section` and `show_result`, as before. The goal is no event sitting silent for many seconds with nothing on screen changing and nothing being said, that read as dead, scripted-feeling pacing in the first Metabase PoC cut. Note this was always just an authoring convention, not something `narration/audit_narrator.py` enforces in code, it builds its narration map from any event with a non-empty `narration` field regardless of `type`, so no code change was needed there to support narrating more event types, only this doc and the lesson scripts themselves needed to change.
- Numbers in narration must match the **2-decimal display values** from the viewer; run `check_numbers.py` to see them.
- Spell "S-Q-L" as three letters in narration text for TTS clarity.
- Avoid em dashes in narration — they break ElevenLabs pacing.
- Do not commit API keys or `output/` content.

## File References

- Authoring rules: `AUTHORING_GUIDE.md`
- Production card template: `courses/TEMPLATE/video_X_Y/production_card.yml`
- Current renderer: `renderer.py`
- Current pipeline: `produce.py`
- Environment check: `test_env.py`
- Dependencies: `requirements.txt`
- Setup script: `setup.sh`
