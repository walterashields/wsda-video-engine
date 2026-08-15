# Multi-Video Progression: Findings

A scoped test, not a system. This connects exactly two existing videos
(`courses/metabase_poc/video_1_1` and `video_1_2`) to learn what a real
multi-video course actually requires, the same way the Metabase target
itself was proven out as a scoped PoC before committing to building it
out. It does not build general multi-video orchestration — see "What
would actually be needed" below for what that would take.

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
one. The rewritten opening (`video_1_2`'s `e00_intro` only, per scope):

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
scripts side by side before rendering anything.

## Verifying state, not just narration

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
first time this session:

1. Recorded `video_1_1` fresh.
2. Confirmed via the API that "High Value Orders" (card 54) and "WSDA
   Metabase Demo Dashboard" (dashboard 14) were live and active.
3. Recorded `video_1_2` immediately after, against that real state.

**This is the core finding, and it answers the task's central question
directly: yes, this requires continuous session/database state, not
independent fresh containers.** Every prior render this session (and the
prior QA passes' "green" results) ran against a freshly-cleaned
environment; the moment continuity was actually required, it had to be
engineered by hand, once, for this one pair of videos.

## A real bug this surfaced, not just a state question

Recording against genuine continuity didn't just test whether an artifact
*existed* — it changed which **UI path** Metabase itself takes, and broke
the existing script:

`action_save_question`'s post-save "Add this to a dashboard" toast is
built (and was working, repeatedly, all session) against a **zero
existing dashboards** environment, where it opens a "New dashboard"
creation prompt. With **exactly one** dashboard already present (video
1's), Metabase skips that prompt entirely and navigates straight into
*editing that existing dashboard*, with the new chart already auto-placed
on it. `e10_hl`'s highlight and `e10_commit`'s click both wait for
"New dashboard" text that, in this branch, never appears — confirmed by
pulling a frame at the failure point, which showed the dashboard editor
already open with both cards present, not a picker dialog.

This reproduced identically twice in a row against real (non-duplicate)
continuity state, so it isn't the toast-timing flakiness from stale test
debris found earlier in the project (`QA_CHECKLIST.md` item 5's history)
— it's a distinct, real behavioral branch in Metabase's own UI based on
existing-dashboard count (0 vs. 1 vs. likely N+).

**Not fixed in the driver this pass** (would mean teaching
`action_add_to_dashboard` to detect and handle the "already merged"
branch, real but scoped work, not orchestration). For this render, it was
isolated instead: the "High Value Orders" *question* stayed live
throughout (the artifact the recap narration actually names and depends
on), while the pre-existing dashboard was temporarily archived so the
already-working zero-dashboard path could complete. Final live state after
this render: `High Value Orders` (video 1, untouched, id 54) and `Monthly
Revenue Trend` (video 2, id 57) both active as separate questions, but on
two separate dashboards (`Revenue Overview`, new) rather than one unified,
growing one. That's the honest gap: question-level continuity is real;
dashboard-level continuity was sidestepped, not achieved.

## Verified end to end

29/29 (`video_1_1`) and 32/32 (`video_1_2`) events, both against the
shared, continuous state. `video_1_2`'s render: mp4 duration matches the
real 308.5s recording, audio present and audible throughout (opening
recap segment and closing both checked directly), pacing unregressed. The
opening was extracted and watched at the frame level; Metabase's own home
screen even greeted the returning session differently ("Good to see you,
WSDA" vs. the first-run "Howdy, WSDA") — a small, unplanned, genuinely
nice reinforcement of continuity, not something engineered.

## Does this generalize, or was it special-cased?

**The narration technique generalizes cleanly.** Recapping the prior
video's concrete outcome, naming the specific saved artifact, and framing
the new material as the stakeholder's next ask (rather than reciting
pedagogy) is a content pattern, grounded directly in the transcripts, that
any video N can apply against video N-1. Nothing about the wording
approach was specific to these two videos.

**The state mechanism does not generalize — it was manual, once.**
"Record video N-1, check the API by hand, don't clean up, record video N
immediately after" is not a repeatable system. It doesn't survive:
re-recording video N-1 alone later (would need to redo N too, or state
drifts), recording videos out of order, or more than two videos (state
complexity compounds, and so does the UI-branching risk found above — a
third video would hit a *different* Metabase branch again, e.g. two
existing dashboards instead of one).

## What would actually be needed for a real multi-video course

1. **Lesson script format**: an explicit `continues_from: video_1_1`
   (or similar) field, naming which prior lesson a video depends on and,
   ideally, which specific artifacts (question/dashboard names) it
   assumes exist — so this dependency is declared and checkable, not
   discovered by hand-querying the API the way this test did.
2. **Driver state-awareness**: actions like `add_to_dashboard` need to
   detect which UI branch they're actually in (0 / 1 / N existing
   dashboards) rather than assume one fixed path — the exact bug found
   here. Likely more such branches exist and haven't been hit yet because
   nothing has run against accumulated state before now.
3. **Environment architecture** (the question this task asked to flag,
   not resolve): does a course run against one long-lived, continuously
   accumulating Metabase instance, or does each recording session
   reconstruct the required prior state via direct API calls (fast,
   deterministic, decoupled from having to actually re-record prior
   videos) before recording video N? The second is very likely the right
   answer for a real system — it would let any single video be
   re-recorded or edited independently without cascading re-recording of
   everything after it — but it's a real architectural decision with
   real tradeoffs (API-seeded state might not perfectly match what an
   actual recorded run produces), not something to decide unilaterally
   here.
4. **QA**: a new checklist-style check (companion to `QA_CHECKLIST.md`,
   not added there yet since it doesn't apply to any single-video render)
   -- "does every artifact video N's narration references provably exist
   in the environment at record time" -- automatable via the same API
   query used by hand in this test.

## Bottom line

Two videos can genuinely read as one progressing course — the recap
technique is sound and reusable. Getting there required stepping outside
this session's normal (correct, for single-video QA) habit of resetting
the environment between tests, and doing so immediately surfaced a real
UI-automation bug that no amount of single-video testing would ever have
found. That's the actual proof-of-concept result: continuity is a real,
different failure mode from anything tested so far, worth the
architecture investment above before attempting a third video.
