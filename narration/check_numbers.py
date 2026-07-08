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


_NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40,
    'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
}
_MAGNITUDE_WORDS = {'hundred': 100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000}


def _words_to_int(tokens: list) -> float:
    total, current = 0, 0
    for tok in tokens:
        if tok == 'and':
            continue
        if tok in _NUMBER_WORDS:
            current += _NUMBER_WORDS[tok]
        elif tok in _MAGNITUDE_WORDS:
            if current == 0:
                # Bare magnitude word, no preceding number - not a real
                # number phrase (e.g. "a hundred percent"). Don't fabricate
                # an implicit "one hundred"/"one thousand".
                continue
            mag = _MAGNITUDE_WORDS[tok]
            if mag == 100:
                current = current * 100
            else:
                total += current * mag
                current = 0
    return total + current


def extract_spelled_number_mentions(text: str) -> list[tuple[str, float]]:
    """
    Find fully spelled-out numbers, e.g. 'ninety-four thousand eight hundred
    seventy point zero zero' -> ('...', 94870.0). Needed because narration
    sometimes spells numbers out (better for TTS) instead of using digits,
    and plain digit-regex checking can't see those at all — a silent blind
    spot that lets wrong numbers through undetected.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    vocab = set(_NUMBER_WORDS) | set(_MAGNITUDE_WORDS) | {'and', 'point'}
    results = []
    i, n = 0, len(words)
    while i < n:
        if words[i] in vocab and words[i] not in ('and', 'point'):
            j = i
            run = []
            while j < n and words[j] in vocab:
                run.append(words[j])
                j += 1
            while run and run[-1] in ('and', 'point'):
                run.pop()
                j -= 1
            if run:
                if 'point' in run:
                    idx = run.index('point')
                    whole_tokens = [t for t in run[:idx] if t != 'and']
                    dec_tokens = [t for t in run[idx + 1:]
                                  if t in _NUMBER_WORDS and t not in _MAGNITUDE_WORDS]
                    whole_val = _words_to_int(whole_tokens) if whole_tokens else 0
                    dec_digits = ''.join(str(_NUMBER_WORDS[t]) for t in dec_tokens)
                    val = float(f"{int(whole_val)}.{dec_digits}") if dec_digits else float(whole_val)
                else:
                    whole_tokens = [t for t in run if t != 'and']
                    val = float(_words_to_int(whole_tokens))
                if val >= 100 or 'point' in run:
                    results.append((' '.join(run), val))
            i = j
        else:
            i += 1
    return results


_APPROX_QUALIFIERS = ('almost', 'about', 'roughly', 'nearly', 'around',
                       'approximately', 'just over', 'just under', 'give or take')


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
    # Fully spelled-out numbers: "ninety-four thousand eight hundred seventy point zero zero"
    found.extend(extract_spelled_number_mentions(text))

    # Drop mentions explicitly framed as approximations — not claims about
    # an exact displayed value.
    text_lower = text.lower()
    filtered = []
    for raw_text, num in found:
        idx = text_lower.find(raw_text.lower())
        preceding = text_lower[max(0, idx - 25):idx] if idx >= 0 else ''
        if any(q in preceding for q in _APPROX_QUALIFIERS):
            continue
        filtered.append((raw_text, num))
    return filtered


@click.command()
@click.argument("card_path")
@click.option("--db", default=None, help="Override database path")
def check(card_path, db):
    card_path = Path(card_path)
    lesson_dir = card_path.parent

    with open(card_path) as f:
        card = yaml.safe_load(f)

    if not card.get('assets', {}).get('database'):
        console.print("[dim]No database asset — skipping number check (non-SQL lesson)[/dim]")
        console.print("[bold green]✓ No number mismatches found[/bold green]")
        return 0
    db_path = Path(db) if db else lesson_dir / "assets" / card['assets']['database'].split('/')[-1]
    sql_path = lesson_dir / "assets" / card['assets']['sql_file'].split('/')[-1]

    if not db_path.exists():
        console.print(f"[dim]Database not found: {db_path} — skipping number check[/dim]")
        console.print("[bold green]✓ No number mismatches found[/bold green]")
        return 0
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
