# Daily Spark Prompt

**Interaction type:** `daily_spark`
**Default model:** `gpt-4.1-nano`
**Source:** `app/services/spark_service.py` — inline in `generate_daily_spark()` (line 140)
**Called by:** `generate_daily_spark()` — once per user per day, result cached in `daily_sparks` table

---

## System prompt

```
Generate a single fascinating curiosity question that would make someone want to learn immediately.
Return ONLY the question — nothing else, no quotes, no preamble.
```

## User prompt template

```
Topics the learner loves: {topic_hint}
```

Where `topic_hint` is up to 3 of the user's saved interest topics from `user_interests`, falling back to `"science, history, or technology"` if none are set.

## Output

Raw string — the question text (quotes and leading/trailing whitespace stripped).
Cached in `daily_sparks` table keyed by `(uid, generated_at date)`.
Max tokens: `120`.
