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

As of the second pass on this document, the five rules below aren't a
generic best-practice guess — rules 1 through 4 are validated, and rule 5
is directly motivated, against the transcripts of Walter's own LinkedIn
Learning flagship course, *SQL Essential Training* (500K+ learners, 4.8
stars). See "Grounded in SQL Essential Training" below for the specific
patterns pulled from those transcripts.

## The five rules

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
lecture-style openings) — and it's also, independently, exactly how
Walter's own flagship course frames nearly every lesson (see below: every
query in *SQL Essential Training* answers a named "management" request
against the fictional WSDA Music, not an abstract exercise). Every content
adapter needs the same instinct applied to it, even where nothing
currently checks for it automatically (see "Enforcement" below).

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

### 5. Narration must never reference what isn't visible and highlighted

If the narration says a name, a number, or a column, the screen shows it,
highlighted, for as long as it's being talked about. This is a hard
requirement, same tier as rule 1, not a delivery nicety — it's a content
failure when violated, not a polish gap, because a viewer who can't see
the thing being described isn't learning it, they're being told about it.

Two specific, previously-real gaps this rule closes:

- **Values being typed or entered** (filter numbers, search terms, any
  typed input) must be visible on screen, highlighted if possible, for as
  long as narration discusses them — not just the click that opens the
  control they'll eventually go into. Narrating "we'll filter between
  fifty and a thousand dollars" while the screen shows an empty, unopened
  filter button is a violation: the learner hears two numbers and sees
  neither.
- **Columns, fields, or structures named in narration** must be visible
  and highlighted at the moment they're named. Narrating a list of column
  names while the screen shows a generic, unrelated highlight (or no
  highlight at all) is a violation, even if those columns are technically
  present somewhere on screen.

This is a software-agnostic authoring rule, not a Metabase-specific fix:
the same gap will recur on any platform this system automates next (SQL
Server, Snowflake, whatever comes after). `automation/metabase_driver.py`
implements two general mechanisms in support of it — `pre_actions` on a
highlight event (run small click/fill steps to reveal data before it's
narrated, not after) and `highlight_targets` (plural, for narration that
names several things in the same breath) — but the rule itself is about
the narration script, not the driver: an author writing for a brand-new
platform with neither mechanism yet built for it still fails this rule by
writing narration that names something off-screen.

## Grounded in SQL Essential Training

Walter's transcripts (`Transcripts/`, LinkedIn Learning's *SQL Essential
Training*) show a consistent, repeated structure across ~500K learners of
real, working instruction. The patterns below are paraphrased from that
material, not quoted verbatim, and are the concrete template rules 1
through 4 are checked against — not just abstract principles this system
invented on its own.

**Five video roles, each with a distinct job.** The course's file naming
reveals a consistent per-chapter shape: a chapter-opener video, several
lesson videos, and a closing "challenge" video where the learner applies
the chapter's skill independently against a new request, with the whole
course bookended by a welcome video and a final wrap-up. A lesson system
that only ever produces one flat video type (which is what
`metabase_poc/video_1_1` currently is) is missing the "challenge" role
entirely — see "Where metabase_poc still falls short" below.

**The chapter-opener pattern.** Every chapter-opener video in the
transcripts follows the same shape, in this order: (1) a personal or
striking hook — sometimes a story, sometimes a strong scenario; (2) an
explicit recap of what the learner can already do, stated relative to
what's coming ("so far we've written a lot of queries... but we've only
been getting data from one table at a time"); (3) a concrete request from
the course's recurring fictional company, WSDA Music, that the learner's
current skills can't yet satisfy; (4) the new tool named and defined in
one plain sentence ("a join is a command that connects the fields from
two or more tables"); (5) a short transition into the first lesson. This
is rule 1's outcome-statement requirement in its proven form: the outcome
isn't stated in isolation, it's stated as the gap between what the
learner can already do and the new request they can't yet satisfy.

**The lesson-video loop.** Individual lesson videos follow a tighter,
repeated loop: open on a specific, named stakeholder question ("management
has asked how many customers purchased two songs at 99 cents each");
briefly show why the learner's current tools would require something
tedious or error-prone (manually counting rows); introduce the new
clause/keyword and build the query piece by piece, narrating each field
or table by its exact on-screen name as it's added, not a summary
afterward; run it; and then state the actual resulting count or value out
loud, tied to a specific visible column ("we have 111 rows that satisfy
our new criteria" / "if we take a look at our results and look at the
BillingCity, we see all seven of these records are now pointing to
Brussels"). This is rule 5's data-capture rule already in practice: the
narration doesn't just say a number exists, it says *look at this column,
here's the number in it*. It closes by tying the result back to the
original stakeholder ("we can now tell WSDA management that...").

**Mechanics paired with reasoning, including for pure UI navigation.**
Even purely administrative steps (installing software, downloading a
file) are narrated as plain, sequential instructions with no jargon
assumed — but wherever a *choice* is being made (which clause, which
operator, which quoting style), the narration states the reason for that
choice inline, immediately, not as a separate aside. The clearest
recurring example: text values must be quoted and numbers must not, and
every time this comes up the instructor explicitly pauses to flag it as a
common point of confusion before moving on — a "gotcha" beat, delivered
in the middle of the step it applies to, not batched into a separate
"common mistakes" segment.

**Progression is explicit, not assumed.** New concepts are consistently
introduced by naming what was already covered and what specifically is
now being added ("with what we've learned thus far, we can select all of
the records... but now, with the WHERE clause..."). A learner is never
handed a new keyword without being told, in the same breath, what problem
it solves that the previous approach didn't.

**Sentence-level style.** Short, spoken sentences; contractions
throughout; relatable analogies for jargon (a database table explained via
an unrelated everyday meaning of the word "table"; different database
systems compared to sneaker brands — same core function, different
brand); direct second-person address ("you're going to..."); and a small
set of casual, recurring transition phrases ("let's take a look," "let's
go," "up next, we'll...") used to move between beats instead of formal
signposting. None of this is decorative — the analogies and casual tone
are specifically what make dense, jargon-heavy material trackable for a
true beginner, which is rule 4's requirement in practice.

### Where metabase_poc still falls short of this pattern

Flagging for a future pass, not fixed here: `metabase_poc/video_1_1` is a
single flat lesson video with no chapter-opener/challenge structure around
it, so it can't yet exhibit the "recap relative to what's already been
taught" beat (rule/pattern above) — there's nothing established prior to
recap against. It also has no "gotcha" beat and no explicit statement of
what specific new capability is being added versus what the learner could
already do before this video, both because it's currently a standalone
proof-of-concept with only one video, not a chapter. Building out
`metabase_poc` into an actual multi-video chapter (opener → lesson(s) →
challenge) would be needed to fully match the proven structure, not just
match it at the single-video level.

## Enforcement

- **SQL/AI pipeline** (`generator/prompts.py` → production cards →
  `verify.py`): rules 1 and 3 are partially automated today via
  `verify.py`'s `check_engagement` (flags generic titles, missing
  `stakes` on the title card, and dry openings). Rules 2, 4, and 5 are not
  automated — they're checked by a human read of the narration against
  this document.
- **Metabase automation path** (hand-authored `lesson_script.yml` →
  `automation/metabase_driver.py`): rule 5 has driver-level support
  (`pre_actions`, `highlight_targets` — see automation/metabase_driver.py's
  module docstring), but nothing here is automatically *checked*. Every
  `lesson_script.yml` narration line should be checked against this
  standard by hand before recording, the same way `courses/metabase_poc/
  video_1_1/lesson_script.yml` was rewritten against it.
- **Any future content adapter** added to this system inherits this
  standard by default; if it doesn't fit one of the five rules as
  written, that's a sign the adapter's format needs its own explicit
  carve-out documented here, not that the rule gets silently skipped.

## Authoring checklist

Before recording, for every lesson:

- [ ] Is there a one-sentence outcome statement before the first action,
      framed (where a prior lesson/chapter exists) as the gap between
      what the learner can already do and what they can't yet?
- [ ] For every narrated step, is there a reason stated for *why* this
      step happens, not just *what* is being clicked/typed/shown?
- [ ] Does the lesson trace back to one concrete, stated scenario with
      real stakes, and are specific values (filter ranges, thresholds,
      table choices) motivated by that scenario rather than arbitrary?
- [ ] Does any line assume the learner already knows this specific tool's
      UI, naming, or layout?
- [ ] Does every value, column, or field named in narration appear
      highlighted on screen at that moment — not just the click that
      leads to it, and not just described in voice?
- [ ] Does narration state the actual resulting number/value after an
      action, tied to a specific visible column, rather than a vague
      description of the outcome?
