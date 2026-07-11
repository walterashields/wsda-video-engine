# Content Brief: Why LEFT JOIN can quietly turn your matches into NULLs for data analysts using SQL

**Format:** lesson  
**Generated:** 2026-07-10 20:43

---

## Market Analysis
**Demand:** HIGH  
**Why now:** As organizations push data literacy across all business roles, more analysts are writing their own SQL queries without formal database training, and LEFT JOIN misunderstandings are one of the top causes of silently wrong dashboards and reports. The rise of self-serve analytics tools like dbt, Metabase, and Looker makes it critical that analysts understand join behavior at a deeper level.  
**Target learner:** A data analyst with 6-18 months of SQL experience who uses LEFT JOINs regularly but has been burned by unexpected NULLs in query results and does not fully understand why they appear or how to prevent them.  
**Learner goal:** Diagnose and prevent the common scenarios where a LEFT JOIN silently introduces NULLs into matched rows, so they can trust their query output and stop debugging phantom data issues.  
**Gap this fills:** Most existing content explains LEFT JOIN syntax and shows the classic Venn diagram, but almost nobody walks through the subtle scenarios where NULLs appear even when you expect a match — such as duplicate keys causing fan-out that later gets aggregated, filtering the right table in the WHERE clause instead of the ON clause, or joining on columns that contain NULLs themselves. This lesson should focus on the traps, not the syntax.  
**Best platform:** Best suited for LinkedIn Learning or Udemy as a mid-course lesson within a broader SQL for Data Analysts course. It assumes the learner already knows basic JOIN syntax from a prior lesson and sets up a next lesson on defensive JOIN patterns and data validation.

---

## Content Hook
> Your LEFT JOIN matched every row — so why is your report full of NULLs? The answer is not what you think.

**Core promise:** You will be able to identify and fix the three most common ways a LEFT JOIN silently turns your matched data into NULLs.

---

## Lesson Structure

### Lesson 1: How LEFT JOIN Quietly Turns Your Matches into NULLs — and How to Stop It
**Duration:** 8 min  
**Objective:** By the end of this lesson the learner will be able to identify three hidden causes of unexpected NULLs in LEFT JOIN results and apply targeted fixes to each one.  
**Key takeaway:** A LEFT JOIN does not just add NULLs for missing matches — it can silently introduce NULLs through WHERE clause placement, duplicate keys, and NULL join columns, even when your data is technically complete.

**Scenes (5):**
- Scene 1: **The Phantom NULL Problem** (100s) — sql_viewer
  - Exercise file: `phantom_nulls_setup.sql`
- Scene 2: **Trap 1 — WHERE Clause Converts LEFT JOIN to INNER JOIN** (120s) — sql_viewer
  - Exercise file: `where_vs_on_filter.sql`
- Scene 3: **Trap 2 — Duplicate Keys Create Fan-Out and False NULLs** (120s) — sql_viewer
  - Exercise file: `duplicate_key_fanout.sql`
- Scene 4: **Trap 3 — Joining on Columns That Contain NULLs** (80s) — sql_viewer
  - Exercise file: `null_key_join.sql`
- Scene 5: **Your LEFT JOIN Diagnostic Checklist** (60s) — slides

---

## Exercise Files
- `phantom_nulls_setup.sql` (sql) — Creates the orders and customers tables and inserts sample data that triggers all three NULL traps so the learner can follow along from the start of the lesson. [Lessons [1]]
- `where_vs_on_filter.sql` (sql) — Contains two versions of the same LEFT JOIN query — one with the right-table filter in the WHERE clause and one in the ON clause — so the learner can run both and compare results side by side. [Lessons [1]]
- `duplicate_key_fanout.sql` (sql) — Contains queries that demonstrate row fan-out from duplicate keys, including a pre-join duplicate detection query using GROUP BY and HAVING COUNT, so the learner can practice identifying duplicates before joining. [Lessons [1]]
- `null_key_join.sql` (sql) — Contains queries that demonstrate NULL = NULL behavior in join keys, along with COALESCE and IS NOT DISTINCT FROM workarounds the learner can test. [Lessons [1]]
- `sample_data.csv` (csv) — Provides the raw data for learners who want to import into their own database environment rather than running the setup SQL script directly. [Lessons [1]]

---

## Production Notes
**Tone:** conversational  
**Pacing:** deliberate  
**Complexity:** intermediate  
**Hands-on ratio:** 60 percent doing, 40 percent watching  
**Adapters needed:** sql_viewer, slides

---

*Total scenes: 5*  
*Run `python3 draft.py research/why_left_join_can_quietly_turn_your_matc/brief.json` to generate production cards.*