# WSDA Video Engine

Automated instructional video production system for Walter Shields Data Academy.

## Architecture Decision Record

### Why not DB Browser?
DB Browser is a Qt desktop app. Playwright can't touch it. Automation requires
PyAutoGUI + OpenCV image-matching — brittle, resolution-dependent, breaks on
any UI update. We replace it with a custom web SQL viewer that Playwright controls
with full reliability.

### Why a custom SQL viewer instead of Datasette?
Datasette is excellent but opinionated about its UI. We need pixel-level control
over highlighting, focus zones, and visual emphasis. A thin Flask app gives us that
while staying simple.

### Why no OBS for MVP?
OBS requires a running desktop session and WebSocket setup. FFmpeg + virtual display
(Xvfb) can record a browser window headlessly with zero external dependencies.
OBS is Phase 2 when you need multi-source mixing.

### Why Playwright over Selenium?
Async, reliable waiting, built-in screenshot/video capture, no driver management.

## Folder Structure

```
wsda-video-engine/
├── courses/
│   └── novabridge/
│       └── video_1_1/
│           ├── production_card.yml     # Authoritative source
│           ├── lesson_timeline.json    # Compiled output (never edit directly)
│           └── assets/
│               ├── novabridge.db
│               └── ambiguity_demo_queries.sql
├── adapters/
│   ├── sql_viewer_adapter.py          # Controls the web SQL viewer
│   └── editor_adapter.py              # Controls code/text display
├── engine/
│   ├── compiler.py                    # Production card → timeline JSON
│   ├── timeline_runner.py             # Executes timeline events
│   └── attention_engine.py            # Renders visual emphasis
├── web/
│   ├── app.py                         # Flask SQL viewer app
│   ├── templates/
│   └── static/
├── recording/
│   └── recorder.py                    # FFmpeg screen capture
├── config/
│   └── settings.yml
├── output/                            # Final MP4s + audit logs land here
├── run.py                             # Main entry point
└── rehearse.py                        # Dry-run without recording
```

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers
playwright install chromium

# 3. Rehearse (no recording, 2x speed, verbose)
python rehearse.py courses/novabridge/video_1_1/production_card.yml

# 4. Record
python run.py courses/novabridge/video_1_1/production_card.yml
```

## Phases

| Phase | Scope |
|-------|-------|
| 1 (MVP) | Production card → executed demonstration → MP4 |
| 2 | + Automated attention management (zoom, highlight, focus) |
| 3 | + Narration audio synchronization via WhisperX timestamps |
| 4 | + Full course package automation |
