# Phase 4 — Post-Completion Suggestions (next level + similar, never repeated)

> **Status: IMPLEMENTED 2026-06-11** (uncommitted). New
> `app/services/suggestion_service.py` (pure `pick_suggestions` + budget-gated
> `generate_next_level`) and `GET /journeys/{id}/suggestions` in journeys.py.
> Dedup uses title+tag token Jaccard ≥0.6 (6-char stem) **plus** tag-set
> Jaccard ≥0.7 — validated against live prod data (the four AI-music dupes no
> longer surface). Next-level AI generation only fires when the user has
> actually completed the source journey ("More like this" calls it on every
> page view), reuses authored-but-unstarted level-ups instead of regenerating,
> and never 402s the endpoint (catalogue-only fallback). Frontend:
> CompletionOverlay shows level-up CTA + ≤3 similar; "More like this" is
> history-aware for signed-in users (tag-overlap fallback for guests/errors);
> Journey page state now resets on id change (overlay navigates within the
> same route). 15 tests in tests/services/test_suggestions.py; 105 api+service
> tests green; vite build green.

Goal: when a user finishes a journey, immediately offer (a) the **next level of the
same course** and (b) **similar courses** — all guaranteed new to that user.

## Why the current "More like this" isn't enough

- `Journey.tsx:74-86` scores by tag overlap client-side over the full `getJourneys()`
  list. It does **not** exclude journeys the user completed or started.
- Production data has heavy near-duplicates (4 ~identical "AI music" journeys,
  3 "black holes" journeys) because /explore mints a new journey per question — tag
  overlap alone would happily suggest the same course four times.
- There is no "level/series" relation between journeys; `difficulty`
  (beginner → intermediate → advanced) is the only progression axis.

## 4.0 Verified generation pipeline (what we can reuse)

From the backend graph + `ai_service.py:140-180`: `explore()` →
`check_budget` → `ai_service.generate_journey(uid, question)` →
`complete_text(interaction_type="journey", max_tokens=2048)` → parse JSON →
`Journey` model → persisted to the `journeys` table by the endpoint →
`record_usage`. The journey prompt also lives in the `ai_provider_config` table
(`get_config("journey")`), and `inject_fingerprint(uid, …)` personalizes it.

So "generate the next level" is a thin wrapper around the existing pipeline:
`generate_journey` needs an optional parameter (e.g. `extra_context` or
`difficulty_override`) appended to `user_content` — "Level 2 of '<title>' for a
learner who completed: <step titles>. Difficulty: intermediate." No new AI
plumbing, same budget/usage accounting as `/explore`.

## 4.1 Backend — `GET /api/v1/journeys/{journey_id}/suggestions` (auth required)

Response:
```json
{
  "next_level": { ...Journey or null },
  "similar": [ ...Journey, max 3 ],
  "next_level_generated": false
}
```

Algorithm:

1. **User exclusion set** — one query joining `user_progress` against `journeys`:
   - *completed*: journeys where the user's distinct step count == journey's step count
   - *started*: any journey with ≥1 progress row
   Exclude both ("completely unique to the user"). Also exclude journeys the user
   generated (`journeys.uid = uid`) — they've seen those.
2. **Candidate pool**: all journeys minus exclusion set minus the source journey.
3. **Dedupe near-identicals** within the pool *and against the exclusion set*:
   normalize title (lowercase, strip punctuation/stopwords) + sorted lowercase tag
   set; drop a candidate when similarity to an excluded/selected journey exceeds a
   threshold (token-set Jaccard ≥ 0.6 — tune against the AI-music/black-holes dupes
   in prod data). This is what makes "no repeats" real despite the dupe-filled table.
4. **next_level**: candidate sharing ≥2 tags (or normalized-topic match) with the
   finished journey at the next difficulty (beginner→intermediate→advanced;
   advanced→null). If none exists, **generate one** via
   `ai_service.generate_journey` with the same topic/question, bumped difficulty, and
   an explicit "level 2 — assume the learner completed: <step titles>" prompt note;
   persist with `is_curated=false`, return `next_level_generated: true`.
   - Gate generation behind the user's token budget (`check_budget`/`record_usage`),
     same 402 semantics as elsewhere. Decision #4: confirm cost is acceptable;
     fallback is catalogue-only (next_level may be null).
5. **similar**: top 3 remaining candidates by tag overlap, prefer same difficulty,
   prefer `is_curated`, tiebreak newest.
6. Anonymous users: 401 (endpoint requires auth); frontend simply hides the section.

Performance: pool is small (29 rows) — single-pass Python is fine; no new indexes.

## 4.2 Frontend

1. **CompletionOverlay** (`Journey.tsx:12-44`): after "Complete Journey", fetch
   suggestions and render inside the overlay:
   - Primary CTA: "Continue to Level 2: {title}" → `/journey/{id}` (replaces or sits
     above "View Passport").
   - "Or explore something similar": up to 3 compact cards.
   - Loading: keep overlay celebratory content immediately, stream suggestions in
     (skeleton row); on error, fall back to today's Passport/Keep-exploring buttons.
2. **"More like this"** (`Journey.tsx:282-302`): for signed-in users, replace the
   client-side tag overlap with the same endpoint (`similar` list) so mid-journey
   recommendations also respect uniqueness. Guests keep the current client-side list.
3. New `api.ts` function `getJourneySuggestions(journeyId, token)` + types.

## Tests

- Exclusion: completed and in-progress journeys never appear; user-authored journeys
  never appear.
- Dedupe: with the four "AI music" prod rows, at most one appears in `similar`, and
  none if the user finished any one of them.
- next_level: picks existing higher-difficulty match; generates when absent
  (mock LLM); advanced journeys → null next_level without generation.
- 402 path when generation is gated by budget.

## Acceptance

- Finishing a journey shows a level-up CTA plus ≤3 similar courses, none of which the
  user has completed, started, or authored — and no near-duplicate of anything they
  have done.
