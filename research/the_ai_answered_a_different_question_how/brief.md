# Content Brief: The AI Answered a Different Question: How to Catch a Wrong GROUP BY Level Before You Ship

**Format:** micro  
**Generated:** 2026-07-27 18:56

---

## Market Analysis
**Demand:** HIGH  
**Why now:** Millions of people are now pasting SQL questions into ChatGPT and trusting the output without checking the grain of the result set, leading to silently wrong dashboards and reports that nobody catches until a stakeholder notices the numbers do not add up.  
**Target learner:** A complete beginner who has just started using AI tools to write SQL queries and copies the output straight into a report or dashboard without knowing how to verify the results  
**Learner goal:** Spot when a GROUP BY is at the wrong level by doing a simple row-count sanity check before trusting any AI-generated query  
**Gap this fills:** Existing SQL tutorials teach GROUP BY syntax but never show the real-world failure mode where AI confidently returns a query grouped at the wrong grain — nobody is showing the dramatic before-and-after of how one wrong GROUP BY silently doubles or halves your revenue number  
**Best platform:** TikTok, Instagram Reels, and YouTube Shorts are ideal because the reveal moment — the number is wildly wrong — creates a visual shock that works perfectly in under 90 seconds and is highly shareable among data and analytics communities

---

## Content Hook
> I asked ChatGPT for total revenue by customer and it gave me a number that was 3x too high — and the SQL looked perfectly fine.

**Core promise:** You will learn the one sanity check that instantly reveals when an AI-generated GROUP BY is at the wrong level.

---

## Lesson Structure

### Lesson 1: The Row Count Trick That Catches a Bad GROUP BY in 5 Seconds
**Duration:** 1.5 min  
**Objective:** By the end of this lesson the learner will be able to compare expected row counts against actual row counts to detect a wrong GROUP BY grain in any AI-generated SQL query  
**Key takeaway:** Before you trust any AI-generated GROUP BY query, count the rows in the result and compare that to the number of distinct values in your grouping column — if they do not match, the JOIN duplicated rows and your numbers are wrong.

**Scenes (2):**
- Scene 1: **The AI Gave You the Wrong Answer** (50s) — sql_viewer
- Scene 2: **The 5-Second Row Count Check** (40s) — sql_viewer

---

## Exercise Files

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** beginner  
**Hands-on ratio:** 0% — this is a watch-only micro video designed for passive consumption in a social feed  
**Adapters needed:** sql_viewer

---

*Total scenes: 2*  
*Run `python3 draft.py research/the_ai_answered_a_different_question_how/brief.json` to generate production cards.*