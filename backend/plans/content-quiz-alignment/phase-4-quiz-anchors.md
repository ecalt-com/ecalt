# Phase 4 — Shared Contract (Quiz Anchors)

**Duration:** 2–3 days  
**Goal:** Eliminate the root architectural problem — content and quiz are
generated independently with no shared understanding of what the step teaches.

Phases 2 and 3 improve both prompts in isolation. Phase 4 connects them:
when content is generated, it also produces a compact list of explicitly
testable facts. The quiz generator draws from that list instead of
inferring from free-form prose.

---

## The Concept

```
Current (disconnected):

  generate_step_content() ─────► content prose ───────────────────────►
                                                                        ↓
  generate_quiz_set()  ◄──────────────────────────── context[:4000] ◄──┘
  (infers from prose, may go beyond it)


Phase 4 (connected via anchors):

  generate_step_content() ─────► content prose ──────────────────────►
                          │
                          └────► quiz_anchors [list of testable facts]─►
                                                                        ↓
  generate_quiz_set()  ◄──── context + anchors (must draw from list) ◄─┘
  (anchored to explicitly stated facts — cannot invent beyond)
```

---

## Step 1 — Extend the Content Output Contract

**File:** `app/services/ai_service.py`

Update `_STEP_CONTENT_CONTRACT` to return a second field:

```python
_STEP_CONTENT_CONTRACT = """\
Return ONLY a valid JSON object with this exact structure:
{
  "content": "...",
  "quiz_anchors": [
    {
      "fact": "One sentence stating something explicitly in the content above",
      "testable_as": "application | implication | exception | connection",
      "hint_direction": "One phrase pointing toward the answer without
                         stating it — used for hint generation"
    }
  ]
}

QUIZ ANCHOR RULES:
- Generate exactly 3–5 anchors
- Each anchor must be:
    (a) A specific, unambiguous fact stated in your content — not implied
    (b) Falsifiable: there is a clearly wrong answer possible
    (c) Different from the other anchors — no two anchors test the same idea
- Do NOT anchor vague or definitional statements
  BAD:  "Encryption is important for security"
  GOOD: "AES-256 encryption would take longer than the age of the universe
         to brute-force with current hardware"
- testable_as values:
    application → "If X, what happens to Y?"
    implication → "Given X, what does this mean for Z?"
    exception   → "Under what conditions does X break down?"
    connection  → "How does X relate to [another concept in this content]?"
"""
```

Update `generate_step_content` to parse and return anchors:

```python
async def generate_step_content(...) -> tuple[str, list[dict], int, int]:
    """Returns (content, quiz_anchors, in_tok, out_tok)."""
    ...
    data = json.loads(raw[start:end])
    content = data["content"]
    quiz_anchors = data.get("quiz_anchors", [])
    return content, quiz_anchors, in_tok, out_tok
```

Update all callers (`warm_journey_steps`, the journeys endpoint) to handle
the new return value.

---

## Step 2 — Store Anchors in the DB

**Migration:** `../migrations/NNN_add_quiz_anchors_to_step_content.sql`

```sql
ALTER TABLE step_content
ADD COLUMN IF NOT EXISTS quiz_anchors JSONB DEFAULT '[]'::jsonb;
```

Update the `INSERT` / `ON CONFLICT` in `warm_journey_steps`:

```sql
INSERT INTO step_content (journey_id, step_id, content, quiz_anchors)
VALUES (%s, %s, %s, %s::jsonb)
ON CONFLICT (journey_id, step_id) DO NOTHING
```

---

## Step 3 — Feed Anchors to Quiz Generation

**File:** `app/services/quiz_service.py`

In `generate_quiz_set`, after fetching the full content from `step_content`,
also fetch anchors:

```python
if journey_id and step_id:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content, quiz_anchors FROM step_content "
                "WHERE journey_id = %s AND step_id = %s",
                (journey_id, step_id),
            )
            row = cur.fetchone()
            if row:
                context = row["content"] or context
                anchors = row["quiz_anchors"] or []
```

Build an anchor block for the prompt:

```python
def _format_anchors(anchors: list[dict]) -> str:
    if not anchors:
        return ""
    lines = ["QUIZ ANCHORS — draw each question from one of these facts:"]
    for i, a in enumerate(anchors, 1):
        lines.append(
            f"  Anchor {i} [{a.get('testable_as', 'application')}]: "
            f"{a.get('fact', '')}"
        )
    lines.append(
        "Each question must test a DIFFERENT anchor. "
        "Do not ask about anything not listed here or explicitly in the context."
    )
    return "\n".join(lines)
```

Inject into user_content:

```python
anchor_block = _format_anchors(anchors)
user_content = (
    f"Concept: {concept}\n"
    f"{age_line}"
    f"{anchor_block}\n\n" if anchor_block else ""
    f"{recent_summary}\n\n"
    f"OVERRIDE FOR THIS REQUEST: generate exactly {num_questions} DISTINCT "
    f"questions with ESCALATING DIFFICULTY:\n"
    f"{difficulty_spec}\n"
    ...
    f"Context:\n{context[:4000]}"
)
```

---

## Step 4 — Backfill Existing Step Content

Many steps already have content but no anchors. Backfill:

`scripts/backfill_quiz_anchors.py`:

```
For each row in step_content WHERE quiz_anchors = '[]':
  1. Read the existing content
  2. Call Claude with a simple extraction prompt:
     "Extract 3–5 quiz-testable facts from this content.
      Each fact must be explicitly stated in the content.
      Return JSON array: [{"fact":..., "testable_as":..., "hint_direction":...}]"
  3. UPDATE step_content SET quiz_anchors = %s WHERE id = %s
```

This runs once as a background script, not on the hot path.

---

## Validation

Re-run the alignment evaluator with Phase 4 active. The key metric is:

- **Anchor coverage**: What % of generated questions reference a concept
  that matches one of the anchors? (Should be 90%+)
- **Answerability score**: Should reach **82–88%** after Phase 4

Also check: do anchors themselves remain vague or generic in practice?
Sample 20 anchor sets manually. If anchors are too abstract
(e.g., "Energy is important"), tighten the BAD/GOOD examples in the anchor
generation prompt.

Record as `scripts/alignment_phase4.json`.
