#!/usr/bin/env python3
"""
WSDA Number Pre-Check

Run BEFORE recording. Checks every narration block in a production card
against actual query results from the database — using the SAME 2-decimal
rounding the SQL viewer uses to render numbers on screen.

This catches "narration says X but screen shows Y" errors before you
spend time recording and synthesizing audio.

Usage:
  python3 narration/check_numbers.py courses/novabridge/video_1_3/production_card.yml
"""

import re
import sqlite3
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


def parse_sql_sections(sql_file: Path) -> dict:
    content = sql_file.read_text()
    sections, cur, lines = {}, None, []
    for line in content.splitlines():
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


def get_display_values(db_path: Path, sql: str) -> list[float]:
    """Run query, return values rounded exactly as the viewer displays them."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
    finally:
        conn.close()
    values = []
    for row in rows:
        for val in row:
            if isinstance(val, (int, float)):
                values.append(round(float(val), 2))
    return values


def extract_decimal_mentions(text: str) -> list[tuple[str, float]]:
    """Find decimal numbers and number-words in narration text."""
    found = []
    # Plain decimals: 0.05, 0.0487
    for m in re.finditer(r'\b0\.\d+\b', text):
        found.append((m.group(), float(m.group())))
    # "zero point zero five" style
    word_digits = {'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,
                   'six':6,'seven':7,'eight':8,'nine':9}
    for m in re.finditer(r'zero point (\w+)(?:\s+(\w+))?(?:\s+(\w+))?(?:\s+(\w+))?', text.lower()):
        digits = [word_digits.get(g) for g in m.groups() if g and g in word_digits]
        if digits:
            num_str = "0." + "".join(str(d) for d in digits)
            found.append((m.group(), float(num_str)))
    return found


@click.command()
@click.argument("card_path")
@click.option("--db", default=None, help="Override database path")
def check(card_path, db):
    card_path = Path(card_path)
    lesson_dir = card_path.parent

    with open(card_path) as f:
        card = yaml.safe_load(f)

    db_path = Path(db) if db else lesson_dir / "assets" / card['assets']['database'].split('/')[-1]
    sql_path = lesson_dir / "assets" / card['assets']['sql_file'].split('/')[-1]

    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        return
    if not sql_path.exists():
        console.print(f"[red]SQL file not found: {sql_path}[/red]")
        return

    sections = parse_sql_sections(sql_path)
    console.print(f"\n[bold]Number Pre-Check[/bold]: {card_path}")
    console.print(f"Found {len(sections)} queries: {list(sections.keys())}\n")

    # Show display values for every query
    table = Table(title="Actual Displayed Values (2-decimal rounded)")
    table.add_column("Query")
    table.add_column("Displayed Values")

    query_display_values = {}
    for name, sql in sections.items():
        try:
            vals = get_display_values(db_path, sql)
            query_display_values[name] = vals
            table.add_row(name, ", ".join(f"{v:.2f}" for v in vals))
        except Exception as e:
            table.add_row(name, f"[red]ERROR: {e}[/red]")

    console.print(table)

    # Now check each narration block
    issues = []
    events = card.get('events', [])
    for i, e in enumerate(events):
        narr = (e.get('narration') or '').strip()
        if not narr:
            continue
        query_ref = e.get('query_ref')
        # Try to infer query from preceding events if not explicit
        if not query_ref:
            for j in range(i, -1, -1):
                if events[j].get('query_ref'):
                    query_ref = events[j]['query_ref']
                    break

        if not query_ref or query_ref not in query_display_values:
            continue

        actual = query_display_values[query_ref]
        mentioned = extract_decimal_mentions(narr)

        for raw_text, num in mentioned:
            match = any(abs(num - v) < 0.005 for v in actual)
            if not match:
                issues.append({
                    'event': e['id'],
                    'query': query_ref,
                    'mentioned': raw_text,
                    'value': num,
                    'actual': actual,
                })

    if issues:
        console.print(f"\n[bold red]Found {len(issues)} number mismatches:[/bold red]\n")
        for iss in issues:
            console.print(f"  [red]✗[/red] {iss['event']} ({iss['query']}): "
                          f"narration says '{iss['mentioned']}' ({iss['value']}) "
                          f"but screen will show {iss['actual']}")
        console.print(f"\n[yellow]Fix these before recording.[/yellow]")
    else:
        console.print(f"\n[bold green]✓ No number mismatches found[/bold green]")

    return len(issues)


if __name__ == "__main__":
    check()
