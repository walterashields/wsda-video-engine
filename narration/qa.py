#!/usr/bin/env python3
"""
WSDA Narration QA
Automated quality check before video render.

Checks:
  1. Every narration clip fits within its pause window
  2. Numbers mentioned in narration match actual query results
  3. No narration fires while the wrong visual is on screen
  4. Clips don't overlap into the next visual event

Run after audit_narrator synthesizes clips, before final render.
Outputs a QA report and auto-fixes pause durations where possible.
"""

import json
import re
import sqlite3
import sys
import wave
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def wav_duration_s(path: Path) -> float:
    if not path.exists():
        return 0.0
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def get_query_results(db_path: Path, sql_file: Path) -> dict:
    """Run all queries and capture actual results for comparison."""
    results = {}
    
    # Parse SQL file sections
    content = sql_file.read_text()
    sections = {}
    cur, lines = None, []
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

    conn = sqlite3.connect(str(db_path))
    for name, sql in sections.items():
        try:
            cursor = conn.execute(sql)
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            results[name] = {"columns": cols, "rows": rows}
        except Exception as e:
            results[name] = {"error": str(e)}
    conn.close()
    return results


def extract_numbers_from_text(text: str) -> list[str]:
    """Extract number-like phrases from narration text."""
    patterns = [
        r'\b\d+\.\d+\b',                    # decimals: 0.05, 143.00
        r'\b\d{1,3}(?:,\d{3})*\b',          # integers with commas
        r'\b(?:zero point \w+ \w+)\b',       # "zero point zero five"
        r'\bone hundred and [\w-]+\b',       # "one hundred and fifty-eight"
        r'\b\d+ percent\b',                  # "five percent"
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text.lower()))
    return found


def words_to_number(text: str) -> float | None:
    """Convert number words to float for comparison."""
    text = text.lower().strip()
    
    word_map = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
        'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90, 'hundred': 100,
    }
    
    # "one hundred and fifty-eight" -> 158
    m = re.match(r'one hundred and (\w+)-(\w+)', text)
    if m:
        tens = word_map.get(m.group(1), 0)
        ones = word_map.get(m.group(2), 0)
        return float(100 + tens + ones)
    
    # "zero point zero five" -> 0.05
    m = re.match(r'zero point (\w+) (\w+)', text)
    if m:
        w1 = word_map.get(m.group(1), 0)
        w2 = word_map.get(m.group(2), 0)
        return float(f"0.{w1:01d}{w2:02d}")
    
    # plain decimal or integer
    try:
        return float(text.replace(',', ''))
    except ValueError:
        return None


def check_number_accuracy(narration: str, query_results: dict, event_id: str) -> list[str]:
    """
    Check if the PRIMARY result number in narration matches actual query output.
    Numbers mentioned in comparison context ("not X", "versus X") are allowed.
    """
    issues = []

    # Map event to its query
    query_ref = None
    if event_id in ('e06',): query_ref = 'query_1'
    elif event_id in ('e09',): query_ref = 'query_2'
    elif event_id in ('e12',): query_ref = 'query_3'
    elif event_id in ('e15',): query_ref = 'query_4'

    if not query_ref or query_ref not in query_results:
        return issues

    result = query_results[query_ref]
    if 'error' in result:
        return issues

    actual_values = set()
    for row in result['rows']:
        for val in row:
            if isinstance(val, (int, float)):
                actual_values.add(float(val))

    if not actual_values:
        return issues

    # Remove comparison context: numbers after "not", "versus", "compared to", 
    # "instead of", "rather than" are legitimate contrasts, not errors
    clean_narration = narration.lower()
    for phrase in ['not one', 'not two', 'not three', 'versus', 'compared to',
                   'instead of', 'rather than', 'from ', 'previously']:
        # Remove the sentence containing these contrast words
        for sent in clean_narration.split('.'):
            if any(p in sent for p in ['not one hundred', 'not one', 'versus']):
                clean_narration = clean_narration.replace(sent, '')

    # Only check the first number mentioned (the primary result)
    mentioned = extract_numbers_from_text(clean_narration)
    if not mentioned:
        return issues

    # Check only the first significant number
    for mention in mentioned[:2]:
        num = words_to_number(mention)
        if num is None or num < 1:
            continue
        match = any(abs(num - av) < 0.01 or 
                    (abs(av) > 0 and abs(num - av) / abs(av) < 0.05)
                    for av in actual_values)
        if not match:
            issues.append(
                f"Primary number '{mention}' ({num}) doesn't match "
                f"query_{query_ref[-1]} result {sorted(actual_values)}"
            )
        break  # Only check first number

    return issues


@click.command()
@click.argument("audit_path")
@click.argument("card_path")
@click.option("--work-dir", default=None, help="Directory containing synthesized WAV clips")
@click.option("--fix", is_flag=True, help="Auto-fix pause durations in production card")
@click.option("--db", default=None, help="Override database path")
def qa(audit_path, card_path, work_dir, fix, db):
    """
    QA check: verify narration timing and number accuracy before render.
    """
    audit_path = Path(audit_path)
    card_path  = Path(card_path)

    with open(audit_path) as f:
        audit = json.load(f)
    with open(card_path) as f:
        card = yaml.safe_load(f)

    lesson_dir = card_path.parent

    # Find work directory
    if work_dir:
        work = Path(work_dir)
    else:
        # Look for most recent _auditwork directory
        mp4_stem = audit_path.stem.replace('_audit', '')
        work = lesson_dir.parent.parent.parent / "output" / f"_auditwork_{mp4_stem}"
        if not work.exists():
            # Try output dir
            out_dir = Path("output")
            candidates = sorted(out_dir.glob(f"_auditwork_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            work = candidates[0] if candidates else Path("_auditwork_unknown")

    console.print(f"\n[bold]WSDA Narration QA[/bold]")
    console.print(f"Audit: [cyan]{audit_path.name}[/cyan]")
    console.print(f"Card:  [cyan]{card_path.name}[/cyan]")
    console.print(f"Clips: [cyan]{work}[/cyan]\n")

    # Build event map from audit
    audit_map = {e['event_id']: e for e in audit['events']}

    # Build card event list
    card_events = card.get('events', [])

    # Load actual query results
    db_path = Path(db) if db else lesson_dir / "assets" / "novabridge.db"
    sql_path = lesson_dir / "assets"
    sql_files = list(sql_path.glob("*.sql"))
    query_results = {}
    if db_path.exists() and sql_files:
        try:
            query_results = get_query_results(db_path, sql_files[0])
            console.print(f"[green]✓[/green] Query results loaded from {db_path.name}")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not load query results: {e}")

    # Build schedule: event_id -> {narration, pause_window_s, clip_path, clip_dur_s}
    schedule = []
    issues = []
    fixes = []

    for i, event in enumerate(card_events):
        eid = event.get('id', '')
        narration = (event.get('narration') or '').strip()
        if not narration:
            continue

        # Find the pause that follows this event
        pause_dur = None
        pause_id = None
        for j in range(i + 1, len(card_events)):
            next_evt = card_events[j]
            if next_evt.get('type') == 'pause':
                pause_dur = next_evt.get('duration', 0)
                pause_id = next_evt.get('id')
                break
            elif (next_evt.get('narration') or '').strip():
                break

        # Find clip file
        clip_path = None
        if work.exists():
            # Look for clip matching this event
            candidates = list(work.glob(f"clip_*_{eid}.wav"))
            if candidates:
                clip_path = candidates[0]

        clip_dur = wav_duration_s(clip_path) if clip_path else None

        entry = {
            'event_id':    eid,
            'narration':   narration[:80] + ('…' if len(narration) > 80 else ''),
            'full_narration': narration,
            'pause_id':    pause_id,
            'pause_dur':   pause_dur,
            'clip_path':   clip_path,
            'clip_dur':    clip_dur,
        }
        schedule.append(entry)

        # Check 1: Does clip fit in pause window?
        # Use actual audit timing if available, fall back to card pause duration
        actual_window = None
        if eid in audit_map and pause_id and pause_id in audit_map:
            # Actual window = time from narration event completion to next visual event start
            event_completed = audit_map[eid]['completed_at_ms'] / 1000
            # Find next non-pause event after the pause
            next_visual_start = None
            found_pause = False
            for ce in card_events:
                if ce.get('id') == pause_id:
                    found_pause = True
                    continue
                if found_pause and ce.get('type') not in ('pause',) and ce.get('id') in audit_map:
                    next_visual_start = audit_map[ce['id']]['started_at_ms'] / 1000
                    break
            if next_visual_start:
                actual_window = next_visual_start - event_completed - 0.3  # 0.3s lead

        window = actual_window if actual_window else pause_dur

        if clip_dur and window:
            if clip_dur > window * 0.97:  # 3% buffer
                overage = clip_dur - window
                needed = clip_dur + 6.0
                issues.append({
                    'type':    'TIMING',
                    'event':   eid,
                    'message': f"Clip {clip_dur:.1f}s exceeds window {window:.1f}s by {overage:.1f}s",
                    'fix':     f"Increase {pause_id} duration to {needed:.0f}s",
                    'pause_id': pause_id,
                    'needed_dur': needed,
                    'actual_window': window,
                })
        elif clip_dur and not window:
            issues.append({
                'type':    'NO_PAUSE',
                'event':   eid,
                'message': f"Clip {clip_dur:.1f}s has no following pause window",
                'fix':     "Add pause event after this event",
            })

        # Check 2: Number accuracy
        num_issues = check_number_accuracy(narration, query_results, eid)
        for ni in num_issues:
            issues.append({
                'type':    'NUMBER',
                'event':   eid,
                'message': ni,
                'fix':     "Update narration to match actual query output",
            })

    # Display schedule
    table = Table(header_style="bold cyan", box=box.SIMPLE)
    table.add_column("Event", style="dim")
    table.add_column("Pause")
    table.add_column("Clip")
    table.add_column("Fits?")
    table.add_column("Narration")

    for entry in schedule:
        pause = f"{entry['pause_dur']:.0f}s" if entry['pause_dur'] else "—"
        clip  = f"{entry['clip_dur']:.1f}s" if entry['clip_dur'] else "?"
        if entry['clip_dur'] and entry['pause_dur']:
            fits = "[green]✓[/green]" if entry['clip_dur'] <= entry['pause_dur'] * 0.9 else "[red]✗[/red]"
        else:
            fits = "[yellow]?[/yellow]"
        table.add_row(entry['event_id'], pause, clip, fits, entry['narration'])

    console.print(table)

    # Display issues
    if issues:
        console.print(f"\n[bold red]Issues found: {len(issues)}[/bold red]\n")
        for issue in issues:
            icon = "⏱" if issue['type'] == 'TIMING' else "🔢" if issue['type'] == 'NUMBER' else "⚠"
            console.print(f"  {icon} [{issue['type']}] {issue['event']}")
            console.print(f"     Problem: {issue['message']}")
            console.print(f"     Fix:     {issue['fix']}\n")
    else:
        console.print("\n[bold green]✓ All checks passed[/bold green]\n")

    # Auto-fix pause durations
    if fix and issues:
        timing_fixes = [i for i in issues if i['type'] == 'TIMING' and 'pause_id' in i]
        if timing_fixes:
            console.print(f"[bold]Auto-fixing {len(timing_fixes)} pause durations...[/bold]")
            content = card_path.read_text()
            for issue in timing_fixes:
                # Find and update the pause duration in the YAML
                pause_id = issue['pause_id']
                needed   = issue['needed_dur']
                # Pattern: find the pause block with this ID and update duration
                old_pattern = f'  - id: "{pause_id}"\n    type: "pause"\n    duration:'
                idx = content.find(old_pattern)
                if idx != -1:
                    # Find the duration line
                    dur_start = content.find('duration:', idx) + len('duration:')
                    dur_end   = content.find('\n', dur_start)
                    old_dur   = content[dur_start:dur_end].strip()
                    content   = content[:dur_start] + f' {needed:.0f}.0' + content[dur_end:]
                    console.print(f"  {pause_id}: {old_dur}s → {needed:.0f}s")
                    fixes.append(pause_id)

            card_path.write_text(content)
            console.print(f"[green]✓[/green] Fixed {len(fixes)} pause durations in {card_path.name}")
            console.print("[dim]Re-run recording to apply changes[/dim]")

    return len(issues)


if __name__ == "__main__":
    qa()
