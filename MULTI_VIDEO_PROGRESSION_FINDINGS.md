# Multi-Video Progression: Findings

A scoped test, not a system. This connects three existing videos
(`courses/metabase_poc/video_1_1`, `video_1_2`, `video_1_3`) to learn what
a real multi-video course actually requires, the same way the Metabase
target itself was proven out as a scoped PoC before committing to
building it out. It does not build a general multi-video course
orchestrator — see "What would actually be needed" below for what that
would still take.

**Status: the environment architecture question this document originally
raised has been decided, implemented, and now proven repeatable across a
third, structurally different video — not a one-off that happened to
work for a single pair.** The first pass proved continuity manually
against one continuous Metabase session; a second pass replaced that with
API-seeded state and re-proved the same result — `video_1_2` recorded
fully independently, `video_1_1` never run — against a genuinely fresh
environment. A third pass then tested whether that mechanism generalizes
past the one pair it was built on, with `video_1_3` — a workflow neither
prior video's automation exercised. All three passes are recorded below,
in order, because each one's finding motivated the next pass's design or
scope.

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

## Pass 2's verdict: generalizes to one pair, not yet proven past that

**Both the narration technique and the state mechanism generalize across
`video_1_1` → `video_1_2`.** The recap technique was already content, not
code, and never depended on which state-bridging approach was used. The
state mechanism, after this pass, is genuinely reusable in principle:
`requires_state` is plain data any future lesson script can declare,
`state_seed.py`'s seeding functions are generic (resolve any table/field
by name, build a `between` filter, create/reuse a card, create/reuse a
dashboard, attach cards to it) rather than hardcoded to this specific
pair of videos, and `action_add_to_dashboard` now handles all three real
UI branches found rather than assuming one.

What was still true and worth restating at the time: this proved the
*mechanism* on one pair of videos, built and debugged against exactly
that pair. "Generic in principle" and "proven to generalize" are
different claims — pass 3 exists to close that gap.

## Pass 3: does the mechanism hold on a third, different video, or was it coincidence?

`video_1_3` ("One Filter, Both Charts") was deliberately chosen to be
structurally different from both priors, not a third instance of either
one's shape: `video_1_1` builds and filters a question, `video_1_2`
summarizes and charts one, `video_1_3` opens the *existing* dashboard
from the first two videos, adds a dashboard-level filter, and connects it
to both existing charts' `Created At` field at once. It's also the first
video whose `requires_state` needs a chart question (`Monthly Revenue
Trend`, a Sum aggregation with a month breakout), not just a filtered
table like `High Value Orders`.

The transcripts were re-read specifically for how a *third*-in-sequence
video's opening differs from a second one — not assumed to be the same
pattern as `video_1_2`'s recap. `05_04` (third video in that chapter's
sequence) turned out to use the same light, scenario-continuation
register as `05_03` (second in sequence) — no heavier formal recap just
because it's video 3, but a brief "thus far" acknowledgment of
accumulated progress that the second video's opening didn't need yet.
`06_03` (third video after a chapter-opener) has almost no recap at all,
since it continues the immediately preceding video's own task rather than
opening a new stakeholder request. `video_1_3`'s new material (a
dashboard filter spanning two existing charts) is a new stakeholder
request, closer to `05_04`'s shape, so its opening names both existing
artifacts (necessary here specifically because the whole teaching point
is that *one* filter controls *two* things) but stays in the same light,
story-driven register as `video_1_2`'s opening — not a heavier
chapter-style rundown just because it's third.

Recorded completely independently: every existing artifact was archived
first (confirmed via the API — zero active matches for either question
name or the dashboard name), then `video_1_3` was run from a fresh
container with **neither `video_1_1` nor `video_1_2` actually run this
pass**. The driver's seeding step created all three `requires_state`
artifacts fresh via the API before Playwright even started. 15/15 events
succeeded.

### The honest answer: the mechanism's format held; its implementation did not, and a real bug was found in extending it

This is the actual finding this pass exists to produce, not "video_1_3
works":

- **What held unmodified:** the `requires_state` declarative format
  itself, `seed_required_state()`'s orchestration (seed all questions,
  then all dashboards, resolve by name), its idempotency behavior, and —
  notably, since this was the more dangerous of the two video_1_2 bugs —
  `action_add_to_dashboard`'s fixed priority order (named target before
  "New dashboard" before bare Save). `video_1_3` doesn't call
  `action_add_to_dashboard` at all (it edits an already-pinned dashboard
  directly, via `open_saved_item` and a filter-mapping flow), so this
  isn't a retest of the same code path — it's a second, independent
  question asked of the same dashboard-state layer, and it answered
  clean: `GET /api/dashboard/20` after recording showed exactly one
  active dashboard, both cards present, no duplicates.
- **What needed real extension:** `state_seed.py`'s question-seeding
  schema only supported a `filter` key before this pass.
  `Monthly Revenue Trend` needed a `sum` aggregation and a `month`
  breakout — tested against the old schema first and got a plain
  `KeyError`, confirming the gap directly rather than guessing it would
  eventually need extending. Fixed by adding `_build_aggregation_mbql`
  and `_build_breakout_mbql` and wiring them into `_seed_question`.
- **A real, separate bug found while extending it:** the original
  field-name lookup did a bare `.lower()` on the spec's field name. That
  happened to work for `"Total"` (Metabase's real column is `TOTAL`) by
  coincidence, and broke immediately on `"Created At"` (Metabase's real
  column is `CREATED_AT`, underscore, not space) — a plain `KeyError`,
  not a silent wrong result, but still a real defect that had been
  latent since the very first `requires_state` spec and simply never
  been exercised by a multi-word field name until now. Fixed with a real
  `_normalize_field_name` helper (`.lower().replace("_", " ")`), applied
  consistently everywhere a field name is looked up, not a special case
  for this one field.
- **Three small driver mechanisms were new, not extensions of existing
  bugs:** `action_open_saved_item` (search + Enter, needed because this
  video opens an existing dashboard rather than building something new),
  an `"index"` option on the `"text"` locator kind, and a new `"label"`
  locator kind (both needed for the dashboard filter-mapping UI, which
  reuses the same visible text — "Orders.Created At", "Select…" — for
  more than one control on screen at once).

So: the *shape* of the API-seeded architecture — declare state as data,
seed it via HTTP before recording, verify against real state after —
held without any redesign. Its *implementation* had a real gap (no
aggregation/breakout support) and a real latent bug (field-name
normalization), both found by actually building a genuinely different
third video, not by inspecting the code for problems in the abstract.
That is the difference between "generic in principle" (pass 2's claim)
and "proven to generalize" (this pass's claim) — and it took a real
video with real new requirements to tell them apart.

### Verified against real API state, not just the audit log

Per `QA_CHECKLIST.md` item 9 and the discipline the video_1_2 pass's
silent duplicate-dashboard bug established: queried the live Metabase API
after recording, not just trusted the driver's "15/15 events succeeded."
Confirmed exactly one active copy each of `High Value Orders` (id 66),
`Monthly Revenue Trend` (id 67), and `WSDA Metabase Demo Dashboard` (id
20); the dashboard's one `Date` parameter is mapped to both cards via the
same field (13, `Created At`) through matching `parameter_mappings` —
exactly what the narration claims ("one filter, both charts") and exactly
what manual UI exploration produced when this workflow was first
prototyped by hand. No duplication, no orphaned card, no silent wrong
target. All nine `QA_CHECKLIST.md` items were run against the rendered
output and passed, including a frame-level check that both
"Orders.Created At" chips are highlighted simultaneously at the core
teaching moment (item 7) and the sequencing check that every commit event
fires only after its preceding highlight/pause completes (item 4).
Metabase state was archived back to a clean slate afterward, matching the
repeatability discipline established in pass 1 and pass 2.

## Does this generalize, or was it special-cased?

**Yes, past a single pair, with one honest caveat.** Three structurally
different videos (filter/save/dashboard; summarize/chart-type;
dashboard-filter-spanning-two-charts) now all seed their prerequisite
state via the same declarative mechanism, verified against real API state
each time, with zero continuous-session dependency between any of them.
The caveat: every extension so far (the `sum`/breakout addition, the
field-normalization fix, the three new driver mechanisms) was demand-
driven by an actual video that needed it, not built ahead of need — which
is the right discipline for a PoC, but it also means the schema's
coverage is still exactly as wide as three videos' worth of real
requirements, not wider. See below for what's still untested.

## What would actually be needed for a real multi-video course

1. **Lesson script format** — proven across three relationship shapes now
   (a filtered table, a Sum/breakout chart, a dashboard filter mapped to
   two existing cards). Still not covering every artifact type Metabase
   has (models, metrics, collections) or richer query shapes (joins,
   multiple filters/aggregations combined, filter operators beyond
   `between`) — extend `state_seed.py`'s dispatch as real lesson scripts
   need them, not speculatively ahead of that, same discipline that
   produced the aggregation/breakout addition and the field-normalization
   fix in pass 3.
2. **Driver state-awareness** — done for `add_to_dashboard`'s three
   branches, and now independently exercised (not just re-tested) by
   `video_1_3`'s different dashboard-editing path with a clean real-state
   result. Other actions that could plausibly hit similar already-exists
   branches (`save_question` itself, if a question with the same name
   already exists) still haven't been tested against that condition,
   because nothing has forced it yet.
3. **Environment architecture** — decided and now proven repeatable:
   API-seeded state per recording, not a long-lived shared instance. Any
   single video can be re-recorded, edited, or recorded out of order
   independently, without cascading re-recording of everything before or
   after it — demonstrated directly by recording `video_1_3` with neither
   prior video having actually run this pass.
4. **QA** — `QA_CHECKLIST.md` item 9 (added after pass 2, exercised
   again in pass 3) covers this: confirm, before calling a lesson done,
   that everything `requires_state` declares actually exists in that real
   shape after recording, by the same API query `state_seed.py` itself
   performs.
5. **Not yet built**: anything that orchestrates *which* videos need
   seeding for a given course, in what order, or manages a real N-video
   dependency graph. Three passes have each hand-written `requires_state`
   for one specific video; a real system would need lesson generation (or
   authoring tooling) to produce it automatically from a course outline.
   Three data points is still not enough to say the schema/dispatch
   extension pattern will keep holding cheaply as N grows further —
   worth another structurally-different video before believing that
   without re-checking.

## Bottom line

Three videos read as one progressing course, from independent, fully
rebuildable state rather than a fragile continuous session, and the
mechanism has now been shown to generalize rather than just work once.
Getting there took three real passes: the first proved continuity was
necessary and found one UI-branching bug by brute force; the second
implemented the actual architecture and found a more dangerous
second bug — a silent wrong-click that reported success while producing
the wrong result — caught only by real-state verification, not trusting
"N/N events succeeded"; the third built a genuinely different third video
against that architecture and found the honest limits of "generic in
principle" — the declarative format and orchestration held unmodified,
but the seeding implementation needed a real feature it didn't have
(aggregation/breakout support) and had a real latent bug (field-name
normalization) that a filtered-table-only test history had simply never
exercised. Each pass's bug was caught by the same discipline: querying
real application state after recording, not trusting a clean audit log —
`QA_CHECKLIST.md` item 9's whole reason for existing, now with three
independent instances behind it instead of one.
