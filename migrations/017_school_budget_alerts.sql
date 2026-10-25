-- SC-504: per-month dedup markers for the 80% / 100% school-budget admin alert
-- emails. Additive and idempotent — safe to apply before the backend deploys.
-- A threshold's column is stamped the first (and only) time that threshold is
-- crossed in a month; the alert email fires only for the writer that stamps it.

ALTER TABLE public.school_usage
  ADD COLUMN IF NOT EXISTS alert_80_at  timestamptz,
  ADD COLUMN IF NOT EXISTS alert_100_at timestamptz;
