# Content Brief: Why your top spenders query missed your actual best customer using sql (written for a complete beginner with no prior knowledge; mostly watching, minimal hands-on requirement)

**Format:** short-video  
**Generated:** 2026-07-18 17:53

---

## Market Analysis
**Demand:** HIGH  
**Why now:** SQL content is exploding on short-form platforms as data literacy becomes a baseline expectation for marketing, product, and business roles. The counterintuitive angle of a simple query being WRONG hooks the growing audience of people learning SQL who assume SELECT and ORDER BY are all they need.  
**Target learner:** A complete beginner who has seen or written a basic SELECT query and thinks sorting by total spend is enough to find the best customer — likely a marketer, junior analyst, or career-switcher scrolling TikTok or Reels for bite-sized SQL knowledge.  
**Learner goal:** Understand that a naive ORDER BY total_spent query can miss a loyal, frequent, recent customer who is actually more valuable — and see the one-line fix that reveals them.  
**Gap this fills:** Most SQL shorts teach syntax in a vacuum. Almost none show a real business scenario where a correct query gives a misleading answer. This video weaponizes surprise — the viewer feels smart, then gets humbled, then gets the fix, all in under two minutes.  
**Best platform:** TikTok, Instagram Reels, and YouTube Shorts — the controversial hot-take format (your query is WRONG) performs extremely well in short-form feeds where pattern interrupts drive watch-through rates.

---

## Content Hook
> This SQL query finds your top spender. It also completely misses your best customer. Let me show you why.

**Core promise:** You will see exactly how a simple ORDER BY total_spent query hides a more valuable customer and learn the one tweak that reveals them.

---

## Lesson Structure

### Lesson 1: The top spender query lied to you — here is the customer it buried
**Duration:** 1.5 min  
**Objective:** By the end of this lesson the learner will be able to explain why sorting customers by total spend alone can hide a more valuable customer and recognize that factoring in recency or frequency changes the answer.  
**Key takeaway:** Sorting by total spend alone is a vanity metric — filtering by recency and sorting by frequency reveals who is actually driving your business right now.

**Scenes (2):**
- Scene 1: **The query that looks right but is not** (50s) — sql_viewer
- Scene 2: **The one-line fix that changes everything** (40s) — sql_viewer

---

## Exercise Files
- `customers_top_spender_trap.sql` (sql) — Contains the CREATE TABLE statement, sample data for five customers, the naive top-spender query, and the improved recency-plus-frequency query so curious viewers can paste it into any free SQL playground and try it themselves. [Lessons [1]]

---

## Production Notes
**Tone:** energetic  
**Pacing:** fast  
**Complexity:** beginner  
**Hands-on ratio:** 5% — this is a watch-and-absorb format with an optional SQL file linked in bio for anyone who wants to try it  
**Adapters needed:** sql_viewer

---

*Total scenes: 2*  
*Run `python3 draft.py research/why_your_top_spenders_query_missed_your_/brief.json` to generate production cards.*