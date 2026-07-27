# Content Brief: How to Paste Your Schema So ChatGPT Stops Inventing Column Names

**Format:** micro  
**Generated:** 2026-07-27 11:35

---

## Market Analysis
**Demand:** HIGH  
**Why now:** Millions of non-technical workers are pasting database questions into ChatGPT daily and getting back confident SQL with completely hallucinated column names like 'customer_id' when their table actually uses 'cust_no'. This is the number one reason beginners lose trust in AI-generated SQL and give up.  
**Target learner:** A non-technical office worker or analyst who has access to a database, has tried asking ChatGPT to write SQL for them, and got burned by made-up column names they had to debug  
**Learner goal:** Copy their real database schema and paste it into ChatGPT so every AI-generated query uses the actual column names from their database  
**Gap this fills:** Most prompt-engineering content is abstract and talks about 'providing context' without showing the exact 3-second copy-paste move that fixes hallucinated columns. Nobody shows the hilarious before-and-after of ChatGPT confidently using a column that does not exist.  
**Best platform:** TikTok, Instagram Reels, YouTube Shorts — this is a single visual gag (fake column names) followed by a satisfying one-move fix, perfect for short-form dopamine content where the payoff lands in under 90 seconds

---

## Content Hook
> ChatGPT just wrote you a perfect SQL query — except the column 'customer_email' does not exist anywhere in your database.

**Core promise:** One paste fixes hallucinated column names forever.

---

## Lesson Structure

### Lesson 1: One Paste to Kill Fake Column Names
**Duration:** 1.5 min  
**Objective:** By the end of this lesson the learner will be able to copy a CREATE TABLE statement from their database tool and paste it into a ChatGPT prompt so the AI uses real column names instead of inventing them.  
**Key takeaway:** Always paste your real CREATE TABLE statement into ChatGPT before asking for SQL — it cannot hallucinate column names if you hand it the real ones.

**Scenes (2):**
- Scene 1: **The Hallucination Horror Show** (35s) — browser
- Scene 2: **The One-Paste Fix** (55s) — browser
  - Exercise file: `sample_schema.sql`

---

## Exercise Files
- `sample_schema.sql` (sql) — A realistic ugly-but-real CREATE TABLE statement with abbreviated column names that the learner can paste into ChatGPT to practice the technique themselves [Lessons [1]]

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** beginner  
**Hands-on ratio:** 10% — viewer mostly watches the demo and laughs at the hallucinated names, then optionally tries it with the sample schema file  
**Adapters needed:** browser, sql_viewer

---

*Total scenes: 2*  
*Run `python3 draft.py research/how_to_paste_your_schema_so_chatgpt_stop/brief.json` to generate production cards.*