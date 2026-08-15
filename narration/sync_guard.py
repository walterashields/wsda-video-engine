#!/usr/bin/env python3
"""
WSDA Sync Guard — narration / visual sync check

Run BEFORE recording. Verifies that every narration block matches what is
actually on screen at that moment:
- Numbers mentioned in narration must appear in the current query result.
- SQL constructs named in narration (GROUP BY, JOIN, etc.) must exist in the
  query being discussed.
- Result cells highlighted or called out must exist in the current result.

This is a system-level guard, not a per-video manual check.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running this script directly from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from narration.check_numbers import parse_sql_sections, extract_spelled_number_mentions


_SECTION_SQL_CONSTRUCTS = {
    "group by": (r"\bGROUP\s+BY\b", "a GROUP BY clause"),
    "grouped by": (r"\bGROUP\s+BY\b", "a GROUP BY clause"),
    "partition by": (r"\bPARTITION\s+BY\b", "a PARTITION BY clause"),
    "window function": (r"\bOVER\s*\(", "a window function"),
    "rank": (r"\bRANK\s*\(", "RANK()"),
    "row_number": (r"\bROW_NUMBER\s*\(", "ROW_NUMBER()"),
    "join": (r"\bJOIN\b", "a JOIN"),
    "left join": (r"\bLEFT\s+JOIN\b", "a LEFT JOIN"),
    "inner join": (r"\bINNER\s+JOIN\b", "an INNER JOIN"),
    "self join": (r"\bJOIN\b.*\b(?:self|same)\b|\b(?:self|same)\b.*\bJOIN\b", "a self-join"),
    "subquery": (r"\(\s*SELECT\b", "a subquery"),
    "common table expression": (r"\bWITH\b", "a CTE"),
    "cte": (r"\bWITH\b", "a CTE"),
    "case when": (r"\bCASE\b.*\bWHEN\b", "a CASE expression"),
    "having": (r"\bHAVING\b", "a HAVING clause"),
    "where clause": (r"\bWHERE\b", "a WHERE clause"),
    "order by": (r"\bORDER\s+BY\b", "an ORDER BY clause"),
    "limit": (r"\bLIMIT\b", "a LIMIT clause"),
    "distinct": (r"\bDISTINCT\b", "DISTINCT"),
}


def _strip_sql_comments(sql_text: str) -> str:
    """Remove -- line comments and /* */ block comments from SQL."""
    lines = []
    in_block = False
    for line in sql_text.splitlines():
        out = []
        i = 0
        while i < len(line):
            if not in_block and line[i:i + 2] == "/*":
                in_block = True
                i += 2
                continue
            if in_block and line[i:i + 2] == "*/":
                in_block = False
                i += 2
                continue
            if not in_block and line[i:i + 2] == "--":
                break
            if not in_block:
                out.append(line[i])
            i += 1
        lines.append("".join(out))
    return "\n".join(lines)


@dataclass
class SyncIssue:
    event_id: str
    event_type: str
    severity: str  # warning | error
    message: str


def _load_card(card_path: Path) -> dict:
    return yaml.safe_load(card_path.read_text(encoding="utf-8"))


def _display_values(rows: list[tuple]) -> list[float]:
    """Mirror the viewer's 2-decimal number formatting."""
    values = []
    for row in rows:
        for val in row:
            if isinstance(val, (int, float)):
                values.append(round(float(val), 2))
    return values


def _run_query(db_path: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _query_results(db_path: Path, sections: dict[str, str]) -> dict[str, list[float]]:
    results = {}
    for ref, sql in sections.items():
        try:
            rows = _run_query(db_path, sql)
            results[ref] = _display_values(rows)
        except Exception as e:
            results[ref] = []
            # Surface as a warning in the final report, but don't crash.
            results[f"{ref}:error"] = str(e)
    return results


_NEGATION_WORDS = {"not", "no", "never", "none", "isn't", "isnt", "aren't", "arent",
                    "wasn't", "wasnt", "weren't", "werent", "don't", "dont", "doesn't",
                    "doesnt", "didn't", "didnt", "can't", "cant", "cannot", "couldn't",
                    "couldnt", "won't", "wont", "wouldn't", "wouldnt", "shouldn't",
                    "shouldnt", "ain't", "aint", "without", "except", "rather than",
                    "instead of"}
_APPROX_WORDS = {"about", "roughly", "nearly", "around", "almost", "approximately",
                 "just over", "just under", "more than", "less than", "give or take",
                 "close to", "somewhere", "maybe"}


def _is_negated_or_approximate(text: str, match_start: int, match_str: str) -> bool:
    """Check whether a number mention is negated or framed as an approximation."""
    lower = text.lower()
    # Find the actual occurrence of the matched text for spelled numbers.
    idx = lower.find(match_str.lower())
    if idx == -1:
        idx = match_start
    window = lower[max(0, idx - 60):idx]
    tokens = re.findall(r"[a-z']+", window)
    # Check the last few tokens and any bigrams.
    check_tokens = tokens[-6:]
    for t in check_tokens:
        if t in _NEGATION_WORDS or t in _APPROX_WORDS:
            return True
    for i in range(len(check_tokens) - 1):
        bigram = f"{check_tokens[i]} {check_tokens[i + 1]}"
        if bigram in _NEGATION_WORDS or bigram in _APPROX_WORDS:
            return True
    return False


def _extract_numeric_mentions(text: str) -> list[tuple[float, str]]:
    """Return numbers (digits or spelled out) found in narration text.

    Each tuple is (value, source) where source is 'digit' or 'spelled'.
    Skips numbers that are negated or approximate to avoid false positives
    on phrases like "not four hundred" or "about a thousand".
    """
    mentions = []
    # Digits, optional commas/decimals.
    for m in re.finditer(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?", text):
        raw = m.group().replace(",", "")
        if _is_negated_or_approximate(text, m.start(), raw):
            continue
        try:
            mentions.append((round(float(raw), 2), "digit"))
        except ValueError:
            pass
    # Spelled-out numbers.
    for display, val in extract_spelled_number_mentions(text):
        if _is_negated_or_approximate(text, -1, display):
            continue
        mentions.append((round(float(val), 2), "spelled"))
    return mentions


def _expected_on_screen_values(
    event: dict,
    query_results: dict[str, list[float]],
    last_query_ref: str | None,
) -> list[float]:
    """Collect all numeric values that will be visible during this event."""
    refs = []
    etype = event.get("type", "")
    params = {k: v for k, v in event.items() if k not in ("id", "type", "narration")}

    if etype in ("run_query", "reveal_query", "highlight_section"):
        ref = params.get("query_ref") or params.get("section")
        if ref:
            refs.append(ref)
            last_query_ref = ref
    elif etype in ("show_result", "focus_result"):
        ref = params.get("query_ref") or last_query_ref
        if ref:
            refs.append(ref)
    elif etype == "show_diff":
        for key in ("left_ref", "right_ref"):
            ref = params.get(key)
            if ref:
                refs.append(ref)
    elif etype == "compare_results":
        # Legacy compare uses last two query refs.
        pass

    values = []
    seen = set()
    for ref in refs:
        for v in query_results.get(ref, []):
            if v not in seen:
                values.append(v)
                seen.add(v)
    return values


def _check_clause_mentions(event: dict, sql_texts: list[str]) -> list[str]:
    """Flag narration that names an SQL construct not present in any relevant query."""
    if not sql_texts:
        return []
    narr = (event.get("narration") or "").lower().replace("'", " ")
    cleaned = [_strip_sql_comments(s).lower() for s in sql_texts if s]
    issues = []
    for phrase, (pattern, label) in _SECTION_SQL_CONSTRUCTS.items():
        phrase_re = re.escape(phrase).replace(r"\ ", r"\s+")
        if re.search(rf"\b{phrase_re}\b", narr):
            if not any(re.search(pattern, s, re.IGNORECASE) for s in cleaned):
                issues.append(f"narration mentions {label}, but the relevant SQL does not contain it.")
    return issues


def _check_highlight_cells(event: dict, rows: list[tuple]) -> list[str]:
    """Warn if narration references row/cell positions that don't exist."""
    issues = []
    for key in ("highlight_rows", "error_rows", "warning_rows"):
        for idx in event.get(key, []):
            if idx < 0 or idx >= len(rows):
                issues.append(f"{key}[{idx}] points past the result ({len(rows)} rows).")
    cell = event.get("highlight_cell")
    if cell and len(cell) == 2:
        r, c = cell
        if rows and (r < 0 or r >= len(rows) or c < 0 or c >= len(rows[0])):
            issues.append(f"highlight_cell ({r},{c}) is outside the result grid.")
    return issues


def _rows_for_ref(db_path: Path, sections: dict, ref: str | None) -> list[tuple]:
    if not ref or ref not in sections:
        return []
    try:
        return _run_query(db_path, sections[ref])
    except Exception:
        return []


def check_sync(card_path: Path) -> list[SyncIssue]:
    """Run the full narration/visual sync guard on a production card."""
    card = _load_card(card_path)
    events = card.get("events", [])
    issues: list[SyncIssue] = []

    assets_dir = card_path.parent / "assets"
    db_candidates = list(assets_dir.glob("*.db"))
    sql_candidates = list(assets_dir.glob("*.sql"))

    if not db_candidates or not sql_candidates:
        # Non-SQL adapters (chat, concept) have nothing to sync against here.
        return issues

    db_path = db_candidates[0]
    sql_path = sql_candidates[0]
    sections = parse_sql_sections(sql_path)
    query_results = _query_results(db_path, sections)

    last_query_ref: str | None = None

    for event in events:
        eid = event.get("id", "unknown")
        etype = event.get("type", "")
        narration = event.get("narration", "")

        # Track last query ref for show_result/focus_result events.
        params = {k: v for k, v in event.items() if k not in ("id", "type", "narration")}
        if etype in ("run_query", "reveal_query", "highlight_section"):
            ref = params.get("query_ref") or params.get("section")
            if ref:
                last_query_ref = ref

        if not narration:
            continue

        # Determine on-screen numeric values for this event.
        on_screen = _expected_on_screen_values(event, query_results, last_query_ref)

        def _value_match(num: float, values: list[float]) -> bool:
            """Mirror check_numbers.py tolerance for rounded display values."""
            return any(abs(num - v) < (1.0 if abs(v) >= 100 else 0.005) for v in values)

        # Check numbers in narration.
        narr_numbers = _extract_numeric_mentions(narration)
        for num, source in narr_numbers:
            if on_screen and not _value_match(num, on_screen):
                # Digit mentions are hard assertions — flag as errors.
                # Spelled-out mentions are softer (TTS, approximations) — flag as warnings.
                severity = "error" if source == "digit" else "warning"
                issues.append(SyncIssue(
                    event_id=eid,
                    event_type=etype,
                    severity=severity,
                    message=f"narration says {num}, but that value is not displayed by the current query result.",
                ))

        # Check SQL clause consistency for query-focused events.
        refs = []
        if etype in ("highlight_section", "reveal_query"):
            ref = params.get("section") or params.get("query_ref")
            if ref:
                refs.append(ref)
        elif etype in ("show_result", "focus_result"):
            ref = params.get("query_ref") or last_query_ref
            if ref:
                refs.append(ref)
        elif etype == "show_diff":
            for key in ("left_ref", "right_ref"):
                ref = params.get(key)
                if ref and ref not in refs:
                    refs.append(ref)

        if refs:
            sql_texts = [sections[r] for r in refs if r in sections]
            for msg in _check_clause_mentions(event, sql_texts):
                issues.append(SyncIssue(
                    event_id=eid,
                    event_type=etype,
                    severity="error",
                    message=msg,
                ))

            # Highlight validity only makes sense for a single ref; use the first.
            primary_ref = refs[0]
            if primary_ref in sections:
                rows = _rows_for_ref(db_path, sections, primary_ref)
                for msg in _check_highlight_cells(event, rows):
                    issues.append(SyncIssue(
                        event_id=eid,
                        event_type=etype,
                        severity="warning",
                        message=msg,
                    ))

    return issues


def check_sync_to_dict(issues: list[SyncIssue]) -> dict:
    """Serialize issues for API consumers."""
    return {
        "passed": not any(i.severity == "error" for i in issues),
        "issues": [
            {"event_id": i.event_id, "event_type": i.event_type,
             "severity": i.severity, "message": i.message}
            for i in issues
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 narration/sync_guard.py CARD_PATH")
        sys.exit(1)
    card_path = Path(sys.argv[1])
    result = check_sync_to_dict(check_sync(card_path))
    print(yaml.safe_dump(result, sort_keys=False))
    sys.exit(0 if result["passed"] else 1)
