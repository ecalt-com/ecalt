-- Quiz quality log — records inline judge results for every generated question (Phase 6)
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

-- Monitoring view: pass rate by difficulty (last 7 days)
CREATE OR REPLACE VIEW quiz_quality_7d AS
SELECT
  difficulty,
  COUNT(*)                                                      AS total,
  SUM(CASE WHEN judge_ok THEN 1 ELSE 0 END)                    AS passed,
  ROUND(100.0 * SUM(CASE WHEN judge_ok THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 1)                              AS pass_pct,
  SUM(CASE WHEN was_retried THEN 1 ELSE 0 END)                 AS retried
FROM quiz_quality_log
WHERE logged_at > now() - interval '7 days'
GROUP BY difficulty
ORDER BY difficulty;
