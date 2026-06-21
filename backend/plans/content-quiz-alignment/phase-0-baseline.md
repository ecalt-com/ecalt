# Phase 0 — Baseline Measurement

**Duration:** 1 day  
**Goal:** Get a number before touching anything. Every subsequent phase is
validated by moving this number.

---

## What to Build

`scripts/evaluate_quiz_alignment.py`

### Step 1 — Select test steps

Pull 50–100 steps from the DB with existing warmed content. Ensure diversity:

```sql
SELECT
  s.journey_id, s.step_id, s.content,
  j.difficulty  AS journey_difficulty,
  j.age_group,
  j.steps       AS journey_steps_json   -- to extract step_type
FROM step_content s
JOIN journeys j ON j.id = s.journey_id
ORDER BY random()
LIMIT 100;
```

Extract `step_type` from the journey's `steps` JSONB array by matching `step_id`.

Aim for roughly:
- 40% concept steps, 25% practice, 20% challenge, 15% explore
- 40% beginner journeys, 35% intermediate, 25% advanced

### Step 2 — Generate quiz (using current prompts, no changes)

For each step, call `generate_quiz_set` with 3 questions. Use the full stored
content as context (not the truncated client-sent version — this isolates
prompt quality from the truncation bug).

### Step 3 — Run the answerability judge

For each generated question, make a separate Claude call:

```
JUDGE SYSTEM PROMPT:
You are an educational alignment reviewer. Your only job is to score whether
a quiz question is fair given what the content teaches.

JUDGE USER PROMPT:
Step content:
---
{full_content}
---

Quiz question: {question}
Expected answer: {correct_answer}

A learner read ONLY the content above — no textbook, no internet, no prior
knowledge of this topic.

Score this question on two dimensions:

answerable_score (float 0.0–1.0):
  1.0 = Fully and clearly answerable from the content alone
  0.7 = Mostly answerable; content hints at it but is vague
  0.5 = Half answerable; requires one small inference not in content
  0.2 = Barely answerable; mostly requires outside knowledge
  0.0 = Completely unanswerable from this content

gap (string, required if score < 0.8):
  In one sentence: exactly what specific fact, mechanism, or detail does
  the content NOT cover that this question requires?
  Be concrete. Not "more depth needed" — name the specific missing thing.
  e.g. "Content says mitochondria make energy but never explains ATP or
  oxidative phosphorylation, which the question requires."

Return ONLY valid JSON:
{"answerable_score": 0.7, "gap": "..."}
```

Use a fast, cheap model (gpt-4.1-nano or claude-haiku) for the judge — it's
doing a straightforward binary comparison, not creative generation.

### Step 4 — Record results

Write to `scripts/alignment_baseline.json`:

```json
[
  {
    "step_id": "...",
    "journey_id": "...",
    "step_type": "concept",
    "journey_difficulty": "beginner",
    "age_group": "adults",
    "question_1": {
      "question": "...",
      "correct_answer": "...",
      "difficulty": "exploratory",
      "answerable_score": 0.4,
      "gap": "Content never explains the mechanism, only names it"
    },
    "question_2": { ... },
    "question_3": { ... },
    "avg_score": 0.5
  }
]
```

### Step 5 — Print summary

```
=== ALIGNMENT BASELINE ===
Steps evaluated:          87
Questions evaluated:      261

Overall answerable ≥0.8:  38%  (99/261)

By difficulty:
  surface:      72%
  exploratory:  41%
  deep:         18%
  research:      9%

By step type:
  concept:      29%
  practice:     44%
  challenge:    51%
  explore:      38%

Top gap patterns:
  1. Content names concept but never explains mechanism (34% of failures)
  2. Question probes edge case; content only covers happy path (28%)
  3. Question asks for implication; content states fact without consequence (22%)
  4. Content too short; topic barely introduced before ending (11%)
  5. Other (5%)
```

---

## Output

- `scripts/alignment_baseline.json` — raw results, kept for comparison
- Summary printed to stdout
- The **overall answerable ≥0.8 %** is your baseline number

This number will be compared after every subsequent phase. Do not change any
prompt or code until this script has run and the baseline is recorded.
