-- Cache table for personalised journey recommendations (Phase 3).
-- One row per user; replaced on each regeneration. TTL enforced in application code.
CREATE TABLE IF NOT EXISTS journey_recommendations (
    uid          text        NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    generated_at timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    journeys     jsonb       NOT NULL DEFAULT '[]',
    PRIMARY KEY (uid)
);

ALTER TABLE journey_recommendations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users can read own recommendations"
    ON journey_recommendations FOR SELECT
    USING (auth.uid()::text = uid);
