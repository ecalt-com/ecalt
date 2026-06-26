-- ── Phase: Learner Intelligence Upgrade ──────────────────────────────────────
-- Covers: journey preview cache, learner intent columns, quiz analytics

-- 1. Journey preview cache (pre-persist, expires after 30 min)
CREATE TABLE IF NOT EXISTS journey_previews (
  preview_token  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uid            text NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
  question       text NOT NULL,
  journey_json   jsonb NOT NULL,
  age_group      text NOT NULL DEFAULT 'all',
  created_at     timestamptz DEFAULT now(),
  expires_at     timestamptz DEFAULT (now() + INTERVAL '30 minutes')
);

CREATE INDEX IF NOT EXISTS journey_previews_uid_idx ON journey_previews(uid);
CREATE INDEX IF NOT EXISTS journey_previews_exp_idx ON journey_previews(expires_at);

-- 2. Profession field on users (persistent, set once in profile)
ALTER TABLE users ADD COLUMN IF NOT EXISTS profession text;

-- 3. Learner intent per journey
ALTER TABLE journeys ADD COLUMN IF NOT EXISTS learner_purpose   text;
ALTER TABLE journeys ADD COLUMN IF NOT EXISTS topic_expertise   text;

-- 4. Concept interactions — analytics feed for Mind Signature 27 dimensions
CREATE TABLE IF NOT EXISTS concept_interactions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uid            text NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
  journey_id     text,
  step_id        text,
  concept        text NOT NULL,
  domain         text,
  verdict        text NOT NULL CHECK (verdict IN ('excellent', 'on_track', 'off_track')),
  missed_aspect  text,
  hints_used     int  DEFAULT 0,
  difficulty     text,
  attempted_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS concept_interactions_uid_idx      ON concept_interactions(uid);
CREATE INDEX IF NOT EXISTS concept_interactions_concept_idx  ON concept_interactions(uid, concept);
CREATE INDEX IF NOT EXISTS concept_interactions_journey_idx  ON concept_interactions(journey_id);
