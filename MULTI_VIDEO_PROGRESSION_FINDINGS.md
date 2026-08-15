# Multi-Video Progression: Findings

A scoped test, not a system. This connects exactly two existing videos
(`courses/metabase_poc/video_1_1` and `video_1_2`) to learn what a real
multi-video course actually requires, the same way the Metabase target
itself was proven out as a scoped PoC before committing to building it
out. It does not build a general multi-video course orchestrator — see
"What would actually be needed" below for what that would still take.

**Status: the environment architecture question this document originally
raised has been decided and implemented, not left open.** The first pass
proved continuity manually against one continuous Metabase session; a
second pass replaced that with API-seeded state and re-proved the same
result — `video_1_2` recorded fully independently, `video_1_1` never
run — against a genuinely fresh environment. Both passes are recorded
below, in order, because the first pass's finding (continuity requires
*some* mechanism, not independent fresh containers with no bridge at
all) is what motivated the second pass's design.

## Method

Re-read the transcripts (`Transcripts/`) specifically for how *individual*
videos hand off to each other within a chapter, not just the heavier
chapter-opener pattern already in `LESSON_CONTENT_STANDARD.md`. The two
textures are different:

- **Chapter-opener (MM30) transitions** (e.g. `06_01`) recap explicitly
  and broadly: "so far we've written a lot of queries... but we've only
  been getting data from one table at a time." Reserved for a genuinely
  new *topic* (single-table queries → joins).
- **Within-chapter (XR30 → XR30) transitions** are lighter and carry the
  *story* forward, not the pedagogy. `05_02` → `05_03`: "management is
  pretty happy with us finding [X]... but now they'd like to know [Y]."
  No "in the last video you learned..." framing at all — just the same
  stakeholder, a new ask.

`video_1_1` → `video_1_2` (filter to a saved question → chart it) is a
same-scenario capability increment, not a new topic, so the opening was
modeled on the **light, within-chapter** pattern, not the chapter-opener
one. The rewritten opening (`video_1_2`'s `e00_intro` only, per the first
pass's scope):

> Remember that High Value Orders list you saved and pinned to a
> dashboard last time? Your manager's been checking it herself ever
> since, exactly like you set it up to do. But now she has a new
> question: is revenue actually trending up, or does it just feel that
> way from scrolling a list of orders? A filtered list can't answer
> that, so by the end of this, you'll turn that same order data into a
> single chart she can glance at and understand in seconds.

This lines up directly with `video_1_1`'s actual closing line ("It's
something she can check herself, anytime" → "she's been checking it
herself ever since") — a deliberate callback, confirmed by reading both
scripts side by side before rendering anything. Unchanged by the
architecture decision below: this narration technique doesn't care
whether the state it describes was seeded via API or produced by an
earlier recording, only that the state is real.

## Pass 1: proving continuity is required at all (continuous shared state)

The recap names a specific artifact ("High Value Orders... pinned to a
dashboard"). For that to be true rather than a nice-sounding fiction, it
had to actually exist in Metabase when `video_1_2` recorded. Checked
directly: at the start of this test, `video_1_1`'s artifacts were
**archived** — 11 stale copies each of "High Value Orders" and "WSDA
Metabase Demo Dashboard" sitting in the trash, left over from every prior
QA pass this session, which always cleaned up afterward to keep the
environment repeatable for independent testing.

So the two videos were recorded **back to back against one continuous
Metabase session**, deliberately not cleaning up in between, for the
first time this session: recorded `video_1_1` fresh, confirmed via the
API that its artifacts were live, recorded `video_1_2` immediately after
against that real state. **This answered the central question this
document originally posed: yes, narratively-true continuity requires
*some* real state bridge between videos — independent fresh containers
with no bridge at all does not work.** It did not yet answer *which*
bridge is right; that's what pass 2 tested.

This also surfaced a real Metabase UI-branching bug that pass 2 had to
resolve properly (see below): with zero existing dashboards,
`action_save_question`'s post-save "Add this to a dashboard" toast opens
a "New dashboard" creation prompt; with exactly one already present,
Metabase can skip that prompt and merge straight into editing the
existing dashboard instead, which `action_add_to_dashboard` wasn't
written to handle. Reproduced twice in pass 1 and worked around (not
fixed) by temporarily archiving the pre-existing dashboard so the
already-working zero-dashboard path could complete — a real, honest gap
in that pass's result, called out explicitly rather than glossed over.

## Pass 1's verdict: continuity works manually, doesn't generalize

29/29 (`video_1_1`) and 32/32 (`video_1_2`) events against the shared,
continuous state, audio/duration/pacing all correct. But: "record video
N-1, check the API by hand, don't clean up, record video N immediately
after" is not a repeatable system. It doesn't survive re-recording video
N-1 alone later, recording out of order, or a third video. Given how this
session's actual workflow has gone — constant re-renders after every fix
pass, re-tests after every standard update — that fragility is not a
theoretical concern, it's the normal case.

## Decision: API-seeded state, not continuous shared containers

Made explicitly, not inferred: **each video runs in an independent
environment; any state it depends on from a prior video is created
directly via Metabase's API immediately before recording, not by
re-running the prior video's UI actions and not by relying on a
long-lived shared container.**

### What changed

- **Lesson script format** gained `requires_state`, declaring what a
  video needs as data, not as "replay the prior video":

  ```yaml
  requires_state:
    - type: "question"
      name: "High Value Orders"
      database: "Sample Database"
      table: "Orders"
      display: "table"
      filter:
        field: "Total"
        operator: "between"
        min: 50
        max: 1000
    - type: "dashboard"
      name: "WSDA Metabase Demo Dashboard"
      contains: ["High Value Orders"]
  ```

- **`automation/state_seed.py`** (new) resolves this against the live
  Metabase instance and creates whatever's missing via direct API calls
  — real MBQL queries against resolved table/field ids, not simulated
  clicks. Idempotent by name: an already-existing active question or
  dashboard is reused, not duplicated, which matters given how much of
  this session's own testing has produced duplicate "High Value Orders"
  cards from repeated runs. Verified idempotent directly: running it
  twice in a row against the same state produced "already exists,
  reusing" both times, no duplication.
- **`run_lesson()`** calls the seeding step first, before Playwright even
  starts — pure HTTP, no browser, never in the recorded footage, the same
  treatment login/account setup already got.

### Re-proving the result against a genuinely fresh environment

Every existing artifact ("High Value Orders", "WSDA Metabase Demo
Dashboard", and everything from pass 1) was archived — a real clean
slate, confirmed via the API before proceeding. `video_1_2` was then
recorded **directly, without running `video_1_1` at all this pass**. The
driver's own seeding step created "High Value Orders" and "WSDA Metabase
Demo Dashboard" via the API, then the recording ran against that seeded
state: 32/32 events, mp4 duration matched the real 313s+ recording, audio
correct, pacing correct.

## A second real bug, and why the audit log alone didn't catch it

Seeding a dashboard as a precondition made the branching behavior found
in pass 1 unavoidable rather than occasional — with a dashboard always
already present, every recording now exercises that branch. Fixing it
properly (not working around it this time) meant handling it live, and
doing so surfaced a *third* branch, more serious than the first because
it fails silently:

With an **API-seeded** dashboard specifically (as opposed to one created
moments earlier by an actual UI-recorded save, as in pass 1), Metabase's
"Add this to a dashboard" toast showed a full **picker dialog** — the
target dashboard listed as a selectable option, *and* a "New dashboard"
button also visible in the same dialog — rather than the direct
auto-merge pass 1 found. The first fix attempt checked for "New
dashboard" before checking for the named target, so it always won that
race: it clicked "New dashboard", created a **second dashboard with the
exact same name**, and pinned the new chart there instead of onto the
real seeded one.

**This did not raise an exception. The recording reported 32/32 events
succeeded. It looked exactly like success.** It was only caught by
querying Metabase's actual API state afterward and finding two active
dashboards both named "WSDA Metabase Demo Dashboard" — one holding "High
Value Orders" alone, the other holding "Monthly Revenue Trend" alone —
instead of one dashboard holding both. This is precisely the class of
failure `QA_CHECKLIST.md` was written to warn about (automated
event-count success is not sufficient), now with a second, concrete,
first-hand instance to point to.

Fixed by checking priority correctly — the named target dashboard first,
"New dashboard" only if no match, and a bare "Save" click only if neither
appears (the pass-1 auto-merge case) — then **re-verified against real
API state, not the audit log**: re-ran, confirmed via `GET
/api/dashboard/17` that it contains both `High Value Orders` and `Monthly
Revenue Trend` on the one real dashboard, no duplicate created.

## Does this generalize, or was it special-cased?

**Both the narration technique and the state mechanism generalize now.**
The recap technique was already content, not code, and never depended on
which state-bridging approach was used. The state mechanism, after this
pass, is genuinely reusable: `requires_state` is plain data any future
lesson script can declare, `state_seed.py`'s seeding functions are
generic (resolve any table/field by name, build a `between` filter,
create/reuse a card, create/reuse a dashboard, attach cards to it) rather
than hardcoded to this specific pair of videos, and `action_add_to_dashboard`
now handles all three real UI branches found rather than assuming one.

What's still true and worth restating: this proves the *mechanism* on one
pair of videos, not a general orchestrator across an arbitrary N. See
below for what scaling past that would still need.

## What would actually be needed for a real multi-video course

1. **Lesson script format** — done for the one relationship type tested
   (`requires_state` naming questions/dashboards and how they're built).
   Not yet covering every artifact type Metabase has (models, metrics,
   collections) or richer query shapes (joins, multiple filters,
   aggregations beyond a single `between`) — extend
   `state_seed.py`'s dispatch as real lesson scripts need them, not
   speculatively ahead of that, same discipline as everything else this
   session.
2. **Driver state-awareness** — done for `add_to_dashboard`'s three
   branches. Other actions that could plausibly hit similar
   already-exists branches (`save_question` itself, if a question with
   the same name already exists) haven't been tested against that
   condition yet, because nothing has forced it yet.
3. **Environment architecture** — decided: API-seeded state per
   recording, not a long-lived shared instance. Any single video can now
   be re-recorded, edited, or recorded out of order independently,
   without cascading re-recording of everything before or after it.
4. **QA** — a `requires_state`-aware check now belongs in
   `QA_CHECKLIST.md` proper (not added yet, since this is the first
   lesson to use the field): confirm, before recording, that everything
   `requires_state` declares either already exists or was just seeded,
   by the same API query `state_seed.py` already performs.
5. **Not yet built**: anything that orchestrates *which* videos need
   seeding for a given course, in what order, or manages a real N-video
   dependency graph. This pass hand-wrote `requires_state` for one known
   pair; a real system would need lesson generation (or authoring
   tooling) to produce it automatically from a course outline.

## Bottom line

Two videos read as one progressing course, and now do so from
independent, fully rebuildable state rather than a fragile continuous
session. Getting there took two real passes: the first proved continuity
was necessary and found one UI-branching bug by brute force; the second
implemented the actual architecture, and in doing so found a *second*,
more dangerous bug — a silent wrong-click that reported success while
producing the wrong result — which only real-state verification (not
trusting "N/N events succeeded") caught. That second finding is arguably
the more important one: it's a direct, first-hand demonstration of why
`QA_CHECKLIST.md` insists automated pass/fail is not sufficient on its
own, from inside the very work meant to make this system more reliable.
