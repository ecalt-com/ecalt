-- F1.3 (plans/feature-improvements): spaced review. One row per learner and
-- step, in a Leitner box (1..5); a correct review moves it up (due later), a
-- miss sends it back to box 1. Removed with the user.
CREATE TABLE IF NOT EXISTS public.review_items (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  uid              text        NOT NULL REFERENCES public.users(uid) ON DELETE CASCADE,
  journey_id       text        NOT NULL,
  step_id          text        NOT NULL,
  concept          text        NOT NULL,
  box              integer     NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
  due_at           timestamptz NOT NULL,
  last_result      text        CHECK (last_result IN ('correct','incorrect')),
  last_reviewed_at timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (uid, journey_id, step_id)
);
CREATE INDEX IF NOT EXISTS review_items_due_idx ON public.review_items (uid, due_at);
ALTER TABLE public.review_items ENABLE ROW LEVEL SECURITY;
