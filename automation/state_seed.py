#!/usr/bin/env python3
"""
Metabase state seeding: creates the Metabase state a lesson script's
`requires_state` declares (questions, dashboards) directly via Metabase's
REST API, before recording starts. No browser, no simulated UI clicks, no
dependency on a prior video having actually just run.

Architecture decision (2026-08-15, see MULTI_VIDEO_PROGRESSION_FINDINGS.md
for the full write-up): API-seeded state, not continuous shared
containers. A lesson script that depends on state from an earlier video
declares what it needs as data:

  requires_state:
    - type: "question"
      name: "High Value Orders"
      database: "Sample Database"
      table: "Orders"
      display: "table"
      filter:
        field: "Total"
        operator: "between"
        min: 50
        max: 1000
    - type: "dashboard"
      name: "WSDA Metabase Demo Dashboard"
      contains: ["High Value Orders"]

This module resolves that against the live Metabase instance and creates
whatever's missing. It is idempotent by name: if an active question or
dashboard with the declared name already exists, it's reused, not
duplicated -- this matters a lot on this project specifically, given how
much of this session's own testing produced duplicate "High Value
Orders" cards from repeated runs. A seeding step that isn't idempotent
would just move that same problem here.

Kept deliberately minimal, extended only as real lesson scripts have
needed more, not speculatively ahead of that: one filter operator
(`between`), one aggregation function (`sum`, added 2026-08-15 for
video_1_3's requires_state, which needs to seed a chart question --
`Monthly Revenue Trend` -- not just a filtered-table question, proving
this schema needed a real extension rather than holding unmodified
across a second use), one dashboard action (contains named cards, now
plural).

  - type: "question"
    name: "Monthly Revenue Trend"
    database: "Sample Database"
    table: "Orders"
    display: "bar"
    aggregation: {function: "sum", field: "Total"}
    breakout: {field: "Created At", granularity: "month"}
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(base_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/session",
        json={"username": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _headers(token: str) -> dict:
    return {"X-Metabase-Session": token}


def _resolve_table_and_fields(base_url, headers, database_name, table_name):
    """Database/table/field names in a lesson script are for human
    readability; Metabase's query API needs their internal integer ids.
    Resolved fresh each seed rather than hardcoded, since these ids are
    specific to one Metabase instance's data and would silently drift if
    baked into a lesson script as constants."""
    dbs = requests.get(f"{base_url}/api/database", headers=headers, timeout=15).json()
    db = next((d for d in dbs["data"] if d["name"] == database_name), None)
    if db is None:
        raise ValueError(f"database {database_name!r} not found")

    meta = requests.get(
        f"{base_url}/api/database/{db['id']}/metadata", headers=headers, timeout=15
    ).json()
    table = next(
        (t for t in meta["tables"] if t["name"].lower() == table_name.lower()), None
    )
    if table is None:
        raise ValueError(f"table {table_name!r} not found in database {database_name!r}")

    fields = {_normalize_field_name(f["name"]): f["id"] for f in table["fields"]}
    return db["id"], table["id"], fields


def _normalize_field_name(name: str) -> str:
    """Confirmed live (2026-08-15, video_1_3 work): Metabase's real
    column names use underscores (CREATED_AT), but a lesson script writes
    the human-readable version (Created At), matching what's shown in the
    UI. A naive `.lower()` lookup worked for one-word fields like Total
    by coincidence and broke immediately on the first two-word field,
    raising a KeyError rather than silently producing a wrong result --
    still worth normalizing properly rather than relying on continuing to
    get lucky with single-word field names."""
    return name.lower().replace("_", " ")


def _build_filter_mbql(spec, fields):
    """Only `between` is implemented, since it's the only operator any
    current lesson script's requires_state needs (see module docstring).
    Extend this dispatch, not the caller, when a lesson needs another
    operator."""
    operator = spec["operator"]
    field_id = fields[_normalize_field_name(spec["field"])]
    if operator == "between":
        return ["between", ["field", field_id, None], spec["min"], spec["max"]]
    raise ValueError(f"unsupported filter operator {operator!r}")


def _build_aggregation_mbql(spec, fields):
    """Only `sum` is implemented, since it's the only aggregation any
    current lesson script needs (see module docstring's minimalism
    note). Extend this dispatch when a lesson needs another."""
    function = spec["function"]
    field_id = fields[_normalize_field_name(spec["field"])]
    if function == "sum":
        return ["sum", ["field", field_id, None]]
    raise ValueError(f"unsupported aggregation function {function!r}")


def _build_breakout_mbql(spec, fields):
    field_id = fields[_normalize_field_name(spec["field"])]
    options = {"temporal-unit": spec["granularity"]} if "granularity" in spec else None
    return ["field", field_id, options]


def _find_active_card_by_name(base_url, headers, name):
    cards = requests.get(f"{base_url}/api/card", headers=headers, timeout=15).json()
    matches = [c for c in cards if c["name"] == name and not c.get("archived")]
    return matches[0] if matches else None


def _find_active_dashboard_by_name(base_url, headers, name):
    dashboards = requests.get(
        f"{base_url}/api/dashboard", headers=headers, timeout=15
    ).json()
    matches = [d for d in dashboards if d["name"] == name and not d.get("archived")]
    return matches[0] if matches else None


def _seed_question(base_url, headers, spec) -> int:
    existing = _find_active_card_by_name(base_url, headers, spec["name"])
    if existing is not None:
        print(f"[state_seed] question {spec['name']!r} already exists (id {existing['id']}), reusing")
        return existing["id"]

    db_id, table_id, fields = _resolve_table_and_fields(
        base_url, headers, spec["database"], spec["table"]
    )
    query = {"source-table": table_id}
    if "filter" in spec:
        query["filter"] = _build_filter_mbql(spec["filter"], fields)
    if "aggregation" in spec:
        query["aggregation"] = [_build_aggregation_mbql(spec["aggregation"], fields)]
    if "breakout" in spec:
        query["breakout"] = [_build_breakout_mbql(spec["breakout"], fields)]

    payload = {
        "name": spec["name"],
        "dataset_query": {"database": db_id, "type": "query", "query": query},
        "display": spec.get("display", "table"),
        "visualization_settings": spec.get("visualization_settings", {}),
    }
    resp = requests.post(f"{base_url}/api/card", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    card = resp.json()
    print(f"[state_seed] created question {spec['name']!r} (id {card['id']})")
    return card["id"]


def _seed_dashboard(base_url, headers, spec, name_to_card_id) -> int:
    existing = _find_active_dashboard_by_name(base_url, headers, spec["name"])
    if existing is not None:
        dashboard_id = existing["id"]
        print(f"[state_seed] dashboard {spec['name']!r} already exists (id {dashboard_id}), reusing")
        full = requests.get(
            f"{base_url}/api/dashboard/{dashboard_id}", headers=headers, timeout=15
        ).json()
        existing_card_ids = {dc["card_id"] for dc in full.get("dashcards", [])}
    else:
        resp = requests.post(
            f"{base_url}/api/dashboard", headers=headers, json={"name": spec["name"]}, timeout=30
        )
        resp.raise_for_status()
        dashboard_id = resp.json()["id"]
        existing_card_ids = set()
        print(f"[state_seed] created dashboard {spec['name']!r} (id {dashboard_id})")

    wanted_card_ids = [name_to_card_id[name] for name in spec.get("contains", [])]
    missing = [cid for cid in wanted_card_ids if cid not in existing_card_ids]
    if missing:
        full = requests.get(
            f"{base_url}/api/dashboard/{dashboard_id}", headers=headers, timeout=15
        ).json()
        dashcards = full.get("dashcards", [])
        next_row = max([dc.get("row", 0) + dc.get("size_y", 6) for dc in dashcards], default=0)
        new_dashcards = [
            {
                "id": -(i + 1),
                "card_id": cid,
                "row": next_row,
                "col": 0,
                "size_x": 8,
                "size_y": 6,
                "parameter_mappings": [],
            }
            for i, cid in enumerate(missing)
        ]
        existing_payload = [
            {k: v for k, v in dc.items() if k in
             ("id", "card_id", "row", "col", "size_x", "size_y", "parameter_mappings")}
            for dc in dashcards
        ]
        resp = requests.put(
            f"{base_url}/api/dashboard/{dashboard_id}",
            headers=headers,
            json={"dashcards": existing_payload + new_dashcards},
            timeout=30,
        )
        resp.raise_for_status()
        print(f"[state_seed] added {len(missing)} card(s) to dashboard {spec['name']!r}")

    return dashboard_id


def seed_required_state(base_url: str, admin_email: str, admin_password: str, requires_state: list):
    """Entry point called from run_lesson before any recording starts.
    Pure HTTP against Metabase's API, no Playwright/browser involved --
    this is infrastructure setup, not a teaching moment, so it shouldn't
    exist in the recorded footage at all, the same reasoning that put
    login/account setup in an unrecorded phase."""
    if not requires_state:
        return

    token = _login(base_url, admin_email, admin_password)
    headers = _headers(token)

    name_to_card_id = {}
    for spec in requires_state:
        if spec["type"] == "question":
            name_to_card_id[spec["name"]] = _seed_question(base_url, headers, spec)

    for spec in requires_state:
        if spec["type"] == "dashboard":
            _seed_dashboard(base_url, headers, spec, name_to_card_id)
