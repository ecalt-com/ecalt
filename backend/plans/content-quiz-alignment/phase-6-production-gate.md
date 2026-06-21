# Phase 6 — Production Quality Gate

**Duration:** 1–2 days  
**Goal:** Catch misaligned questions at generation time before any user sees
them. A lightweight real-time judge runs after generation; failing questions
are regenerated once with tighter constraints.

This is the safety net, not the primary fix. Phases 1–5 do the heavy lifting.
Phase 6 catches the residual ~12% that systematic prompt improvement doesn't
eliminate.

---

## Design Principles

- **Fast and cheap:** Use gpt-4.1-nano (or claude-haiku) for the judge —
  latency budget is ~300ms extra per question
- **One retry only:** If the regenerated question still fails, serve it
  anyway and log it — never block the user
- **Log everything:** Every judge result goes to a table for ongoing
  monitoring. This is how you detect future prompt drift

---

## Step 1 — Inline Judge in `generate_quiz_set`

**File:** `app/services/quiz_service.py`

After generating and parsing the question list, before storing to DB:

```python
_INLINE_JUDGE_SYSTEM = """\
You are a quiz fairness checker. Given step content and a quiz question,
determine if the question is answerable by a learner who read ONLY the content.
Return ONLY JSON: {"ok": true} or {"ok": false, "issue": "one sentence"}"""


async def _check_answerable(content: str, question: str, answer: str) -> tuple[bool, str]:
    """Returns (is_ok, issue_description). Fast, cheap call."""
    try:
        user_msg = (
            f"Content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Question: {question}\n"
            f"Expected answer: {answer}"
        )
        raw, _, _, _ = await complete_text(
            interaction_type="quiz",   # reuses quiz config / model
            system=_INLINE_JUDGE_SYSTEM,
            user_content=user_msg,
            max_tokens=60,
        )
        start = raw.find("{"); end = raw.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            return bool(data.get("ok", True)), data.get("issue", "")
    except Exception as e:
        logger.debug("inline_judge failed: %s", e)
    return True, ""  # fail open — never block on judge error
```

In `generate_quiz_set`, after parsing `questions`, before the DB insert loop:

```python
checked_questions = []
for q in questions:
    ok, issue = await _check_answerable(
        content=context,
        question=q.get("question", ""),
        answer=q.get("correct_answer", ""),
    )
    if not ok:
        logger.info(
            "quiz.inline_judge_failed concept=%.60s issue=%s — retrying",
            concept, issue,
        )
        # One retry with explicit constraint
        retry_prompt = (
            f"The previous question was not answerable from the content alone.\n"
            f"Issue: {issue}\n\n"
            f"Generate a REPLACEMENT question for anchor concept '{concept}' "
            f"at {q.get('difficulty', difficulty)} depth that tests only what "
            f"is explicitly in the context. Do not repeat the same question.\n"
            f"Return ONE question object in the same JSON format."
        )
        # ... call complete_text with retry_prompt as user content ...
        # parse the single replacement; if it also fails judge, keep original
        checked_questions.append(replacement or q)
    else:
        checked_questions.append(q)

questions = checked_questions
```

---

## Step 2 — Quiz Quality Log Table

**Migration:** `../migrations/NNN_quiz_quality_log.sql`

```sql
CREATE TABLE IF NOT EXISTS quiz_quality_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  uid             TEXT NOT NULL,
  quiz_session_id UUID REFERENCES quiz_sessions(id),
  concept         TEXT NOT NULL,
  journey_id      TEXT,
  step_id         TEXT,
  question        TEXT NOT NULL,
  difficulty      TEXT NOT NULL,
  judge_ok        BOOLEAN NOT NULL,
  judge_issue     TEXT,
  was_retried     BOOLEAN NOT NULL DEFAULT FALSE,
  logged_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON quiz_quality_log (logged_at DESC);
CREATE INDEX ON quiz_quality_log (judge_ok, difficulty);
```

Log each judged question (whether OK or not) to this table. This gives you:
- Real-time failure rate in production
- Which difficulty levels / step types still fail most
- Whether prompt changes improved things after deployment

---

## Step 3 — Admin Monitoring Query

A simple SQL view for the admin dashboard or ad-hoc monitoring:

```sql
-- Overall pass rate by difficulty (last 7 days)
SELECT
  difficulty,
  COUNT(*) AS total,
  SUM(CASE WHEN judge_ok THEN 1 ELSE 0 END) AS passed,
  ROUND(100.0 * SUM(CASE WHEN judge_ok THEN 1 ELSE 0 END) / COUNT(*), 1)
    AS pass_pct,
  SUM(CASE WHEN was_retried THEN 1 ELSE 0 END) AS retried
FROM quiz_quality_log
WHERE logged_at > now() - interval '7 days'
GROUP BY difficulty
ORDER BY difficulty;
```

Alert threshold: if `pass_pct` for any difficulty drops below 70% over a
rolling 24-hour window, investigate — it means a prompt or model change has
degraded quality.

---

## What This Phase Does NOT Do

- Does not block quiz generation on failure — fail open always
- Does not run the judge for single-question quizzes (`generate_quiz`) to
  keep latency acceptable for the chat-driven flow
- Does not automatically update prompts — the log is for human review and
  targeted iteration (Phase 5 can be re-run periodically)

---

## Expected Outcome

- Real-time visibility into question quality in production
- Residual failure rate after retry: < 8%
- Zero cases where users receive a question that requires knowledge not in
  the step content (any that slip through are logged and addressable)
- A feedback loop: production data → periodic Phase 5 re-run → prompt
  improvement → lower failure rate over time
