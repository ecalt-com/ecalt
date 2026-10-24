-- Schools: student AI budget enforcement + login-abuse hardening.
-- Follows 014_schools.sql. Additive and idempotent — safe to apply before the
-- backend deploys. See backend/plans/school-courses/REVIEW.md (H1, M2).
--
-- 1. Per-student daily AI counters back the per-student daily caps
--    (school_settings.student_daily_tutor_messages / _quiz_sets). The monthly
--    school spend is read from school_usage (written by record_usage); these
--    counters give O(1) daily-cap reads and writes on the hot path.
-- 2. A partial index makes the class sign-in throttle count (which scans
--    school_audit_log on every attempt) bounded, and a retention job prunes the
--    high-volume failed-login rows (scheduler.prune_school_audit_log).

-- ── 1. Per-student daily usage counters ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.school_student_daily_usage (
  student_uid     text NOT NULL REFERENCES public.users(uid) ON DELETE CASCADE,
  school_id       uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  day             date NOT NULL,
  tutor_messages  integer NOT NULL DEFAULT 0 CHECK (tutor_messages >= 0),
  quiz_sets       integer NOT NULL DEFAULT 0 CHECK (quiz_sets >= 0),
  PRIMARY KEY (student_uid, day)
);
CREATE INDEX IF NOT EXISTS school_student_daily_usage_school_idx
  ON public.school_student_daily_usage (school_id, day);

ALTER TABLE public.school_student_daily_usage ENABLE ROW LEVEL SECURITY;

-- ── 2. Sign-in throttle index ─────────────────────────────────────────────────

-- The class throttle counts 'student.sign_in_failed' rows per class in a short
-- window; this partial index keeps that count cheap as the audit log grows.
CREATE INDEX IF NOT EXISTS school_audit_log_signin_fail_idx
  ON public.school_audit_log (school_id, target_id, created_at)
  WHERE action = 'student.sign_in_failed';
