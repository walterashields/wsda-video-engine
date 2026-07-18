# Content Brief: Why your GROUP BY total doesn't match the dashboard for data analyst

**Format:** course  
**Generated:** 2026-07-15 22:06

---

## Market Analysis
**Demand:** HIGH  
**Why now:** Companies are hiring record numbers of junior data analysts who are expected to validate dashboard numbers on day one, and GROUP BY mismatches are the single most common source of panic and lost credibility in the first 90 days on the job.  
**Target learner:** A complete beginner who has just started learning SQL or recently landed their first data analyst role and is trying to reconcile query results with existing dashboards in tools like Tableau, Looker, or Power BI.  
**Learner goal:** Confidently diagnose and fix the five most common reasons a GROUP BY query returns a different total than the dashboard, and explain the discrepancy to a stakeholder without sounding unsure.  
**Gap this fills:** Existing SQL courses teach GROUP BY syntax in isolation. Almost none address the real-world scenario where the learner runs a correct query but gets a number that does not match the dashboard — leaving beginners to assume they are wrong. This course bridges the gap between textbook SQL and workplace reality.  
**Best platform:** LinkedIn Learning and Udemy are ideal because learners on these platforms are actively upskilling for analyst roles, expect downloadable exercise files they can run locally, and value a certificate that signals practical SQL debugging ability to hiring managers.

---

## Content Hook
> You wrote a perfectly valid GROUP BY query, the syntax is clean, it runs without errors — and the total is off by thousands. Before you decide SQL is broken, let me show you the five hidden reasons this happens to every analyst.

**Core promise:** You will be able to systematically diagnose why your GROUP BY total does not match a dashboard number and fix or explain the discrepancy every time.

---

## Lesson Structure

### Lesson 1: The Mismatch Moment — Setting Up the Problem You Will Solve
**Duration:** 5 min  
**Objective:** By the end of this lesson the learner will be able to describe the common scenario where a GROUP BY total diverges from a dashboard total and identify the five root-cause categories they will investigate throughout the course.  
**Key takeaway:** A syntactically correct GROUP BY query can still return wrong totals — the problem is almost never the SQL engine, it is a mismatch between what your query includes and what the dashboard includes.

**Scenes (3):**
- Scene 1: **The Slack Message Every Analyst Dreads** (90s) — slides
- Scene 2: **Loading the Sample Data and Seeing the Gap** (120s) — sql_viewer
  - Exercise file: `sample_orders.db`
- Scene 3: **Quick Orientation — Course Roadmap** (90s) — slides

### Lesson 2: Duplicate Rows — The Silent Inflator
**Duration:** 6 min  
**Objective:** By the end of this lesson the learner will be able to detect duplicate rows caused by JOINs or dirty data and use DISTINCT or proper join logic to eliminate them before aggregating.  
**Key takeaway:** Always check for duplicate rows before aggregating — a one-to-many JOIN is the most common reason your SUM is too high.

**Scenes (3):**
- Scene 1: **How a JOIN Creates Duplicates** (120s) — sql_viewer
  - Exercise file: `lesson2_duplicates.sql`
- Scene 2: **Fix 1 — Using DISTINCT and Subqueries** (120s) — sql_viewer
  - Exercise file: `lesson2_duplicates.sql`
- Scene 3: **Quick Check — Counting Before Summing** (120s) — sql_viewer
  - Exercise file: `lesson2_duplicates.sql`

### Lesson 3: Hidden Filters, NULLs, and Status Codes — What the Dashboard Excludes
**Duration:** 6 min  
**Objective:** By the end of this lesson the learner will be able to identify WHERE clause filters, NULL exclusions, and status-code logic that dashboards apply silently, and replicate them in their own queries.  
**Key takeaway:** Before comparing your query to a dashboard, replicate every filter the dashboard applies — including status codes, NULL handling, and default selections you cannot see at first glance.

**Scenes (3):**
- Scene 1: **The Dashboard Has a WHERE Clause You Cannot See** (120s) — browser
  - Exercise file: `lesson3_filters.sql`
- Scene 2: **NULLs That Vanish from Your Total** (100s) — sql_viewer
  - Exercise file: `lesson3_filters.sql`
- Scene 3: **Status Codes — Completed vs Fulfilled vs Shipped** (140s) — sql_viewer
  - Exercise file: `lesson3_filters.sql`

### Lesson 4: Date Ranges and Timezone Traps — When Tuesday is Still Monday
**Duration:** 5 min  
**Objective:** By the end of this lesson the learner will be able to identify date-range boundary errors and timezone conversion issues that cause GROUP BY totals to shift between days, weeks, or months.  
**Key takeaway:** Always use the half-open interval pattern for date ranges and confirm whether your database stores UTC or local time before grouping by day, week, or month.

**Scenes (3):**
- Scene 1: **Off-by-One Day — The Boundary Problem** (100s) — sql_viewer
  - Exercise file: `lesson4_dates.sql`
- Scene 2: **UTC vs Local Time — Orders That Jump Between Days** (100s) — sql_viewer
  - Exercise file: `lesson4_dates.sql`
- Scene 3: **Quick Reference — Date Pattern Cheat Sheet** (100s) — slides
  - Exercise file: `date_cheatsheet.pdf`

### Lesson 5: Metric Definitions and the Capstone Debugging Exercise
**Duration:** 6 min  
**Objective:** By the end of this lesson the learner will be able to identify when a metric definition difference is the root cause of a mismatch and apply a systematic five-step checklist to debug any GROUP BY versus dashboard discrepancy from scratch.  
**Key takeaway:** When your number does not match, work through the five-step checklist in order — duplicates, filters, NULLs, dates, metric definition — and you will find the cause every time.

**Scenes (3):**
- Scene 1: **Revenue vs Gross Revenue vs Net Revenue — Same Word, Different Numbers** (100s) — sql_viewer
  - Exercise file: `lesson5_capstone.sql`
- Scene 2: **The Five-Step Debugging Checklist** (60s) — slides
  - Exercise file: `debugging_checklist.pdf`
- Scene 3: **Hands-On Capstone — Find and Fix All Five Problems** (200s) — sql_viewer
  - Exercise file: `lesson5_capstone.sql`

---

## Exercise Files
- `sample_orders.db` (db) — SQLite database containing orders, payments, and customers tables with intentional data quality issues for the learner to discover and fix throughout the course. [Lessons [1, 2, 3, 4, 5]]
- `dashboard_screenshot.pdf` (pdf) — Static screenshot of a mock dashboard showing regional revenue totals that the learner must match by correcting their SQL queries. [Lessons [1, 5]]
- `lesson2_duplicates.sql` (sql) — SQL file with starter queries that demonstrate duplicate rows from JOINs, diagnostic count queries, and corrected versions using subqueries and DISTINCT. [Lessons [2]]
- `lesson3_filters.sql` (sql) — SQL file with queries that show the impact of missing WHERE clauses, NULL grouping, and status code filtering on GROUP BY totals. [Lessons [3]]
- `lesson4_dates.sql` (sql) — SQL file with date boundary comparison queries and timezone conversion examples that show how totals shift between months. [Lessons [4]]
- `date_cheatsheet.pdf` (pdf) — One-page reference showing the half-open interval pattern, timezone conversion template, and a three-question date diagnostic checklist. [Lessons [4]]
- `lesson5_capstone.sql` (sql) — Capstone exercise file containing a broken query with all five root-cause issues embedded. The learner uses the checklist to find and fix each one until the total matches the dashboard. [Lessons [5]]
- `capstone_solution.sql` (sql) — Fully corrected version of the capstone query with inline comments explaining each fix, for the learner to check their work. [Lessons [5]]
- `debugging_checklist.pdf` (pdf) — Printable five-step debugging checklist the learner can reference on the job whenever a GROUP BY total does not match a dashboard. [Lessons [5]]

---

## Production Notes
**Tone:** conversational  
**Pacing:** moderate  
**Complexity:** beginner  
**Hands-on ratio:** 45% doing, 55% watching — weighted toward watching in early lessons and toward doing in lessons 4 and 5  
**Adapters needed:** sql_viewer, browser, slides

---

*Total scenes: 15*  
*Run `python3 draft.py research/why_your_group_by_total_doesn_t_match_th/brief.json` to generate production cards.*