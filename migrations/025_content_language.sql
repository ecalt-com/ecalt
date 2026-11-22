-- F2.2 (plans/feature-improvements): learn in your language, Hindi first.
-- A journey's language is fixed when it is created, so the step_content cache
-- (keyed by journey and step) stays valid. English is the default everywhere.
ALTER TABLE public.users    ADD COLUMN IF NOT EXISTS preferred_language text NOT NULL DEFAULT 'en';
ALTER TABLE public.journeys ADD COLUMN IF NOT EXISTS language           text NOT NULL DEFAULT 'en';
CREATE INDEX IF NOT EXISTS idx_journeys_language ON public.journeys (language) WHERE language <> 'en';
