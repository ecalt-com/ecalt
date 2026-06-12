# Phase 3 — Mandatory Multi-Question Quiz (2–3 questions)

> **Status: IMPLEMENTED 2026-06-11** (code uncommitted; **migration
> `quiz_step_linkage` already applied to Supabase**). Decisions taken: 3 questions,
> ⌈⅔n⌉ correct to pass (2/3), unlimited retries with fresh sets; guests keep
> view-to-complete (no quiz — auth required). DB style_prompt NOT changed —
> the array format is requested via user_content override, with single-object
> fallback parsing. Backend: `generate_quiz_set` + `step_quiz_status/passed` in
> quiz_service, set path + `GET /quiz/step-status/...` in quiz.py, 412 gate in
> progress.py (after the 409 order check). Frontend: QuizCard rewritten as
> mandatory auto-loading 3-question flow that calls completeStep on pass;
> StepNode no longer completes on view for signed-in users (guests still do);
> "Quiz · 2/3 to pass" chip added. Tests: tests/services/test_quiz_set.py +
> TestQuizGate in tests/api/test_progress_sequential.py — 90 api+service tests
> green; vite build green.
>
> **Addendum 2026-06-11 (user feedback):** (1) Quiz is skippable with an inline
> confirmation ("Skip anyway / Keep going") — skips are recorded in
> `quiz_results.skipped` (migration `quiz_skip_flag`, applied) via
> `POST /quiz/step-skip/{journey_id}/{step_id}`; `step_quiz_status` treats a
> skip as gate-open (`skipped: true`), and skipped rows are excluded from
> adaptive-difficulty history. Skip is offered in the active quiz, the failed
> state, and the error state. (2) All questions are now shown **at once** with
> per-question hint buttons and a single "Submit all answers" (parallel
> submits), replacing the one-at-a-time flow; results show as a per-question
> review. Partial-submit failures recover via a fresh set (sessions are
> single-use server-side).

Goal: each step ends with a mandatory quiz of 2–3 questions; the step only counts as
complete after the quiz is passed. Today the quiz is a single optional free-text
question with no consequence, and steps auto-complete just by viewing content
(`StepNode.tsx:47`).

Proposed pass rule (decision #1 in README): **3 questions, ≥2 correct to pass,
unlimited retries** (retry regenerates questions). Concept-type steps could use 2
questions if generation cost matters.

## 3.1 Database migration (Supabase)

`quiz_sessions` / `quiz_results` currently key only on `concept` — nothing links a quiz
to a journey step, so completion can't be gated on it.

```sql
-- apply via mcp apply_migration / supabase migration
alter table quiz_sessions add column journey_id text, add column step_id text,
                          add column quiz_set_id uuid;
alter table quiz_results  add column journey_id text, add column step_id text,
                          add column session_id uuid references quiz_sessions(id);
create index if not exists idx_quiz_results_step on quiz_results (uid, journey_id, step_id);
```

Nullable columns → existing 6 session / 1 result rows are unaffected; standalone
(non-journey) quizzes keep working with NULLs.

## 3.2 Backend — quiz set generation

Verified current implementation (`app/services/quiz_service.py`):
- `generate_quiz()` makes **one** `complete_text(interaction_type="quiz",
  max_tokens=700)` call and parses a single JSON object containing `question`,
  `hint_1..hint_3`, `correct_answer`, `answer_explanation`.
- The prompt (`style_prompt`) comes from `get_config("quiz")`, i.e. the
  **`ai_provider_config` DB table** — changing the question format is a *data*
  change in that table, not (only) a code change.
- The full quiz (incl. answer) is stored server-side in `quiz_sessions`; the client
  gets a public slice. `get_hint`/`submit_answer` operate per session row;
  `submit_answer` grades by normalized substring match and writes `quiz_results`.
- Adaptive difficulty reads the user's last 3 `quiz_results`.

Changes:

1. Extend `POST /api/v1/quiz` request with optional `journey_id`, `step_id`,
   `num_questions` (default 3, clamp 2–5). Response becomes a **quiz set**:
   `{ quiz_set_id, questions: [...existing public question shape...] }`.
   - **One LLM call returning a JSON array of N distinct questions** (each with its
     own hints/answer/explanation) — raise `max_tokens` to ~1800. N separate calls
     would triple cost/latency for no benefit.
   - Update the `quiz` row in `ai_provider_config` to request the array format and
     distinct aspects of the step content (deploy alongside the code change; keep
     backward parsing: if the model returns a single object, wrap it in a list).
   - Persist **one `quiz_sessions` row per question** (keeps `get_hint`/`submit_answer`
     and their endpoints unchanged), each tagged with journey_id/step_id and a shared
     `quiz_set_id` (add column or reuse the first session's id as the set id).
   - Adaptive difficulty: compute once per set (per-question would oscillate).
2. `POST /quiz/{quiz_id}/submit` unchanged per question, but writes
   journey_id/step_id/session_id into `quiz_results`.
3. New: `GET /api/v1/quiz/step-status/{journey_id}/{step_id}` → 
   `{ passed: bool, correct: int, total: int }` derived from `quiz_results`.
4. **Server-side gate:** in `progress.py mark_step_complete` (after the Phase 2 order
   check), require a passing quiz record for (uid, journey_id, step_id); otherwise
   **412 Precondition Failed** `{"detail": "quiz_not_passed"}`.
   - Skip the gate when the step can't be resolved (same permissive fallback as
     Phase 2) and for legacy completions (no backfill).
   - Budget interaction: quiz generation goes through the same token-budget pipeline
     as step content (402 path) — a budget-exhausted user must see the existing
     upgrade prompt, not a dead end.

## 3.3 Frontend — quiz flow gates completion

1. **Remove auto-complete-on-view** (`StepNode.tsx:47`): viewing content no longer
   calls `onToggle`. This inverts the documented "viewing = completing" behaviour —
   update `frontend/CLAUDE.md` accordingly.
2. `QuizCard` → multi-question flow:
   - Auto-load the quiz set when step content renders (no "take quiz" opt-in).
   - Progress header "Question 1 of 3"; reuse existing question/hint/feedback UI per
     question; advance on submit.
   - End state: pass (≥2/3) → call `completeStep(step.id)` (Phase 2 function), show
     success + unlock animation; fail → "Review the lesson and retry" button that
     regenerates a fresh set.
3. Step card shows a "Quiz: 2/3 to pass" chip so the requirement is visible before
   expanding.
4. Guests: quizzes require auth today (`get_required_user` on quiz endpoints). Either
   (a) keep guests on view-to-complete locally, or (b) show a sign-in prompt at the
   quiz. Recommend (a) — guests lose nothing they had. (Decision #2.)

## Tests

- Backend: quiz set returns N distinct questions; step-status math; complete-step
  without pass → 412; with pass → 200; budget-exhausted quiz generation → 402.
- Manual: full step flow — read → quiz → pass → step completes → next unlocks;
  fail path retries with new questions; un-passed step never completes via API.

## Acceptance

- No step can be completed (UI or API) without a passing 2–3-question quiz.
- Existing standalone quiz behaviour (Explore page concepts) is unchanged.
