# Content Brief: Why your SQL SUM is wrong

**Format:** micro  
**Generated:** 2026-07-27 14:18

---

## Market Analysis
**Demand:** HIGH  
**Why now:** SQL remains the most in-demand data skill in 2024, yet duplicate-row bugs from bad JOINs silently inflate SUM results every day in production dashboards — and almost nobody teaches this specific gotcha. Data trust and analytics engineering are hot topics, and this is the number-one silent killer of accurate reports.  
**Target learner:** Junior to mid-level data analysts or backend developers who write SQL daily and have been burned by numbers that do not match but could never figure out why  
**Learner goal:** Instantly recognize when a JOIN is duplicating rows and silently inflating their SUM, and know the one-line fix  
**Gap this fills:** Most SQL content covers SUM syntax or GROUP BY basics. Almost nobody isolates the specific moment a JOIN creates a fan-out that doubles your revenue overnight — and shows it visually in a way that makes you feel the horror.  
**Best platform:** TikTok, Instagram Reels, YouTube Shorts — this is a classic gotcha reveal moment that triggers mass relatability among anyone who has ever had a stakeholder say your numbers are wrong

---

## Content Hook
> Your SQL SUM is adding up to $4.2 million. Your actual revenue is $2.1 million. And your query has zero errors.

**Core promise:** You will see exactly how a normal-looking JOIN silently doubles your SUM and know how to catch it every time.

---

## Lesson Structure

### Lesson 1: The JOIN that secretly doubled your revenue
**Duration:** 1.5 min  
**Objective:** By the end of this lesson the learner will be able to identify when a one-to-many JOIN causes SUM to silently inflate and verify it by checking row counts before and after the JOIN.  
**Key takeaway:** If your row count increases after a JOIN, your SUM is silently wrong — always aggregate before you join.

**Scenes (2):**
- Scene 1: **The crime scene** (50s) — sql_viewer
- Scene 2: **The one-line fix** (40s) — sql_viewer

---

## Exercise Files

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** intermediate  
**Hands-on ratio:** 0% — this is a watch-and-absorb micro video designed for social feed consumption  
**Adapters needed:** sql_viewer

---

*Total scenes: 2*  
*Run `python3 draft.py research/why_your_sql_sum_is_wrong/brief.json` to generate production cards.*