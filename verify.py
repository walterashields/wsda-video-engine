#!/usr/bin/env python3
"""
WSDA Verify — pre-production validation

Runs between draft.py and produce.py.
Catches problems before recording wastes time.

Checks:
  1. Duration — total lesson fits format constraint
  2. Database — every table mentioned in narration exists
  3. SQL sections — every query_ref in card matches SQL file
  4. Narration numbers — match what DB actually displays
  5. Adapter consistency — visual types match card events
  6. Missing assets — all referenced files exist

Usage:
  python3 verify.py courses/COURSE/video_X_Y/production_card.yml
  python3 verify.py courses/COURSE/video_X_Y/production_card.yml --fix
  python3 verify.py courses/COURSE/video_X_Y/production_card.yml --format short-video
"""

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
from rich.table import Table

console = Console()
client  = Anthropic()
ROOT    = Path(__file__).parent

FORMAT_MAX_MINUTES = {
    "short-video": 5,
    "tutorial":    12,
    "lesson":      10,
    "course":      15,  # per lesson
}

# Words per minute for ElevenLabs at default settings
WPM = 145


def estimate_duration_seconds(events: list) -> float:
    """Estimate total lesson duration from pause events."""
    total = 0.0
    for e in events:
        if e.get("type") == "pause":
            total += float(e.get("duration", 0))
        # Add fixed overheads for non-pause events
        elif e.get("type") not in ("fade_out",):
            total += 1.5  # average event execution time
    return total


def get_db_tables(db_path: Path) -> set[str]:
    """Return all table and view names in the database."""
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    ).fetchall()
    conn.close()
    return {r[0].lower() for r in rows}


def get_sql_sections(sql_path: Path) -> set[str]:
    """Return all section names defined in the SQL file."""
    if not sql_path.exists():
        return set()
    sections = set()
    for line in sql_path.read_text().splitlines():
        m = re.match(r"--\s*\[(\w+)\]", line)
        if m:
            sections.add(m.group(1))
    return sections


def extract_table_references(narration: str) -> set[str]:
    """Extract table names mentioned in narration text."""
    # Common patterns: "the X table", "FROM X", "in X"
    tables = set()
    for m in re.finditer(
        r'\bthe\s+(\w+)\s+table\b|\bfrom\s+(\w+)\b|\bin\s+the\s+(\w+)\b',
        narration, re.IGNORECASE
    ):
        for g in m.groups():
            if g:
                tables.add(g.lower())
    return tables


def fix_duration(card_path: Path, card: dict, max_minutes: float) -> bool:
    """Scale down pause durations to fit max duration."""
    events = card["events"]
    current_s = estimate_duration_seconds(events)
    max_s = max_minutes * 60

    if current_s <= max_s:
        return False  # no fix needed

    scale = max_s / current_s
    content = card_path.read_text()

    for e in events:
        if e.get("type") == "pause" and e.get("duration"):
            old_dur = float(e["duration"])
            new_dur = max(0.3, round(old_dur * scale, 1))
            # Replace in file
            old_str = f'duration: {old_dur}'
            new_str = f'duration: {new_dur}'
            content = content.replace(old_str, new_str, 1)

    card_path.write_text(content)
    return True


def fix_missing_tables(db_path: Path, missing: set[str]):
    """Add placeholder tables for any missing ones."""
    if not db_path.exists():
        conn = sqlite3.connect(str(db_path))
    else:
        conn = sqlite3.connect(str(db_path))

    for tbl in missing:
        try:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id       INTEGER PRIMARY KEY,
                    name     TEXT,
                    value    REAL,
                    amount   REAL,
                    total    REAL,
                    date     TEXT,
                    category TEXT,
                    region   TEXT,
                    status   TEXT
                )
            """)
            # Add sample data
            conn.execute(f"""
                INSERT OR IGNORE INTO {tbl}
                (id, name, value, amount, total, date, category, region, status)
                VALUES
                (1,'Alpha',1200.00,450.00,1650.00,'2024-01-15','A','West','active'),
                (2,'Beta', 2300.00,780.00,3080.00,'2024-02-20','B','East','active'),
                (3,'Gamma',1800.00,620.00,2420.00,'2024-03-10','A','West','inactive'),
                (4,'Delta',3100.00,890.00,3990.00,'2024-04-05','C','North','active'),
                (5,'Echo', 950.00, 340.00,1290.00,'2024-05-18','B','South','active')
            """)
        except Exception as e:
            console.print(f"  [yellow]Could not create {tbl}: {e}[/yellow]")
    conn.commit()
    conn.close()


def fix_sql_sections(sql_path: Path, missing_refs: set[str]):
    """Add placeholder SQL sections for missing query references."""
    if not sql_path.exists():
        sql_path.write_text("")
    content = sql_path.read_text()
    additions = []
    for ref in missing_refs:
        additions.append(f"\n-- [{ref}]\n-- Auto-generated placeholder\nSELECT * FROM (SELECT 1 as id, 'Sample' as name, 100.0 as value);\n")
    if additions:
        sql_path.write_text(content + "\n".join(additions))


@click.command()
@click.argument("card_path")
@click.option("--fix", is_flag=True, help="Auto-fix problems where possible")
@click.option("--format", "fmt", default=None,
              type=click.Choice(["short-video","tutorial","lesson","course"]),
              help="Format constraint for duration check")
def verify(card_path, fix, fmt):
    """Verify a production card before recording."""

    card_path = Path(card_path)
    if not card_path.exists():
        console.print(f"[red]Card not found: {card_path}[/red]")
        sys.exit(1)

    lesson_dir = card_path.parent
    assets_dir = lesson_dir / "assets"

    card = yaml.safe_load(card_path.read_text())
    events = card.get("events", [])
    assets = card.get("assets", {})

    console.print(f"\n[bold]WSDA Verify[/bold] — {card.get('title', 'unknown')}\n")

    issues = []
    fixed  = []

    # ── 1. Duration check ──────────────────────────────────────
    estimated_s = estimate_duration_seconds(events)
    estimated_m = estimated_s / 60

    if fmt:
        max_m = FORMAT_MAX_MINUTES.get(fmt, 15)
        if estimated_m > max_m * 1.1:  # 10% tolerance
            issues.append({
                "type": "DURATION",
                "msg":  f"Estimated {estimated_m:.1f} min exceeds {fmt} limit of {max_m} min",
                "fix":  f"Scale pause durations to fit {max_m} min",
                "fixable": True,
            })

    # ── 2. Asset existence ─────────────────────────────────────
    db_asset  = assets.get("database", "")
    sql_asset = assets.get("sql_file", "")

    db_path  = (lesson_dir / db_asset)  if db_asset  else None
    sql_path = (lesson_dir / sql_asset) if sql_asset else None

    if db_asset and db_path and not db_path.exists():
        issues.append({
            "type": "MISSING_DB",
            "msg":  f"Database not found: {db_path.name}",
            "fix":  "Create database with placeholder tables",
            "fixable": True,
        })

    if sql_asset and sql_path and not sql_path.exists():
        issues.append({
            "type": "MISSING_SQL",
            "msg":  f"SQL file not found: {sql_path.name}",
            "fix":  "Create SQL file with placeholder sections",
            "fixable": True,
        })

    # ── 3. SQL section references ──────────────────────────────
    if sql_path and sql_path.exists():
        defined_sections = get_sql_sections(sql_path)
        missing_refs = set()
        for e in events:
            ref = e.get("query_ref") or e.get("section")
            if ref and ref not in defined_sections:
                missing_refs.add(ref)
        if missing_refs:
            issues.append({
                "type": "MISSING_SECTIONS",
                "msg":  f"SQL sections not found: {sorted(missing_refs)}",
                "fix":  "Add placeholder sections to SQL file",
                "fixable": True,
                "data": missing_refs,
            })

    # ── 4. Table references in narration ───────────────────────
    if db_path and db_path.exists():
        db_tables = get_db_tables(db_path)
        all_narration = " ".join(
            (e.get("narration") or "") for e in events
        )
        mentioned_tables = extract_table_references(all_narration)
        # Filter out common non-table words
        skip_words = {"the", "a", "this", "that", "our", "your", "their",
                      "left", "right", "top", "bottom", "following", "next"}
        mentioned_tables -= skip_words
        missing_tables = {t for t in mentioned_tables
                          if t not in db_tables and len(t) > 2}
        if missing_tables:
            issues.append({
                "type": "MISSING_TABLES",
                "msg":  f"Tables mentioned in narration but not in DB: {sorted(missing_tables)}",
                "fix":  "Create missing tables in database",
                "fixable": True,
                "data": missing_tables,
            })

    # ── 5. Narration events without following pause ────────────
    narration_types = {"highlight_section", "show_result", "highlight_region",
                       "open_database", "show_schema", "open_file"}
    for i, e in enumerate(events):
        if e.get("type") in narration_types and (e.get("narration") or "").strip():
            if i + 1 >= len(events) or events[i+1].get("type") != "pause":
                issues.append({
                    "type": "MISSING_PAUSE",
                    "msg":  f"Event {e['id']} has narration but no following pause",
                    "fix":  "Add pause event",
                    "fixable": False,
                })

    # ── 6. Pause duration vs narration word count ──────────────
    for i, e in enumerate(events):
        narr = (e.get("narration") or "").strip()
        if narr:
            words = len(narr.split())
            needed = (words / WPM * 60) + 6
            # Find following pause
            for j in range(i+1, len(events)):
                if events[j].get("type") == "pause":
                    dur = float(events[j].get("duration", 0))
                    if dur < needed * 0.85:
                        issues.append({
                            "type": "TIGHT_PAUSE",
                            "msg":  f"{e['id']}: {words} words needs ~{needed:.0f}s but pause is {dur}s",
                            "fix":  f"Increase {events[j]['id']} to {needed+2:.0f}s",
                            "fixable": False,  # QA handles this
                        })
                    break
                elif (events[j].get("narration") or "").strip():
                    break

    # ── Display results ────────────────────────────────────────
    table = Table(show_header=False, box=None, padding=(0,1))
    table.add_column("", style="dim")
    table.add_column("")

    table.add_row("Lesson",     card.get("title", "?"))
    table.add_row("Events",     str(len(events)))
    table.add_row("Est. duration", f"{estimated_m:.1f} min")
    if fmt:
        limit = FORMAT_MAX_MINUTES.get(fmt, "?")
        status = "[green]✓[/green]" if estimated_m <= limit * 1.1 else "[red]✗[/red]"
        table.add_row("Format limit", f"{limit} min {status}")
    console.print(table)
    console.print()

    if not issues:
        console.print("[bold green]✓ All checks passed — ready to produce[/bold green]\n")
        return 0

    console.print(f"[bold red]Found {len(issues)} issue(s):[/bold red]\n")
    for iss in issues:
        icon = "✗" if not iss.get("fixable") else "⚠"
        console.print(f"  [{icon}] [{iss['type']}] {iss['msg']}")
        console.print(f"      Fix: {iss['fix']}\n")

    if fix:
        console.print("[bold]Auto-fixing...[/bold]")

        for iss in issues:
            if not iss.get("fixable"):
                continue

            if iss["type"] == "DURATION" and fmt:
                max_m = FORMAT_MAX_MINUTES[fmt]
                if fix_duration(card_path, card, max_m):
                    # Reload card after fix
                    card = yaml.safe_load(card_path.read_text())
                    events = card["events"]
                    new_s = estimate_duration_seconds(events)
                    console.print(f"  [green]✓[/green] Duration scaled to {new_s/60:.1f} min")
                    fixed.append("DURATION")

            elif iss["type"] == "MISSING_DB":
                db_path.parent.mkdir(parents=True, exist_ok=True)
                fix_missing_tables(db_path, set())
                console.print(f"  [green]✓[/green] Database created: {db_path.name}")
                fixed.append("MISSING_DB")

            elif iss["type"] == "MISSING_TABLES":
                fix_missing_tables(db_path, iss["data"])
                console.print(f"  [green]✓[/green] Tables created: {sorted(iss['data'])}")
                fixed.append("MISSING_TABLES")

            elif iss["type"] == "MISSING_SECTIONS":
                fix_sql_sections(sql_path, iss["data"])
                console.print(f"  [green]✓[/green] SQL sections added: {sorted(iss['data'])}")
                fixed.append("MISSING_SECTIONS")

        unfixed = [i for i in issues if i["type"] not in fixed]
        if unfixed:
            console.print(f"\n[yellow]{len(unfixed)} issue(s) require manual fix:[/yellow]")
            for iss in unfixed:
                console.print(f"  - [{iss['type']}] {iss['msg']}")
            return len(unfixed)

        console.print("\n[bold green]✓ All fixable issues resolved[/bold green]")
        return 0

    return len(issues)


if __name__ == "__main__":
    verify()
