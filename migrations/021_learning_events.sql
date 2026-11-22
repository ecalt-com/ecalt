-- F1.2 (plans/feature-improvements): learning funnel events. One row per
-- allowlisted event from signed-in learners (never school students). Pruned
-- after 180 days by the nightly job; removed with the user (ON DELETE CASCADE).
CREATE TABLE IF NOT EXISTS public.learning_events (
  id          bigserial PRIMARY KEY,
  uid         text        NOT NULL REFERENCES public.users(uid) ON DELETE CASCADE,
  event       text        NOT NULL,
  journey_id  text,
  step_id     text,
  props       jsonb       NOT NULL DEFAULT '{}'::jsonb,
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS learning_events_event_at_idx   ON public.learning_events (event, at);
CREATE INDEX IF NOT EXISTS learning_events_journey_at_idx ON public.learning_events (journey_id, at);
CREATE INDEX IF NOT EXISTS learning_events_uid_idx        ON public.learning_events (uid);
ALTER TABLE public.learning_events ENABLE ROW LEVEL SECURITY;
