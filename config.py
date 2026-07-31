"""
WSDA v3 -- Scene Configuration
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Tuple


class UIAction(BaseModel):
    action: Literal["load_db", "open_schema", "type_query", "run_query", "clear_query", "wait"]
    target: Optional[str] = None
    value: Optional[str] = None
    delay_after: float = 0.5
    validation_selector: Optional[str] = None
    fatal_validation: bool = False


class OverlayElement(BaseModel):
    type: Literal["text", "badge", "highlight", "comparison"]
    content: str
    position: Tuple[float, float]
    style: dict = Field(default_factory=dict)
    animation: Literal["fade_in", "slide_up", "typewriter", "none"] = "fade_in"
    start_time: float
    duration: float

    @validator("position")
    def check_position(cls, v):
        if not (0.0 <= v[0] <= 1.0 and 0.0 <= v[1] <= 1.0):
            raise ValueError("Position values must be between 0.0 and 1.0")
        return v


class Scene(BaseModel):
    id: str
    type: Literal["ui_action", "overlay", "hold"]
    duration: float
    description: str
    ui_actions: List[UIAction] = Field(default_factory=list)
    overlays: List[OverlayElement] = Field(default_factory=list)
    transition_in: Literal["fade", "cut", "slide_left", "slide_up"] = "cut"
    transition_out: Literal["fade", "cut", "slide_right", "slide_down"] = "cut"
    bg_fade_opacity: Optional[float] = None

    @validator("duration")
    def check_duration(cls, v):
        if v <= 0:
            raise ValueError("Scene duration must be > 0")
        return v


class VideoConfig(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: int = 30
    output_path: str = "final_output.mp4"
    temp_dir: str = "./temp_frames"
    ide_url: str = "http://127.0.0.1:5000"
    db_asset_path: Optional[str] = None
    scenes: List[Scene]

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)


SCENES_CONFIG = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "output_path": "final_output.mp4",
    "temp_dir": "./temp_frames",
    "ide_url": "http://127.0.0.1:5000",
    "db_asset_path": None,
    "scenes": [
        {
            "id": "intro",
            "type": "ui_action",
            "duration": 1.5,
            "description": "Clean IDE, no DB loaded",
            "ui_actions": [
                {"action": "clear_query", "delay_after": 0.5},
                {"action": "wait", "delay_after": 0.5}
            ],
            "transition_in": "fade",
            "transition_out": "cut"
        },
        {
            "id": "title_card",
            "type": "overlay",
            "duration": 4.0,
            "description": "Full-screen title card",
            "bg_fade_opacity": 1.0,
            "overlays": [
                {
                    "type": "text",
                    "content": "Same Question. Three Tables. Three Answers.",
                    "position": [0.5, 0.38],
                    "style": {"font_size": 68, "color": "#FFFFFF", "bg_color": "#0B0C10", "padding": 60},
                    "animation": "fade_in",
                    "start_time": 0.0,
                    "duration": 4.0
                },
                {
                    "type": "text",
                    "content": "Why JOINs and Aggregates produce different revenue numbers",
                    "position": [0.5, 0.52],
                    "style": {"font_size": 28, "color": "#AAAAAA", "bg_color": "#0B0C10", "padding": 30},
                    "animation": "fade_in",
                    "start_time": 0.4,
                    "duration": 3.6
                },
                {
                    "type": "badge",
                    "content": "Pick the wrong table and your report is off by thousands.",
                    "position": [0.5, 0.65],
                    "style": {"font_size": 22, "color": "#FF6B6B", "bg_color": "#2D1B1B"},
                    "animation": "slide_up",
                    "start_time": 1.0,
                    "duration": 3.0
                }
            ],
            "transition_in": "fade",
            "transition_out": "fade"
        },
        {
            "id": "db_load",
            "type": "ui_action",
            "duration": 2.5,
            "description": "Load novabridge.db",
            "ui_actions": [
                {
                    "action": "load_db",
                    "value": "novabridge.db",
                    "delay_after": 2.0,
                    "validation_selector": "text=novabridge.db",
                    "fatal_validation": False
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "schema_reveal",
            "type": "ui_action",
            "duration": 4.0,
            "description": "Open schema panel",
            "ui_actions": [
                {
                    "action": "open_schema",
                    "delay_after": 3.0,
                    "validation_selector": "text=orders",
                    "fatal_validation": False
                }
            ],
            "overlays": [
                {
                    "type": "badge",
                    "content": "orders table -> order_total",
                    "position": [0.18, 0.35],
                    "style": {"font_size": 18, "color": "#4ECDC4", "bg_color": "#1A2D2B"},
                    "animation": "fade_in",
                    "start_time": 2.0,
                    "duration": 2.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "query_1_type",
            "type": "ui_action",
            "duration": 8.0,
            "description": "Type query 1",
            "ui_actions": [
                {
                    "action": "type_query",
                    "value": "SELECT\n    region,\n    SUM(order_total) AS total_revenue\nFROM orders\nGROUP BY region\nORDER BY total_revenue DESC;",
                    "delay_after": 1.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "query_1_run",
            "type": "ui_action",
            "duration": 3.0,
            "description": "Execute query 1 and show results",
            "ui_actions": [
                {
                    "action": "run_query",
                    "delay_after": 0.5,
                    "fatal_validation": False
                }
            ],
            "overlays": [
                {
                    "type": "badge",
                    "content": "Method 1: Aggregate from orders table",
                    "position": [0.5, 0.12],
                    "style": {"font_size": 20, "color": "#4ECDC4", "bg_color": "#1A2D2B"},
                    "animation": "fade_in",
                    "start_time": 0.0,
                    "duration": 3.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "results_1_hold",
            "type": "hold",
            "duration": 4.0,
            "description": "Hold on results 1",
            "overlays": [
                {
                    "type": "highlight",
                    "content": "North leads with $148,230.50",
                    "position": [0.5, 0.72],
                    "style": {"font_size": 26, "color": "#FFFFFF", "bg_color": "#2D5A3D"},
                    "animation": "fade_in",
                    "start_time": 0.5,
                    "duration": 3.5
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "bridge",
            "type": "overlay",
            "duration": 3.0,
            "description": "Narrative bridge",
            "bg_fade_opacity": 0.9,
            "overlays": [
                {
                    "type": "text",
                    "content": "Now calculate from line items instead...",
                    "position": [0.5, 0.5],
                    "style": {"font_size": 40, "color": "#FFD93D", "bg_color": "#1A1A00", "padding": 50},
                    "animation": "fade_in",
                    "start_time": 0.0,
                    "duration": 3.0
                }
            ],
            "transition_in": "fade",
            "transition_out": "fade"
        },
        {
            "id": "query_2_type",
            "type": "ui_action",
            "duration": 10.0,
            "description": "Type query 2 with JOIN",
            "ui_actions": [
                {"action": "clear_query", "delay_after": 0.5},
                {
                    "action": "type_query",
                    "value": "SELECT\n    region,\n    SUM(unit_price * quantity) AS total_revenue\nFROM order_details od\nJOIN orders o ON od.order_id = o.order_id\nGROUP BY region\nORDER BY total_revenue DESC;",
                    "delay_after": 1.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "query_2_run",
            "type": "ui_action",
            "duration": 3.0,
            "description": "Execute query 2",
            "ui_actions": [
                {
                    "action": "run_query",
                    "delay_after": 0.5,
                    "fatal_validation": False
                }
            ],
            "overlays": [
                {
                    "type": "badge",
                    "content": "Method 2: JOIN order_details + orders",
                    "position": [0.5, 0.12],
                    "style": {"font_size": 20, "color": "#FFD93D", "bg_color": "#3D3A1A"},
                    "animation": "fade_in",
                    "start_time": 0.0,
                    "duration": 3.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "cut"
        },
        {
            "id": "results_2_comparison",
            "type": "hold",
            "duration": 6.0,
            "description": "Show comparison",
            "overlays": [
                {
                    "type": "comparison",
                    "content": "North: $152,907.80  (+$4,677.30)",
                    "position": [0.5, 0.72],
                    "style": {"font_size": 28, "color": "#FF6B6B", "bg_color": "#3D1A1A"},
                    "animation": "slide_up",
                    "start_time": 0.5,
                    "duration": 5.5
                },
                {
                    "type": "badge",
                    "content": "Same question. Different table. Wrong answer.",
                    "position": [0.5, 0.88],
                    "style": {"font_size": 22, "color": "#FFFFFF", "bg_color": "#FF4444"},
                    "animation": "fade_in",
                    "start_time": 2.0,
                    "duration": 4.0
                }
            ],
            "transition_in": "cut",
            "transition_out": "fade"
        }
    ]
}
