#!/usr/bin/env python3
"""
Fix two critical bugs in draft.py:
1. Number extraction: "twenty nine ninety nine" parsed as 128 instead of 29.99
2. Timing: +8 second buffer per pause makes micro lessons 2-3x too long
"""

from pathlib import Path

def main():
    draft_path = Path("draft.py")
    if not draft_path.exists():
        print("ERROR: draft.py not found")
        return

    content = draft_path.read_text()
    original = content
    changes = []

    # FIX 1: Number extraction - add dollar-amount pattern recognition
    old_extractor_start = "def extract_spelled_number_mentions(text: str) -> list:"
    if old_extractor_start not in content:
        print("[WARN] FIX 1: Could not find extract_spelled_number_mentions")
    else:
        # Find the specific section to replace
        old_block = """                    else:
                        whole_tokens = [t for t in run if t != 'and']
                        val = float(_words_to_int(whole_tokens))
                        # Skip trivial single small-number words (too many false
                        # positives, e.g. "two tables", "step one") — only flag
                        # numbers that look like they're reporting a real figure.
                        if val >= 100 or 'point' in run:
                            results.append((' '.join(run), val))
                        i = j"""

        new_block = """                    else:
                        whole_tokens = [t for t in run if t != 'and']
                        val = float(_words_to_int(whole_tokens))
                        # Skip trivial single small-number words (too many false
                        # positives, e.g. "two tables", "step one") — only flag
                        # numbers that look like they're reporting a real figure.
                        if val >= 100:
                            results.append((' '.join(run), val))

                        # DOLLAR-AMOUNT PATTERN: for runs of exactly 4 words
                        # without 'point', try decimal interpretation.
                        # "twenty nine ninety nine" -> 29.99
                        # "eighty nine ninety five" -> 89.95
                        if len(run) == 4 and all(t in _NUMBER_WORDS for t in run):
                            whole_part = _words_to_int(run[:2])
                            dec_part = _words_to_int(run[2:])
                            if dec_part < 100:  # valid cents
                                decimal_val = float(f"{whole_part}.{dec_part:02d}")
                                results.append((' '.join(run), decimal_val))
                        i = j"""

        if old_block in content:
            content = content.replace(old_block, new_block)
            changes.append("FIX 1: Number extraction now recognizes dollar-amount patterns")
        else:
            print("[WARN] FIX 1: Could not find exact block to replace")

    # FIX 2: Reduce pause buffer from +8 to format-aware values in prompt
    old_pause_formula = "Pause duration formula: (word_count / 145 * 60) + 8 seconds, rounded up."
    new_pause_formula = "Pause duration formula: (word_count / 145 * 60) + buffer seconds, rounded up.\n Buffer by format: micro=2s, short=4s, standard=6s."
    if old_pause_formula in content:
        content = content.replace(old_pause_formula, new_pause_formula)
        changes.append("FIX 2: Reduced pause buffer from +8 to format-aware")
    else:
        print("[WARN] FIX 2: Could not find pause formula")

    # FIX 3: Update recompute_pause_durations signature and buffer
    old_recompute_sig = "def recompute_pause_durations(raw_yaml: str) -> str:"
    new_recompute_sig = "def recompute_pause_durations(raw_yaml: str, fmt: str = \"standard\") -> str:"
    if old_recompute_sig in content:
        content = content.replace(old_recompute_sig, new_recompute_sig)
        changes.append("FIX 3a: Added fmt param to recompute_pause_durations")
    else:
        print("[WARN] FIX 3a: Could not find recompute_pause_durations signature")

    old_buffer_line = "            new_duration = round((units / 145 * 60) + 8, 1)"
    new_buffer_block = """            buffer = {"micro": 2.0, "short": 4.0, "short-video": 4.0}.get(fmt.lower(), 6.0)
            new_duration = round((units / 145 * 60) + buffer, 1)"""
    if old_buffer_line in content:
        content = content.replace(old_buffer_line, new_buffer_block)
        changes.append("FIX 3b: Format-aware buffer in recompute_pause_durations")
    else:
        print("[WARN] FIX 3b: Could not find buffer line")

    # FIX 4: Update enforce_duration_cap signature and add per-pause maximums
    old_enforce_sig = "def enforce_duration_cap(raw_yaml: str, max_s: float) -> tuple:"
    new_enforce_sig = "def enforce_duration_cap(raw_yaml: str, max_s: float, fmt: str = \"standard\") -> tuple:"
    if old_enforce_sig in content:
        content = content.replace(old_enforce_sig, new_enforce_sig)
        changes.append("FIX 4a: Added fmt param to enforce_duration_cap")
    else:
        print("[WARN] FIX 4a: Could not find enforce_duration_cap signature")

    # Add per-pause maximums at start of enforce_duration_cap
    old_enforce_start = """    parsed = yaml.safe_load(raw_yaml)
    events = parsed.get("events", [])

    pause_info = []"""
    new_enforce_start = """    parsed = yaml.safe_load(raw_yaml)
    events = parsed.get("events", [])

    # Hard per-pause caps by format (seconds)
    per_pause_max = {
        "micro": 8.0,
        "short": 15.0,
        "short-video": 15.0,
    }.get(fmt.lower(), 25.0)

    # First pass: enforce per-pause maximum
    for e in events:
        if e.get("type") == "pause":
            e["duration"] = min(e.get("duration", 0), per_pause_max)

    pause_info = []"""
    if old_enforce_start in content:
        content = content.replace(old_enforce_start, new_enforce_start)
        changes.append("FIX 4b: Hard per-pause maximums added (micro=8s, short=15s, standard=25s)")
    else:
        print("[WARN] FIX 4b: Could not find enforce_duration_cap start block")

    # FIX 5: Update calls to pass lesson_format
    old_recompute_call = "raw = recompute_pause_durations(raw)"
    new_recompute_call = "raw = recompute_pause_durations(raw, lesson_format)"
    if old_recompute_call in content:
        content = content.replace(old_recompute_call, new_recompute_call)
        changes.append("FIX 5: Pass lesson_format to recompute_pause_durations")
    else:
        print("[WARN] FIX 5: Could not find recompute_pause_durations call")

    old_enforce_call = "raw, cap_message = enforce_duration_cap(raw, max_s)"
    new_enforce_call = "raw, cap_message = enforce_duration_cap(raw, max_s, lesson_format)"
    if old_enforce_call in content:
        content = content.replace(old_enforce_call, new_enforce_call)
        changes.append("FIX 6: Pass lesson_format to enforce_duration_cap")
    else:
        print("[WARN] FIX 6: Could not find enforce_duration_cap call")

    # FIX 7: Update PAUSE SIZING QUICK REFERENCE
    old_quick_ref = """## PAUSE SIZING QUICK REFERENCE
20 words -> 16s pause
40 words -> 24s pause
60 words -> 33s pause
80 words -> 41s pause
100 words -> 49s pause
120 words -> 58s pause
150 words -> 70s pause"""
    new_quick_ref = """## PAUSE SIZING QUICK REFERENCE (by format)
MICRO (2s buffer):  20 words -> 10s | 40 words -> 19s | 60 words -> 27s
SHORT (4s buffer):  20 words -> 12s | 40 words -> 21s | 60 words -> 29s
STANDARD (6s buffer): 20 words -> 14s | 40 words -> 23s | 60 words -> 31s"""
    if old_quick_ref in content:
        content = content.replace(old_quick_ref, new_quick_ref)
        changes.append("FIX 7: Updated pause sizing quick reference")
    else:
        print("[WARN] FIX 7: Could not find pause sizing quick reference")

    if content == original:
        print("No changes applied. File may already be patched or diverged.")
        return

    draft_path.write_text(content)
    print(f"\nApplied {len(changes)} fixes:")
    for c in changes:
        print(f"  [OK] {c}")
    print("\nRun 'git diff draft.py' to review before committing.")

if __name__ == "__main__":
    main()
