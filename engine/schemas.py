"""
WSDA Video Engine — Schemas v3

Core principle: the production card describes INTENT.
The system handles EXECUTION.

Three-phase event model:
  APPROACH  → cursor moves to target (system-generated, before narration)
  FOCUS     → element highlighted (fires as narration begins)  
  ACTION    → query/transition executes (fires after narration ends + offset)

Transition types drive silence gap duration:
  new_concept   → 900ms silence (learner needs reset time)
  continuation  → 450ms silence (same concept flowing forward)
  emphasis      → 650ms silence (pause for weight)
"""

from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ── Event types ────────────────────────────────────────────────

EventType = Literal[
    # Database / file
    "open_database",
    "open_file",
    "open_view",
    "show_schema",
    # SQL
    "highlight_section",
    "run_query",
    "show_result",
    "highlight_result",
    "clear_result",
    # Layout
    "set_layout",
    "compare_results",
    "zoom_result",
    "focus_callout",
    # Navigation
    "activate_table",
    "switch_window",
    # Chat demo events
    "open_chat",
    "new_conversation",
    "type_message",
    "send_message",
    "show_message",
    "show_response",
    "stream_response",
    "highlight_region",
    "clear_highlight",
    "set_input",
    # Control
    "pause",
    "fade_out",
]

TransitionType = Literal["new_concept", "continuation", "emphasis"]

# Silence gap per transition type (ms)
TRANSITION_SILENCE: dict[str, int] = {
    "new_concept":  900,
    "continuation": 450,
    "emphasis":     650,
}

# Default transition per event type
EVENT_DEFAULT_TRANSITION: dict[str, str] = {
    "open_database":     "new_concept",
    "open_file":         "new_concept",
    "show_schema":       "new_concept",
    "highlight_section": "new_concept",
    "run_query":         "continuation",
    "show_result":       "continuation",
    "clear_result":      "continuation",
    "compare_results":   "emphasis",
    "zoom_result":       "emphasis",
    "focus_callout":     "emphasis",
    "set_layout":        "new_concept",
    "activate_table":    "continuation",
    "pause":             "continuation",
    "fade_out":          "emphasis",
}

# How long after narration ends before visual action fires (seconds)
# Built-in instructional rhythm — not guesswork
EVENT_ACTION_OFFSET: dict[str, float] = {
    "open_database":     0.3,
    "open_file":         0.3,
    "show_schema":       0.2,
    "highlight_section": 0.1,   # near-simultaneous — cursor already positioned
    "run_query":         0.4,   # hear "run it", slight beat, see it execute
    "show_result":       0.8,   # let results render, eye settle on numbers
    "clear_result":      0.2,
    "compare_results":   0.6,   # transition has visual weight
    "zoom_result":       0.5,
    "focus_callout":     0.4,
    "set_layout":        0.3,
    "activate_table":    0.2,
    "pause":             0.0,
    "fade_out":          1.2,   # hold before closing
}

# How long before narration starts the cursor should begin moving (seconds)
EVENT_APPROACH_LEAD: dict[str, float] = {
    "highlight_section": 0.6,   # cursor arrives before highlight fires
    "run_query":         0.4,
    "show_result":       0.3,
    "compare_results":   0.8,
    "zoom_result":       0.4,
    "activate_table":    0.5,
    "open_database":     0.3,
    "open_file":         0.3,
    "show_schema":       0.3,
}


# ── Production Card v3 ─────────────────────────────────────────

class ProductionEvent(BaseModel):
    """
    One instructional concept in a lesson.
    
    The system generates three execution phases automatically:
    approach → focus → action
    
    The author only specifies intent.
    """
    id: str
    type: EventType
    target: Optional[str] = None
    asset: Optional[str] = None
    narration: Optional[str] = None

    # What this event operates on
    section: Optional[str] = None       # for highlight_section
    query_ref: Optional[str] = None     # for run_query
    intent: Optional[str] = None        # semantic intent label
    targets: Optional[list[str]] = None # for compare_results
    duration: Optional[float] = None    # for pause/zoom
    # Chat demo fields
    text: Optional[str] = None          # type_message / stream_response
    wpm: Optional[int] = None           # typing/streaming speed
    region: Optional[str] = None        # highlight_region
    callout: Optional[str] = None       # highlight callout text
    title: Optional[str] = None         # new_conversation title
    user_name: Optional[str] = None     # open_chat user name
    initials: Optional[str] = None      # open_chat initials
    view: Optional[str] = None          # open_view name

    # Screen state management
    transition: TransitionType = "new_concept"
    clears: list[str] = Field(default_factory=list)  # screen elements to clear first

    # Optional offset override (added to system default)
    offset_override: float = 0.0


class ProductionCard(BaseModel):
    schema_version: str = "3.0"
    lesson_id: str
    title: str
    course: Optional[str] = None
    assets: dict[str, str] = Field(default_factory=dict)
    events: list[ProductionEvent]

    @model_validator(mode="after")
    def validate_events(self) -> "ProductionCard":
        ids = [e.id for e in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate event IDs in production card")
        return self

    def narration_segments(self) -> list[dict]:
        return [
            {
                "event_id":   e.id,
                "event_type": e.type,
                "text":       e.narration.strip(),
                "transition": e.transition,
                "clears":     e.clears,
                "offset_override": e.offset_override,
            }
            for e in self.events
            if e.narration and e.narration.strip()
        ]


# ── Timeline (compiled, locked) ────────────────────────────────

class Phase(BaseModel):
    """One of three sub-phases within an event execution."""
    name: Literal["approach", "focus", "action"]
    time_offset_ms: int
    action: str                          # what to do
    params: dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    id: str
    time_offset_ms: int                  # when focus phase fires
    type: EventType
    target: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    narration: Optional[str] = None
    transition: str = "new_concept"
    clears: list[str] = Field(default_factory=list)
    phases: list[Phase] = Field(default_factory=list)

    @property
    def time_offset_seconds(self) -> float:
        return self.time_offset_ms / 1000


class LessonTimeline(BaseModel):
    schema_version: str = "3.0"
    lesson_id: str
    title: str
    course: Optional[str] = None
    compiled_from: str
    total_duration_ms: int
    narration_locked: bool = False
    adapter_type: str = "sql_viewer"  # sql_viewer | chat_demo
    events: list[TimelineEvent]


# ── Audit ──────────────────────────────────────────────────────

class EventResult(BaseModel):
    event_id: str
    type: str
    phase: str = "action"
    started_at_ms: int
    completed_at_ms: int
    success: bool
    error: Optional[str] = None


class AuditLog(BaseModel):
    schema_version: str = "3.0"
    lesson_id: str
    run_started: str
    run_completed: Optional[str] = None
    rehearsal_mode: bool = False
    events: list[EventResult] = Field(default_factory=list)
    mp4_path: Optional[str] = None
    total_events: int = 0
    successful_events: int = 0
    failed_events: int = 0
