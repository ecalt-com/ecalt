# Phase 2 — Sequential Step Completion

> **Status: IMPLEMENTED 2026-06-11** (uncommitted). Backend 409 gate in
> `progress.py` (`_journey_steps` shared lookup + `_check_previous_steps_complete`,
> grandfathered legacy rows); 7 new API tests in
> `tests/api/test_progress_sequential.py`, full suite green (11 pre-existing
> live-DB integration failures unrelated). Frontend: `locked` prop on StepNode
> (lock icon, disabled header, no content fetch), circle is now a status-only
> indicator, `toggleStep` → forward-only `completeStep` with 409 toast on both
> Journey and Explore pages. `markStepIncomplete` kept in api.ts but no UI path.

Goal: a user must finish step *n* before step *n+1* unlocks. Today any step can be
expanded, and the numbered circle freely toggles any step complete — so a journey can
be "finished" by clicking 10 circles.

## Current behaviour to change

| Where | Behaviour today |
|-------|----------------|
| `StepNode.tsx:63` | Numbered circle = free complete/incomplete toggle on any step |
| `StepNode.tsx:47` | Expanding a step auto-marks it complete on first content load |
| `Journey.tsx:96` (`toggleStep`) | Optimistically toggles any step, no order check |
| `progress.py:105` | Backend accepts any (journey, step) insert, no order check |

## 2.1 Frontend gating

1. Compute lock state in `Journey.tsx`: step `i` is **unlocked** iff `i === 0` or
   `steps[i-1].completed`. Pass `locked: boolean` to `StepNode`.
2. `StepNode` locked rendering:
   - Circle shows a `Lock` icon (lucide), muted colors, `cursor-not-allowed`.
   - Header row not clickable (no expand, no content fetch); tooltip/caption
     "Complete the previous step to unlock".
3. Remove the circle's toggle-complete behaviour entirely (`StepNode.tsx:63-73`):
   - Completion now happens only through the step flow (content viewed in this
     phase; quiz passed once Phase 3 lands). The circle becomes a status indicator.
   - Keep `markStepIncomplete`/`DELETE` API for admin/debug, but remove the UI path.
     (Un-completing step 3 of 5 would re-lock later steps — avoid that footgun.)
4. `toggleStep` becomes `completeStep(stepId)` — forward-only, and refuses (no-op +
   toast) if the step is locked. Keep the optimistic update + revert-on-failure
   pattern (per CLAUDE.md Optimistic Update Pattern).
5. Guests (`user == null`): keep local-only progression with the same sequential rule
   so the UX is consistent; nothing is persisted (unchanged).

## 2.2 Backend enforcement

Client-side gating is trivially bypassable (the API is public). Enforce in
`progress.py mark_step_complete`:

1. Load the journey's ordered step IDs — same dual source as `_resolve_step_meta`
   (DB `journeys.steps` jsonb first, then `SAMPLE_JOURNEYS` fallback). Refactor that
   helper so both can share the lookup.
2. Find the index of `step_id`. If any earlier step ID has no `user_progress` row for
   this uid, return **409 Conflict** with
   `{"detail": "previous_steps_incomplete", "missing_step_ids": [...]}`.
3. If the journey/step can't be resolved (deleted journey), keep today's permissive
   insert (don't break old links).
4. **Grandfathering:** no data backfill. Existing out-of-order rows stay; the check
   only constrains new inserts. A user with steps {1,3} done can complete 2, then 4.

## 2.3 Frontend handling of 409

In `completeStep`, on a 409 revert the optimistic update and toast
"Finish the earlier steps first". (Should be unreachable through normal UI.)

## Tests

- Backend (`tests/api/`): completing step 2 with step 1 done → 200; with step 1 not
  done → 409 + missing ids; step 1 always → 200; unknown journey → 200 (permissive);
  idempotent re-complete → 200.
- Manual: locked steps not expandable; finishing step n unlocks n+1; progress bar and
  "Complete Journey" card (`Journey.tsx:257`) still trigger only when all steps done.

## Acceptance

- A new user cannot mark step 3 before steps 1–2, via UI or direct API call.
- Journey completion is only reachable by walking steps in order.
