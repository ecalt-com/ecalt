-- Course content quality plan, Phase 4/5:
-- 1. Generation metadata on step_content so cached content can be lazily
--    regenerated when the prompt version advances (existing rows default to
--    version 1; current code writes CONTENT_PROMPT_VERSION = 2).
-- 2. step_feedback table for per-step user ratings; negative tags trigger
--    background regeneration.

ALTER TABLE step_content
    ADD COLUMN IF NOT EXISTS model text,
    ADD COLUMN IF NOT EXISTS prompt_version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS generated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS step_feedback (
    id          bigserial PRIMARY KEY,
    uid         text NOT NULL,
    journey_id  text NOT NULL,
    step_id     text NOT NULL,
    rating      text NOT NULL CHECK (rating IN ('up', 'down')),
    tag         text CHECK (tag IN ('too_generic', 'too_basic', 'too_advanced', 'inaccurate', 'loved_it')),
    comment     text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (uid, journey_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_step_feedback_journey ON step_feedback (journey_id, step_id);

-- Backend connects as table owner (RLS does not apply); this blocks
-- PostgREST anon/authenticated access, consistent with 001_security_hardening.
ALTER TABLE step_feedback ENABLE ROW LEVEL SECURITY;
