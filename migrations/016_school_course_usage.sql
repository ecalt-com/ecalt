-- 016_school_course_usage.sql
-- Per-course AI spend attribution for schools (SC-706). The existing
-- school_usage table is school-wide only; this breaks the monthly pool down by
-- course (journey) so the usage dashboard can show spend per course and, by
-- rolling courses up through assignments, per class. Written alongside the
-- school-wide row by subscription_service.record_school_usage / record_usage
-- whenever a journey id is in context (course building + student tutor/quiz).
-- Additive and idempotent.

CREATE TABLE IF NOT EXISTS public.school_course_usage (
  school_id      uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  journey_id     text NOT NULL,
  period_start   date NOT NULL,
  cost_cents     numeric NOT NULL DEFAULT 0,
  input_tokens   bigint NOT NULL DEFAULT 0,
  output_tokens  bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (school_id, journey_id, period_start)
);

CREATE INDEX IF NOT EXISTS school_course_usage_period_idx
  ON public.school_course_usage (school_id, period_start);

ALTER TABLE public.school_course_usage ENABLE ROW LEVEL SECURITY;
