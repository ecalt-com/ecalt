# Phase 1 — Mechanical Fixes

**Duration:** 1 day  
**Goal:** Fix the bugs that are independent of prompt quality. These cause
misalignment even if both prompts were perfect.

Expected score lift: **+15–25 percentage points** from truncation fix alone.

---

## Fix 1 — Fetch Full Content From DB in Quiz Set Generation

**File:** `app/services/quiz_service.py`  
**Root cause:** Quiz context capped at 1500 chars; client may send truncated
content; quiz sees only ~60% of the step.

In `generate_quiz_set`, when `journey_id` + `step_id` are present, fetch the
authoritative full content directly from the `step_content` table:

```python
async def generate_quiz_set(
    uid: str,
    concept: str,
    context: str,           # client-provided fallback
    base_depth: str = "exploratory",
    num_questions: int = 3,
    journey_id: str | None = None,
    step_id: str | None = None,
    step_type: str = "concept",   # NEW param — see Fix 2
) -> tuple[dict, int, int]:

    # ── Fetch authoritative content from DB when available ────────────────
    if journey_id and step_id:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT content FROM step_content "
                        "WHERE journey_id = %s AND step_id = %s",
                        (journey_id, step_id),
                    )
                    row = cur.fetchone()
                    if row and row["content"]:
                        context = row["content"]
        except Exception as e:
            logger.debug("content fetch failed, using client context: %s", e)
```

Also raise the context truncation limit from `1500` → `4000` chars in both
`generate_quiz` and `generate_quiz_set` (for cases where DB fetch is
unavailable):

```python
# line ~220 and ~321
f"Context from learning session:\n{context[:4000]}"
```

---

## Fix 2 — Step-Type Difficulty Cap

**File:** `app/services/quiz_service.py`  
**Root cause:** A "concept" (first-exposure) step gets the same adaptive
difficulty as a "challenge" (mastery) step. The adaptive engine can push to
"deep" or "research" even when the content is introductory.

Add a constant and clamp after `get_adaptive_difficulty`:

```python
# After existing _HOLD_MAP line:
_STEP_TYPE_DIFFICULTY_CAP = {
    "concept":   "exploratory",  # first exposure → apply but not edge cases
    "practice":  "deep",         # doing it → mechanism questions are fair
    "challenge": "research",     # mastery check → full range OK
    "explore":   "research",     # frontier thinking → full range OK
}
```

In `generate_quiz_set`, after calling `get_adaptive_difficulty`:

```python
difficulty = get_adaptive_difficulty(uid, base_depth)

# Clamp to step-type ceiling
cap = _STEP_TYPE_DIFFICULTY_CAP.get(step_type, "exploratory")
cap_idx = _DIFFICULTY_ORDER.index(cap)
if _DIFFICULTY_ORDER.index(difficulty) > cap_idx:
    difficulty = cap
    logger.debug(
        "quiz.difficulty_capped step_type=%s cap=%s", step_type, cap
    )
```

### Wire `step_type` through the endpoint

**File:** `app/api/v1/endpoints/quiz.py`

```python
class QuizGenerateRequest(BaseModel):
    concept: str
    context: str
    base_depth: str = "exploratory"
    journey_id: Optional[str] = None
    step_id: Optional[str] = None
    num_questions: Optional[int] = None
    step_type: str = "concept"          # NEW — defaults to most conservative
```

Pass it through:

```python
quiz, in_tok, out_tok = await generate_quiz_set(
    uid=uid,
    concept=body.concept.strip(),
    context=body.context.strip(),
    base_depth=body.base_depth,
    num_questions=body.num_questions or 3,
    journey_id=body.journey_id,
    step_id=body.step_id,
    step_type=body.step_type,           # NEW
)
```

The frontend already knows the step type when it triggers a quiz — it just
needs to pass it.

---

## Fix 3 — Hard Content Boundary Rule in Quiz Prompt

**File:** `app/services/provider_service.py` → `_QUIZ_STYLE_DEFAULT`  
Also update the DB row via `set_style_prompt`.

Add the following block **before** the THREE LAWS section:

```
CONTENT BOUNDARY — NON-NEGOTIABLE:
You may ONLY ask about concepts, facts, or mechanisms that are EXPLICITLY
STATED in the context provided above.

Do NOT:
- Infer beyond what is written
- Ask about implications the content never draws
- Reference named techniques, formulas, or people not mentioned in context
- Ask "why does X fail" if the context never describes how X works

If generating your ideal question would require knowledge beyond the context,
SIMPLIFY the question until it is fully answerable from the content alone.
A technically brilliant question that cannot be answered from this content
is a failed question.
```

---

## Validation

After implementing all three fixes, re-run `scripts/evaluate_quiz_alignment.py`
against the same 87 steps from Phase 0.

Expected movement:
- Fix 1 (full context) alone: +15–20pp on deep/research questions
- Fix 2 (difficulty cap) alone: +5–10pp on concept steps
- Fix 3 (boundary rule) alone: +5–10pp across all

Re-run, record as `scripts/alignment_phase1.json`. Compare to baseline.
