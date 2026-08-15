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
        if tok == 'a' and current == 0:
            # "a hundred", "a thousand" -> implicit one
            current = 1
        elif tok in _NUMBER_WORDS:
            current += _NUMBER_WORDS[tok]
        elif tok in _MAGNITUDE_WORDS:
            if current == 0:
                # Bare magnitude word with no preceding number - not a real
                # number phrase (e.g. "a hundred percent" used loosely).
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

    Splits on punctuation FIRST so a number-word run never crosses a real
    sentence/list boundary. Without this, "order 1001, eighty-four
    forty-nine" reads as two adjacent numbers with nothing (after stripping
    punctuation) to separate them, and gets merged into one garbage number.

    Also handles "negative" / "minus" prefixes so "negative four hundred"
    becomes -400 and matches on-screen negative values.
    """
    vocab = set(_NUMBER_WORDS) | set(_MAGNITUDE_WORDS) | {'and', 'point', 'a'}
    negation_words = {'negative', 'minus'}
    results = []

    for segment in re.split(r'[,.;:]', text.lower()):
        words = re.findall(r"[a-zA-Z']+", segment)
        i, n = 0, len(words)
        while i < n:
            if words[i] in vocab and words[i] not in ('and', 'point'):
                # Check for a negation word immediately before this number run.
                negated = i > 0 and words[i - 1] in negation_words
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
                        # A magnitude after the decimal (e.g. "two point three million")
                        # applies to the entire decimal value.
                        tail = [t for t in run[idx + 1:] if t != 'and']
                        trailing_mag_word = None
                        trailing_mag = None
                        if tail and tail[-1] in _MAGNITUDE_WORDS:
                            trailing_mag_word = tail[-1]
                            trailing_mag = _MAGNITUDE_WORDS[trailing_mag_word]
                            tail = tail[:-1]
                        dec_tokens = [t for t in tail if t in _NUMBER_WORDS and t not in _MAGNITUDE_WORDS]
                        whole_val = _words_to_int(whole_tokens) if whole_tokens else 0
                        dec_digits = ''.join(str(_NUMBER_WORDS[t]) for t in dec_tokens)
                        val = float(f"{int(whole_val)}.{dec_digits}") if dec_digits else float(whole_val)
                        if trailing_mag:
                            val = val * trailing_mag
                    else:
                        whole_tokens = [t for t in run if t != 'and']
                        val = float(_words_to_int(whole_tokens))
                        trailing_mag_word = None

                    if negated:
                        val = -val
                    if val >= 100 or 'point' in run or val <= -100:
                        display = ('negative ' if negated else '') + ' '.join(run)
                        results.append((display, val))
                i = j
            else:
                i += 1
    return results


_APPROX_QUALIFIERS = ('almost', 'about', 'roughly', 'nearly', 'around',
                       'approximately', 'just over', 'just under', 'over', 'under',
                       'more than', 'less than', 'give or take')


# Reverse lookup for converting corrected numeric values back to narration text.
_NUM_WORD = {v: k for k, v in _NUMBER_WORDS.items()}


def _int_to_words(n: int) -> str:
    """Convert a non-negative integer into spelled-out English words."""
    if n == 0:
        return "zero"
    if n < 0:
        return "negative " + _int_to_words(-n)

    parts = []
    if n >= 1_000_000_000:
        parts.append(_int_to_words(n // 1_000_000_000) + " billion")
        n %= 1_000_000_000
    if n >= 1_000_000:
        parts.append(_int_to_words(n // 1_000_000) + " million")
        n %= 1_000_000
    if n >= 1_000:
        parts.append(_int_to_words(n // 1_000) + " thousand")
        n %= 1_000
    if n >= 100:
        parts.append(_int_to_words(n // 100) + " hundred")
        n %= 100
    if n > 0:
        if n < 20:
            parts.append(_NUM_WORD[n])
        else:
            tens = (n // 10) * 10
            units = n % 10
            word = _NUM_WORD[tens]
            if units:
                word += " " + _NUM_WORD[units]
            parts.append(word)
    return " ".join(parts)


def _number_to_words(val: float) -> str:
    """Convert a numeric display value into TTS-friendly spelled-out words."""
    if val < 0:
        return "negative " + _number_to_words(-val)
    if isinstance(val, float) and not val.is_integer():
        # Render up to 2 decimal places (viewer rounds to 2 decimals).
        s = f"{val:.2f}" if (val * 100) % 1 < 0.0001 else f"{val:.10f}".rstrip('0')
        whole_str, frac_str = s.split('.')
        whole = _int_to_words(int(whole_str))
        digits = ' '.join(_NUM_WORD[int(d)] for d in frac_str)
        return f"{whole} point {digits}"
    return _int_to_words(int(val))


def _is_likely_year(num: float) -> bool:
    """Heuristic: 4-digit numbers in the 1900-2099 range are probably years/IDs."""
    return 1900 <= num <= 2099


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


def extract_number_mentions(text: str) -> list[tuple[str, float]]:
    """Find both spelled-out numbers and plain digit numbers in narration.

    Digit extraction is conservative: it ignores likely years (1900-2099) and
    small values (< 100) that are usually ordinary counts/IDs, not on-screen
    display values. This keeps the gate strict without drowning the user in
    false positives.
    """
    found = extract_decimal_mentions(text)

    # Plain digit numbers: 433100, 2,325,300, 8082500.00
    for m in re.finditer(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d{3,}(?:\.\d+)?\b', text):
        raw = m.group()
        num_str = raw.replace(',', '')
        try:
            num = float(num_str)
        except ValueError:
            continue
        # Skip likely years/IDs unless they have decimals.
        if '.' not in raw and _is_likely_year(num):
            continue
        found.append((raw, num))

    # De-duplicate overlapping mentions, keeping the longer/more specific match.
    seen = set()
    unique = []
    for raw, num in found:
        key = (raw.lower(), num)
        if key in seen:
            continue
        seen.add(key)
        unique.append((raw, num))
    return unique


def _value_match(num: float, allowed: set[float]) -> bool:
    """Return True if num is close enough to a value in the allowed set."""
    return any(abs(num - v) < (1.0 if abs(v) >= 100 else 0.005) for v in allowed)


def _collect_mismatches(card: dict, query_display_values: dict[str, list[float]]) -> list[dict]:
    """Core mismatch detection shared by CLI and draft.py."""
    issues = []
    events = card.get('events', [])
    revealed_so_far = set()

    for i, e in enumerate(events):
        if e.get('query_ref') and e['query_ref'] in query_display_values:
            revealed_so_far.add(e['query_ref'])

        narr = (e.get('narration') or '').strip()
        if not narr:
            continue

        if not revealed_so_far:
            continue

        allowed = set()
        for ref in revealed_so_far:
            allowed.update(query_display_values[ref])

        mentioned = extract_number_mentions(narr)

        for raw_text, num in mentioned:
            if not _value_match(num, allowed):
                issues.append({
                    'event': e['id'],
                    'query': ', '.join(sorted(revealed_so_far)),
                    'mentioned': raw_text,
                    'value': num,
                    'actual': sorted(allowed),
                })

    return issues


def find_mismatches(card_path: Path, db: Path | None = None) -> list[dict]:
    """Return a list of number mismatches without printing."""
    card_path = Path(card_path)
    lesson_dir = card_path.parent

    with open(card_path) as f:
        card = yaml.safe_load(f)

    if not card.get('assets', {}).get('database'):
        return []
    db_path = Path(db) if db else lesson_dir / "assets" / card['assets']['database'].split('/')[-1]
    sql_path = lesson_dir / "assets" / card['assets']['sql_file'].split('/')[-1]

    if not db_path.exists() or not sql_path.exists():
        return []

    sections = parse_sql_sections(sql_path)
    query_display_values = {}
    for name, sql in sections.items():
        try:
            query_display_values[name] = get_display_values(db_path, sql)
        except Exception:
            pass

    return _collect_mismatches(card, query_display_values)


def fix_narration_numbers(narr: str, allowed: set[float]) -> tuple[str, int, list[dict]]:
    """Auto-correct numeric mentions in one narration block.

    Returns (fixed_text, replacements_made, unresolved_issues). Replacements
    are written back as spelled-out words so TTS reads them correctly.
    """
    mentions = extract_number_mentions(narr)
    fixed_text = narr
    replacements = 0
    unresolved = []

    for raw_text, num in mentions:
        if _value_match(num, allowed):
            continue

        # Find the closest allowed value.
        closest = None
        min_diff = float('inf')
        for v in allowed:
            diff = abs(num - v)
            if diff < min_diff:
                min_diff = diff
                closest = v

        # Sign errors are common (narration drops a negative). Fix them even
        # though the absolute difference is large.
        sign_fixed = None
        for v in allowed:
            if abs(v) > 0 and abs(abs(num) - abs(v)) < (1.0 if abs(v) >= 100 else 0.005):
                sign_fixed = v
                break

        chosen = sign_fixed if sign_fixed is not None else closest
        if chosen is None:
            unresolved.append({
                'mentioned': raw_text,
                'value': num,
                'actual': sorted(allowed),
            })
            continue

        # Accept sign fixes unconditionally; for other mismatches require the
        # closest value to be reasonably close (1% or 1 unit, whichever is larger).
        if sign_fixed is None:
            tol = max(abs(num) * 0.01, 1.0) if abs(num) >= 100 else 0.005
            if min_diff > tol:
                unresolved.append({
                    'mentioned': raw_text,
                    'value': num,
                    'actual': sorted(allowed),
                })
                continue

        correct_words = _number_to_words(chosen)
        fixed_text = fixed_text.replace(raw_text, correct_words, 1)
        replacements += 1

    return fixed_text, replacements, unresolved


def fix_card_numbers(card_path: Path, db: Path | None = None) -> tuple[int, list[dict]]:
    """Rewrite a production card so every narration number matches on-screen values.

    Returns (number_of_fixes, unresolved_issues).
    """
    card_path = Path(card_path)
    lesson_dir = card_path.parent

    with open(card_path) as f:
        card = yaml.safe_load(f)

    if not card.get('assets', {}).get('database'):
        return 0, []

    db_path = Path(db) if db else lesson_dir / "assets" / card['assets']['database'].split('/')[-1]
    sql_path = lesson_dir / "assets" / card['assets']['sql_file'].split('/')[-1]
    if not db_path.exists() or not sql_path.exists():
        return 0, []

    sections = parse_sql_sections(sql_path)
    query_display_values = {}
    for name, sql in sections.items():
        try:
            query_display_values[name] = get_display_values(db_path, sql)
        except Exception:
            pass

    events = card.get('events', [])
    revealed_so_far = set()
    total_fixed = 0
    unresolved = []

    for e in events:
        if e.get('query_ref') and e['query_ref'] in query_display_values:
            revealed_so_far.add(e['query_ref'])

        narr = (e.get('narration') or '').strip()
        if not narr or not revealed_so_far:
            continue

        allowed = set()
        for ref in revealed_so_far:
            allowed.update(query_display_values[ref])

        fixed, replacements, issues = fix_narration_numbers(narr, allowed)
        if replacements:
            e['narration'] = fixed
            total_fixed += replacements
        for iss in issues:
            unresolved.append({'event': e.get('id'), **iss})

    if total_fixed:
        card_path.write_text(yaml.dump(card, sort_keys=False))

    return total_fixed, unresolved


@click.command()
@click.argument("card_path")
@click.option("--db", default=None, help="Override database path")
@click.option("--fix", is_flag=True, help="Auto-fix mismatches in the production card")
def check(card_path, db, fix):
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

    issues = _collect_mismatches(card, query_display_values)

    if fix:
        fixed_count, unresolved = fix_card_numbers(card_path, db)
        if fixed_count:
            console.print(f"\n[green]✓ Auto-fixed {fixed_count} number mention(s) in {card_path.name}[/green]")
        if unresolved:
            console.print(f"\n[yellow]{len(unresolved)} number mention(s) could not be auto-fixed:[/yellow]")
            for iss in unresolved:
                console.print(f"  - {iss['event']}: '{iss['mentioned']}' ({iss['value']}) not in {iss['actual']}")
        # Reload card and re-check so the user sees the final state.
        card = yaml.safe_load(card_path.read_text())
        issues = _collect_mismatches(card, query_display_values)
        if not issues and not unresolved:
            console.print(f"\n[bold green]✓ No number mismatches found[/bold green]")
        return len(issues) + len(unresolved)

    if issues:
        console.print(f"\n[bold red]Found {len(issues)} number mismatches:[/bold red]\n")
        for iss in issues:
            console.print(f"  [red]✗[/red] {iss['event']} ({iss['query']}): "
                          f"narration says '{iss['mentioned']}' ({iss['value']}) "
                          f"but screen will show {iss['actual']}")
        console.print(f"\n[yellow]Fix these before recording, or run with --fix to auto-correct.[/yellow]")
    else:
        console.print(f"\n[bold green]✓ No number mismatches found[/bold green]")

    return len(issues)


if __name__ == "__main__":
    check()
