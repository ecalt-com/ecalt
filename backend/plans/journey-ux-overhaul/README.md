# Journey UX Overhaul — Phased Plan

Status: **DRAFT — for review, not yet implemented**
Created: 2026-06-11

## Scope (from product request)

1. Fix the Start Journey button — it currently does nothing.
2. Make the journey quiz mandatory, with 2–3 questions per step.
3. Enforce sequential step completion — finish one step before the next unlocks.
4. After a journey is finished, suggest the next level of the same course + similar
   courses, **unique to the user, never repeated**.
5. Remove the "Short Haiku responses only · No sign-up needed" hero tagline.

## Current-state findings (code + Supabase)

### Code
- The live frontend is the **Vite tree** (`frontend/src/pages`, `frontend/src/components`).
  `frontend/src/app/**` is a dead Next.js tree (package.json scripts run vite) — do not
  fix bugs there, but note duplicates exist (e.g. `src/app/journey/[id]/page.tsx:109`).
- `frontend/src/pages/Journey.tsx:217` — Start Journey/Continue button has **no onClick**.
- `frontend/src/components/StepNode.tsx:47` — expanding a step **auto-marks it complete**
  on first content load ("viewing = completing").
- `frontend/src/components/StepNode.tsx:63` — the numbered circle is a free toggle; any
  step can be marked complete/incomplete in any order.
- `frontend/src/components/QuizCard.tsx` — optional single-question free-text quiz with
  hints, rendered below step content. Skipping it has no consequence.
- `backend/app/api/v1/endpoints/progress.py:105` — `POST /progress/{journey_id}/{step_id}`
  accepts any step in any order (idempotent insert, no sequence check).
- `backend/app/api/v1/endpoints/quiz.py` — `POST /quiz` generates one question;
  `/quiz/{id}/hint`, `/quiz/{id}/submit`. Keyed by `concept` only.
- `frontend/src/pages/Journey.tsx:74-86` — "More like this" is client-side tag overlap;
  does not exclude journeys the user already completed/started.
- `frontend/src/pages/Home.tsx:547,556` — the two tagline variants.

### Supabase (production data, checked 2026-06-11)
- `journeys` (29 rows): `id text, uid, question, title, description, age_group,
  difficulty text, estimated_hours, steps jsonb, tags text[], icon, is_curated bool`.
  **No "level/series" column** — difficulty (`beginner|intermediate|advanced`) is the
  only progression axis. Heavy near-duplicates exist (4 ~identical "AI music" journeys,
  3 "black holes" journeys) because /explore generates a fresh journey per question.
- `user_progress` (54 rows): `uid, journey_id, step_id, completed_at` — per-step rows,
  unique on (uid, journey_id, step_id). Journey "completion" is derived (all steps done).
- `quiz_sessions` (6 rows): `uid, concept, quiz_data jsonb, hints_given, submitted`.
- `quiz_results` (1 row): `uid, concept, difficulty, is_correct, hints_used`.
  **Neither quiz table references journey_id/step_id** → migration required before quiz
  results can gate step completion.

## Phases

| Phase | File | Touches | Depends on |
|-------|------|---------|-----------|
| 1 | [phase-1-quick-fixes.md](phase-1-quick-fixes.md) | frontend only | — |
| 2 | [phase-2-sequential-steps.md](phase-2-sequential-steps.md) | frontend + backend | Phase 1 (expand-step plumbing) |
| 3 | [phase-3-mandatory-quiz.md](phase-3-mandatory-quiz.md) | backend + migration + frontend | Phase 2 (completion semantics) |
| 4 | [phase-4-completion-suggestions.md](phase-4-completion-suggestions.md) | backend + frontend | Phase 2 (reliable completion signal) |

Recommended order: 1 → 2 → 3 → 4. Phases 3 and 4 are independent of each other and can
be parallelized after Phase 2 lands.

## Open decisions (need product sign-off before Phase 3/4)

1. **Quiz pass criteria**: proposal — 3 questions per step, ≥2 correct to pass,
   unlimited retries with regenerated questions.
2. **Guests**: quiz + sequential gating apply to signed-in users; guests keep read-only
   browsing (they have no progress rows anyway). Confirm.
3. **Existing users** with out-of-order progress: grandfather existing rows; enforcement
   applies only to new completions. Confirm.
4. **"Next level" generation cost**: if no higher-difficulty journey exists for the topic,
   we generate one via AI (token cost per completion). Acceptable? Alternative: only
   suggest from existing catalogue.
