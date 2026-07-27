# Content Brief: COUNT(*) vs COUNT(column): The One-Character Difference That Silently Undercounts Your Data using sql

**Format:** short-video  
**Generated:** 2026-07-26 22:57

---

## Market Analysis
**Demand:** HIGH  
**Why now:** SQL remains the most in-demand data skill in 2024 job postings, and as more non-technical professionals are expected to pull their own data, subtle mistakes like miscounting with NULLs are causing real business errors in dashboards and reports. This is a perennial gotcha that trips up beginners and even intermediate analysts.  
**Target learner:** A complete beginner who has just started writing SELECT statements — could be a marketing coordinator, a junior analyst, or a student who has seen COUNT in a tutorial but has never been warned about how NULLs silently change results.  
**Learner goal:** Confidently choose between COUNT(*) and COUNT(column_name) and understand exactly when and why the numbers will differ so they never silently undercount data.  
**Gap this fills:** Most existing content either buries this in a long SQL fundamentals course or shows it in a dry text blog post with no visual demonstration of the surprise moment. Almost nobody shows a side-by-side live query where the numbers visibly differ and then explains the single reason why. This video needs to deliver that aha moment in under four minutes.  
**Best platform:** YouTube and LinkedIn feed are ideal because the title creates curiosity and mild anxiety — both drive clicks. The short runtime and single-takeaway format match feed-scrolling behavior. LinkedIn is especially strong because data professionals share gotcha content frequently.

---

## Content Hook
> These two SQL queries look almost identical — but one of them is quietly giving you the wrong number. And you would never know unless someone showed you why.

**Core promise:** In under four minutes you will see exactly how one character changes your row count and you will never miscount your data again.

---

## Lesson Structure

### Lesson 1: COUNT(*) vs COUNT(column): See the Silent Undercount in Action
**Duration:** 4 min  
**Objective:** By the end of this lesson the learner will be able to explain why COUNT(*) and COUNT(column_name) return different numbers and choose the correct one for any situation.  
**Key takeaway:** COUNT(*) counts all rows regardless of values. COUNT(column_name) skips NULLs and will silently return a lower number. If you want total rows, always use COUNT(*).

**Scenes (4):**
- Scene 1: **The Surprise: Two Queries, Two Different Numbers** (70s) — sql_viewer
- Scene 2: **The Villain: NULLs Are Invisible to COUNT(column)** (80s) — sql_viewer
- Scene 3: **The Rule: When to Use Which** (50s) — slides
- Scene 4: **Real-World Proof and Wrap-Up** (40s) — sql_viewer
  - Exercise file: `count_demo.sql`

---

## Exercise Files
- `count_demo.sql` (sql) — Contains the CREATE TABLE and INSERT statements to build the sample orders table, plus all four queries shown in the video so the learner can paste them into any SQL environment and reproduce the results. [Lessons [1]]
- `orders_sample.csv` (csv) — A 10-row CSV of the orders table with NULLs in the discount_code column, useful for learners who want to import into a spreadsheet or database tool to experiment on their own. [Lessons [1]]

---

## Production Notes
**Tone:** conversational  
**Pacing:** moderate  
**Complexity:** beginner  
**Hands-on ratio:** 10 percent — the learner primarily watches the demonstration and absorbs the concept, with optional exercise files available for self-guided practice afterward  
**Adapters needed:** sql_viewer, slides

---

*Total scenes: 4*  
*Run `python3 draft.py research/count_vs_count_column_the_one_character_/brief.json` to generate production cards.*