# Phase 5 — Systematic Evaluation (50–100 Subjects)

**Duration:** 2–3 days (running + iteration)  
**Goal:** Run the full pipeline across a diverse subject set, let Claude
identify remaining failure patterns, and do one targeted iteration on
whichever prompt is still causing failures.

This is the phase the user described: "test systematically 50–100 subjects
and run it by Claude — it would rectify it."

---

## What "Run by Claude" Means Concretely

Not just scoring — a diagnosis pass. After collecting all results, feed
the failure cases to Claude in a structured batch and ask it to identify
prompt rules that would prevent those specific failures.

---

## Step 1 — Select 50–100 Diverse Subjects

Good diversity means the evaluation catches failure modes across:

| Dimension | Values to cover |
|-----------|----------------|
| Step type | concept, practice, challenge, explore |
| Journey difficulty | beginner, intermediate, advanced |
| Domain | science, history, tech, math, arts, economics, philosophy |
| Age group | kids, teens, adults |
| Content length after Phase 2 | short (~400w), medium (~550w), long (~800w) |

If the DB has enough warmed content, pull from there. Otherwise regenerate
content for a curated list of 50–100 journey steps spanning these dimensions.

Suggested test set construction:
```sql
SELECT s.journey_id, s.step_id, j.question, j.difficulty, j.age_group,
       j.tags, s.content
FROM step_content s
JOIN journeys j ON j.id = s.journey_id
WHERE array_length(s.quiz_anchors::text::jsonb, 1) > 0
ORDER BY j.difficulty, j.age_group, random()
LIMIT 100;
```

---

## Step 2 — Full Pipeline Run

For each of the 100 steps, run the complete updated pipeline:
1. Content from DB (with anchors from Phase 4)
2. Generate quiz set (3 questions, with Phase 1+2+3+4 changes active)
3. Run answerability judge on each question
4. Record: step_id, step_type, journey_difficulty, age_group, domain tags,
   question, difficulty_level, answerable_score, gap

This produces 300 scored question records.

---

## Step 3 — Aggregate and Identify Failure Clusters

```python
# scripts/evaluate_quiz_alignment.py --phase 5 --cluster-failures

failures = [r for r in results if r["answerable_score"] < 0.8]
print(f"Total failures: {len(failures)} / 300 ({len(failures)/3:.0f}%)")

# Cluster by gap pattern (simple keyword grouping + Claude summary)
gaps = [f["gap"] for f in failures]
```

Send failures to Claude for pattern diagnosis:

```
DIAGNOSIS PROMPT:
Here are {N} content+quiz pairs where the quiz question scored < 0.8
answerability. Each has a "gap" field describing what the content doesn't
cover that the question requires.

Gaps:
{gaps joined, one per line}

Identify:
1. The 3–5 most common gap PATTERNS (abstract the pattern, not just list gaps)
2. For each pattern: is it caused by the CONTENT prompt, the QUIZ prompt,
   or both?
3. For each pattern: write ONE specific rule (1–2 sentences) that would
   prevent this failure if added to the responsible prompt.
4. Rank patterns by frequency and impact.

Be concrete. No generic advice like "be more specific". Name the exact
rule with example wording.
```

---

## Step 4 — Targeted One-Round Iteration

Take Claude's top 3 rules. Add them to the appropriate prompt(s). Do NOT
change everything — only add the rules for the top 3 patterns.

Re-run the evaluator on just the failed questions (not all 300) to verify
that the new rules fix those specific failures without introducing regressions.

If one round reduces failures by 50%+, ship it. If not, run one more
targeted iteration on the remaining top pattern.

**Stop condition:** ≥88% of questions score ≥0.8 across the full 100-step
test set, OR you've done 2 targeted iterations (diminishing returns signal).

---

## Step 5 — Regression Check

After the final iteration, re-run the ORIGINAL Phase 0 test set
(`alignment_baseline.json`) against the fully updated prompts.

This verifies:
- The improvements hold on the original 87 steps, not just the new 100
- No regression on previously passing questions

---

## Step 6 — Document Final Prompt State

Once the evaluation target is reached:
1. Record the final prompt versions (content + quiz) in this plans folder
2. Update both DB rows via `set_style_prompt`
3. Record the final answerability score in the README.md table

---

## Expected Outcome

After Phase 5:
- Overall answerability ≥ 88%
- No step type below 80%
- No journey difficulty level below 78%
- Remaining failures (~12%) are genuinely ambiguous edge cases, not
  systematic prompt failures
