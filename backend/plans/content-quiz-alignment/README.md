# Content–Quiz Alignment Plan

## The Problem

Users report that step content feels like an overview while quiz questions probe
fine-grained details. The quiz is intellectually rigorous but unfair because the
content never taught what the quiz is testing.

## The Fix Frame

> **Content is the floor. The quiz can only be as good as what the content
> teaches. Raise the floor first, then nail the quiz to it.**

The wrong fix is weakening the quiz to match shallow content. The right fix is:

```
Current:
  Content  ──[overview, 380-500 words flat]──────────────────────────►
  Quiz     ──────────────────────────────────[detail, adaptive]───────►
                                              ↑ gap here

Target:
  Content  ────────────[deeper, testable, step-type-aware]────────────►
  Quiz     ────────────[anchored to what content explicitly covers]────►
                        ↑ aligned at a higher level of quality
```

---

## Root Causes (5 layers, all must be fixed)

| # | Cause | Where |
|---|-------|--------|
| 1 | Content targets 380–500 words **flat** — no mechanism, no worked example, no "why X fails" | `_STEP_CONTENT_STYLE_DEFAULT` in `provider_service.py` |
| 2 | Quiz context truncated at **1500 chars** — quiz sees only ~60% of even the shallow content | `quiz_service.py` lines 220, 321 |
| 3 | Quiz difficulty escalates from **past performance** with no awareness of current content depth | `get_adaptive_difficulty()` in `quiz_service.py` |
| 4 | Content and quiz share **no contract** — generated independently, no agreed list of what the step teaches | architecture gap |
| 5 | `step_type` (concept / practice / challenge / explore) is **ignored** by quiz — first-exposure steps get same treatment as mastery steps | `generate_quiz_set()` in `quiz_service.py` |

---

## Phases

- [Phase 0 — Baseline Measurement](phase-0-baseline.md)
- [Phase 1 — Mechanical Fixes](phase-1-mechanical-fixes.md)
- [Phase 2 — Content Prompt Upgrade](phase-2-content-prompt.md)
- [Phase 3 — Quiz Prompt Tightening](phase-3-quiz-prompt.md)
- [Phase 4 — Shared Contract (Quiz Anchors)](phase-4-quiz-anchors.md)
- [Phase 5 — Systematic Evaluation (50–100 subjects)](phase-5-evaluation.md)
- [Phase 6 — Production Quality Gate](phase-6-production-gate.md)

---

## Success Metric

Run the alignment evaluator (`scripts/evaluate_quiz_alignment.py`) after each
phase. Track **answerability score**: the fraction of quiz questions that a
learner who read only the step content could correctly answer.

| Milestone | Target |
|-----------|--------|
| Baseline (before any changes) | ~35–50% |
| After Phase 1 + 2 + 3 | ~65–75% |
| After Phase 4 | ~80–85% |
| After Phase 5 iteration | ≥ 88% |
| Production gate threshold | 80% enforced per question |

---

## Files Touched Across All Phases

```
app/services/quiz_service.py          — context fetch, difficulty cap, anchor injection
app/services/ai_service.py            — content contract, quiz_anchors field
app/services/provider_service.py      — _STEP_CONTENT_STYLE_DEFAULT, _QUIZ_STYLE_DEFAULT
app/api/v1/endpoints/quiz.py          — step_type param
app/models/schemas.py                 — QuizAnchor model (if typed)
scripts/evaluate_quiz_alignment.py    — NEW: evaluation harness
../migrations/NNN_quiz_anchors.sql    — NEW: quiz_anchors column on step_content
```
