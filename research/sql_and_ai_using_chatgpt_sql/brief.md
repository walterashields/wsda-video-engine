# Content Brief: SQL and AI using chatgpt, sql

**Format:** short-video  
**Generated:** 2026-07-06 22:40

---

## Market Analysis
**Demand:** HIGH  
**Why now:** Millions of data professionals and analysts are actively experimenting with ChatGPT to accelerate their SQL workflows, but most are writing vague prompts and getting mediocre results. The intersection of generative AI and SQL is the single fastest-growing skill search term on LinkedIn and YouTube in 2024-2025.  
**Target learner:** Data analysts, junior developers, and business professionals who already know basic SQL SELECT statements but want to use ChatGPT to write, debug, and optimize queries 5x faster than doing it manually.  
**Learner goal:** Use a proven prompt framework to get ChatGPT to generate accurate, production-ready SQL queries on the first try instead of going back and forth with vague prompts.  
**Gap this fills:** Most existing videos either show trivially simple examples like SELECT * FROM users or spend 20 minutes on setup. None give a repeatable prompt template the viewer can copy and use immediately with their own database schema. This video delivers a concrete framework in under 5 minutes.  
**Best platform:** YouTube Shorts and LinkedIn feed are ideal because the target audience — data professionals scrolling during work breaks — responds strongly to quick productivity hacks they can apply within minutes of watching.

---

## Content Hook
> Stop asking ChatGPT to write your SQL like this — you are giving it zero context and wondering why the queries are wrong. Here is the 3-line prompt framework that gets production-ready SQL on the first try.

**Core promise:** You will learn a copy-paste prompt template that turns ChatGPT into a SQL expert that understands your exact database schema.

---

## Lesson Structure

### Lesson 1: The 3-Line Prompt Framework for Perfect SQL from ChatGPT
**Duration:** 5 min  
**Objective:** By the end of this lesson the learner will be able to write a structured 3-part prompt — schema context, business question, and output constraints — that makes ChatGPT generate accurate, runnable SQL queries for any database.  
**Key takeaway:** Always give ChatGPT your actual CREATE TABLE schema, a clear business question, and explicit constraints — this 3-line framework gets accurate SQL on the first prompt every time.

**Scenes (5):**
- Scene 1: **The Bad Prompt vs Good Prompt** (60s) — browser
- Scene 2: **The 3-Line Framework Breakdown** (90s) — browser
  - Exercise file: `prompt_template.txt`
- Scene 3: **Live Demo — Revenue by Customer Segment** (90s) — sql_viewer
  - Exercise file: `sample_database.db`
- Scene 4: **Bonus — Debug and Optimize with One Extra Line** (50s) — browser
  - Exercise file: `prompt_template.txt`
- Scene 5: **Takeaway and Call to Action** (30s) — slides

---

## Exercise Files
- `prompt_template.txt` (txt) — A ready-to-use prompt template with placeholders for schema, business question, and constraints that the learner can copy-paste into ChatGPT and customize for their own database. [Lessons [1]]
- `sample_database.db` (db) — A SQLite database with orders, customers, and products tables pre-loaded with realistic sample data so the learner can run the generated SQL queries locally and verify results. [Lessons [1]]
- `sample_schema.sql` (sql) — The CREATE TABLE statements for all three tables in the sample database, formatted and ready to paste into the prompt template as the schema context line. [Lessons [1]]

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** beginner  
**Hands-on ratio:** 60%  
**Adapters needed:** browser, sql_viewer, slides

---

*Total scenes: 5*  
*Run `python3 draft.py research/sql_and_ai_using_chatgpt_sql/brief.json` to generate production cards.*