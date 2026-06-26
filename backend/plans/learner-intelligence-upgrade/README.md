# Learner Intelligence Upgrade

## Origin

Three issues surfaced from a PhD-level user testing the platform on her own research domain.
She could identify hallucinations and found the quizzes too easy — both valid signals.

---

## The Three Problems

### Problem 1 — Journey Hallucination (no confirmation)

When a user types a very specific query (e.g., a named scientific thesis), the AI
sometimes generates a plausible-sounding but wrong journey. The journey is persisted
to the database and steps start pre-warming **before the user even reads it**.

By the time the user notices it's off, budget has been spent and a bad journey is saved.
After 2–3 sparks (rephrasing), the AI gets it right — so the understanding is possible,
but there's no checkpoint to catch the first hallucinated attempt.

**Root cause:** `POST /api/v1/explore` generates, persists, and pre-warms in one shot.

### Problem 2 — Course depth ignores who the learner is

A PhD researcher with 5 years in a field gets the same journey depth and quiz difficulty
as someone who Googled the topic for the first time. The content is structurally good but
diluted for a domain expert. For a curious IT professional, it might be appropriate.

**Root cause:** `generate_journey()` receives only `question` + `age_group`. No awareness
of profession, purpose, or self-reported expertise.

### Problem 3 — Quiz gives binary pass/fail, blocks progress, ignores near-misses

A user who gives a "95% correct" answer — missing just one nuance — gets marked
INCORRECT, blocked from the next step, and shown a flat explanation. This is demotivating
and inaccurate. The system also throws away nuanced analytics (what was missed, how close
the answer was) that could power a meaningful Mind Signature.

**Root cause:** `submit_answer()` returns binary `is_correct`. The quiz gate blocks the
next step on any wrong-answer session. No mid-tier verdict or analytics signal.

---

## The Fix — Five Phases

| Phase | What changes | Effort |
|-------|-------------|--------|
| [Phase 1 — Journey Confirmation Gate](phase-1-journey-confirmation.md) | Preview before persist; reprompt if wrong | Backend + Frontend |
| [Phase 2 — Learner Intent Profiling](phase-2-learner-intent-profiling.md) | Profession + purpose → injected into prompts | Backend + Frontend + DB |
| [Phase 3 — Nuanced Quiz Feedback & Analytics](phase-3-quiz-feedback-analytics.md) | 3-tier verdict, no gate blocking, Mind Signature analytics | Backend + Frontend + DB |
| [Phase 4 — Journey Test Script](phase-4-journey-test-script.md) | Real OpenAI test harness across 4 batches | Backend script |
| [Phase 5 — Smart Generation: History Context + Structured Refinement](phase-5-smart-generation.md) | Completion history injected into generation; refinement panel instead of starting from scratch | Backend + Frontend |

Phases are independent — each can ship alone without the others.
Phase 5A (learning context) is a safe backend-only change that can ship without Phase 5B (refinement panel).

---

## Success Signal

- Phase 1: Zero "wrong journey" complaints from users who engage with the confirmation step.
- Phase 2: Domain-expert users report quiz difficulty feels appropriate to their level.
- Phase 3: Users report feeling understood rather than graded; Mind Signature page shows richer per-concept analytics.
- Phase 5: Users with 3+ completed journeys get harder/deeper journeys without re-explaining mastered concepts; refinement loop (≥2 previews) ends in confirm rather than abandon.

---

## Files Touched Across All Phases

```
backend/
  app/api/v1/endpoints/explore.py        — preview endpoint
  app/api/v1/endpoints/quiz.py           — verdict response, gate removal
  app/api/v1/endpoints/users.py          — learner profile endpoints
  app/services/ai_service.py             — learner_profile injection in prompts
  app/services/quiz_service.py           — 3-tier grading, concept analytics write
  app/services/mind_signature_service.py — consume concept_interactions for 27 dims
  app/models/schemas.py                  — LearnerProfile, JourneyPreview, VerdictResponse

frontend/
  src/pages/Explore.tsx                  — confirmation UI, intent modal
  src/lib/api.ts                         — previewJourney(), confirmJourney() wrappers
  src/lib/types.ts                       — LearnerProfile, QuizVerdict types

migrations/
  NNN_journey_preview_cache.sql          — ephemeral preview cache table
  NNN_learner_profiles.sql               — profession, purpose, expertise_level
  NNN_concept_interactions.sql           — per-answer analytics for Mind Signature
```
