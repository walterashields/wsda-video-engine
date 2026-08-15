# Lesson Content Standard

Why this document exists: every fix pass on this system so far has been about
*delivery* — highlight accuracy, click/narration sequencing, audio synthesis,
pacing. None of that guarantees the lesson is actually teaching anything. A
perfectly synced, perfectly paced video of someone clicking through a UI with
no reasoning attached is a screen recording, not instruction. This standard
defines what makes the underlying content good, independent of how well it's
delivered, and applies to every lesson this system produces: single videos,
tutorials, and full courses, across every content adapter (the SQL/AI
pipeline driven by `generator/prompts.py`, and the Metabase automation path
driven by hand-authored `lesson_script.yml` files like this one).

Delivery quality and content quality are checked separately and neither
substitutes for the other. A lesson can pass every timing/sync check in
`verify.py` and `narration/qa.py` and still fail this standard.

## The four rules

### 1. Open with the outcome, before any action starts

State what the learner will be able to do by the end, in one sentence,
before the first click, query, or highlight. Not "today we'll look at
Metabase" — a concrete capability: "by the end of this you'll be able to
turn a raw orders table into a saved, shareable answer to a real business
question." The learner should know what they're building toward before
they watch the first step, not infer it retroactively from a summary at
the end.

This is a hard requirement, not a nice-to-have: a lesson with no outcome
statement fails this standard regardless of how good the rest of the
narration is.

### 2. Teach the reasoning, not just the mechanics

"Click New Question" is not a teaching moment. It's a mechanical fact
about where a button is. "We start here because every analysis in
Metabase begins with a question" is a teaching moment — it tells the
learner *why this step exists*, which is the part that transfers to the
next tool they use, long after they've forgotten which button was where.

Every narrated step should answer "why does this step exist" before or
alongside "what is happening on screen." A useful test: if you deleted the
mechanical description ("click X", "select Y") and only the reasoning
sentence remained, would the learner still understand why this step
matters? If the reasoning sentence doesn't exist, the step fails this
rule.

This applies to every step with narration, not just the conceptually
"big" ones. A short "here's what I'm doing" line and a longer "why this
matters" line (see `AGENTS.md`'s two-tier narration convention) are both
still required to carry *some* reasoning — a one-sentence action line can
carry a one-clause reason ("we filter here first, since fixing the range
after aggregating would change the totals") without needing the full
paragraph treatment.

### 3. Connect to a real scenario, not an arbitrary demo action

The learner should never be filtering, joining, or aggregating data for
its own sake. Every action should trace back to a concrete problem a real
person would actually have — a decision they're trying to make, a number
someone is going to ask them for, a mistake that would cost something if
it went unnoticed. This is the same instinct behind the NovaBridge
fictional-company framing already used in the SQL/AI course pipeline
(`generator/prompts.py`'s "named protagonist with a concrete business
problem and real stakes") and enforced there by `verify.py`'s
`check_engagement` (flags generic titles, missing stakes, and dry,
lecture-style openings). Every content adapter needs the same instinct
applied to it, even where nothing currently checks for it automatically
(see "Enforcement" below).

The specifics of a demo action should be motivated by the scenario, not
arbitrary. If a lesson filters orders between $50 and $1,000, there
should be an in-narration reason those specific numbers matter to the
scenario — not just "let's filter between fifty and a thousand" with no
stated reason those particular bounds were chosen over any other range.

### 4. Assume zero prior familiarity with the specific tool

The learner may already understand the underlying concept — filtering,
aggregating, joining — from something else entirely (a spreadsheet, a
different BI tool, a stats class). That prior knowledge does not transfer
to knowing where a given concept lives in *this* tool's UI, what it's
called here, or what this tool does differently. No step should be
narrated as if its existence or location in the interface is self-evident
just because the underlying concept is familiar. Name what's on screen in
plain language before assuming the learner recognizes it.

## Enforcement

- **SQL/AI pipeline** (`generator/prompts.py` → production cards →
  `verify.py`): rules 1 and 3 are partially automated today via
  `verify.py`'s `check_engagement` (flags generic titles, missing
  `stakes` on the title card, and dry openings). Rules 2 and 4 are not
  automated — they're checked by a human read of the narration against
  this document.
- **Metabase automation path** (hand-authored `lesson_script.yml` →
  `automation/metabase_driver.py`): nothing here is automated yet. Every
  `lesson_script.yml` narration line should be checked against this
  standard by hand before recording, the same way `courses/metabase_poc/
  video_1_1/lesson_script.yml` was rewritten against it.
- **Any future content adapter** added to this system inherits this
  standard by default; if it doesn't fit one of the four rules as
  written, that's a sign the adapter's format needs its own explicit
  carve-out documented here, not that the rule gets silently skipped.

## Authoring checklist

Before recording, for every lesson:

- [ ] Is there a one-sentence outcome statement before the first action?
- [ ] For every narrated step, is there a reason stated for *why* this
      step happens, not just *what* is being clicked/typed/shown?
- [ ] Does the lesson trace back to one concrete, stated scenario with
      real stakes, and are specific values (filter ranges, thresholds,
      table choices) motivated by that scenario rather than arbitrary?
- [ ] Does any line assume the learner already knows this specific tool's
      UI, naming, or layout?
