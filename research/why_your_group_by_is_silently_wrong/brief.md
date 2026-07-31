# Content Brief: Why your GROUP BY is silently wrong

**Format:** micro  
**Generated:** 2026-07-28 10:48

---

## Market Analysis
**Demand:** HIGH  
**Why now:** SQL remains the most in-demand data skill in 2024-2025 job postings, yet GROUP BY misuse is the single most common silent-failure bug in analytics queries — and AI code assistants like Copilot and ChatGPT generate this exact mistake constantly, making it more urgent than ever.  
**Target learner:** Junior to mid-level data analysts, backend developers, or self-taught SQL users who write GROUP BY queries daily but have never been burned (or do not realize they have been burned) by non-aggregated column selection.  
**Learner goal:** Recognize that selecting a non-aggregated column in a GROUP BY query can return arbitrary, misleading data — and never trust that pattern again.  
**Gap this fills:** Most SQL content explains GROUP BY syntax correctly but never shows the horrifying moment where the query runs without errors yet returns the WRONG answer. Nobody dramatizes the silent failure. This video makes you feel the betrayal.  
**Best platform:** TikTok, Instagram Reels, YouTube Shorts — the gotcha reveal format is perfect for short-form; the before/after of a query returning wrong data is visually punchy and shareable among data teams.

---

## Content Hook
> This query returns the wrong answer and your database will never tell you.

**Core promise:** You will see exactly how GROUP BY silently picks a random row and lies to your face.

---

## Lesson Structure

### Lesson 1: The GROUP BY lie your database keeps from you
**Duration:** 1.5 min  
**Objective:** By the end of this lesson the learner will be able to identify when a SELECT column is not functionally dependent on the GROUP BY clause and understand that the returned value is arbitrary and unreliable.  
**Key takeaway:** Any column in your SELECT that is not aggregated and not in your GROUP BY clause can return an arbitrary value from any row in the group — and most databases will not warn you.

**Scenes (2):**
- Scene 1: **The query that looks fine** (40s) — sql_viewer
- Scene 2: **The proof and the fix** (50s) — sql_viewer
  - Exercise file: `group_by_trap.sql`

---

## Exercise Files
- `group_by_trap.sql` (sql) — Contains the CREATE TABLE and INSERT statements for the orders table, the broken GROUP BY query, a proof query showing the mismatch, and the corrected version using a window function — so the learner can run all three and see the lie for themselves. [Lessons [1]]

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** intermediate  
**Hands-on ratio:** 20% — this is a watch-and-absorb video but the exercise file lets motivated viewers replicate it immediately  
**Adapters needed:** sql_viewer

---

*Total scenes: 2*  
*Run `python3 draft.py research/why_your_group_by_is_silently_wrong/brief.json` to generate production cards.*