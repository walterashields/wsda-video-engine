# Content Brief: SQL and AI

**Format:** short-video  
**Generated:** 2026-07-06 23:21

---

## Market Analysis
**Demand:** HIGH  
**Why now:** Generative AI tools like ChatGPT and GitHub Copilot are fundamentally changing how people write and optimize SQL, and professionals who combine SQL fluency with AI prompting skills are outperforming peers who rely on either skill alone. Companies are actively seeking analysts and engineers who can leverage AI to accelerate data workflows.  
**Target learner:** Data analysts, junior data engineers, and business intelligence professionals who already know basic SQL and want to use AI tools to write queries faster, debug errors, and optimize performance without blindly trusting AI output.  
**Learner goal:** Use an AI assistant to generate, explain, and optimize a real SQL query against a sample database, while knowing exactly how to verify the output is correct.  
**Gap this fills:** Most existing content either shows trivial AI-generated queries with no verification step, or focuses on AI hype without hands-on SQL. This video bridges the gap by showing a realistic workflow: prompt AI, get a query, then critically validate it against actual data — the skill that separates professionals from hobbyists.  
**Best platform:** YouTube and LinkedIn feed are ideal because the topic intersects two massive search trends — SQL tutorials and AI productivity — and the under-5-minute format matches the snackable learning behavior of working professionals scrolling during breaks or commutes.

---

## Content Hook
> I asked ChatGPT to write a SQL query that looked perfect — but it returned the wrong answer. Here is the 30-second check that catches AI mistakes every time.

**Core promise:** You will learn a repeatable 3-step workflow to use AI to generate SQL queries and then verify them so you never ship wrong data.

---

## Lesson Structure

### Lesson 1: The 3-Step AI-to-SQL Workflow That Prevents Wrong Answers
**Duration:** 5 min  
**Objective:** By the end of this lesson the learner will be able to prompt an AI tool to generate a SQL query, identify where AI-generated SQL commonly fails, and apply a quick validation technique to confirm correctness.  
**Key takeaway:** Never trust AI-generated SQL without a micro-query spot-check and an assumption review — these two steps take 60 seconds and prevent costly data errors.

**Scenes (5):**
- Scene 1: **The AI Trap** (60s) — browser
- Scene 2: **Step 1 — Prompt with Schema Context** (80s) — browser
  - Exercise file: `schema_context_prompt.txt`
- Scene 3: **Step 2 — Run and Spot-Check with a Micro-Query** (90s) — sql_viewer
  - Exercise file: `sample_store.db`
- Scene 4: **Step 3 — Ask AI to Explain Its Own Query** (60s) — browser
- Scene 5: **The 3-Step Recap and Call to Action** (30s) — slides

---

## Exercise Files
- `sample_store.db` (db) — A SQLite database with customers, orders, and order_items tables pre-loaded with realistic sample data so the learner can run the AI-generated queries and practice the micro-query verification technique themselves. [Lessons [1]]
- `schema_context_prompt.txt` (txt) — A ready-to-paste text file containing the CREATE TABLE statements for the sample database and a template prompt the learner can customize when asking AI to generate SQL for their own projects. [Lessons [1]]
- `ai_sql_verification_queries.sql` (sql) — Contains the AI-generated top-5 revenue query and the micro-query used for verification, with comments explaining each step so the learner can study and modify them. [Lessons [1]]

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** intermediate  
**Hands-on ratio:** 60% — the majority of the video shows real queries being typed, run, and validated rather than slides or talking head  
**Adapters needed:** browser, sql_viewer, slides

---

*Total scenes: 5*  
*Run `python3 draft.py research/sql_and_ai/brief.json` to generate production cards.*