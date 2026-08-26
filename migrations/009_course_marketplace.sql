-- Course marketplace: popularity-driven discovery of user-generated journeys,
-- gated by admin review before anything is publicly listed.

ALTER TABLE journeys
    ADD COLUMN marketplace_status text NOT NULL DEFAULT 'private',
    ADD COLUMN popularity_score numeric NOT NULL DEFAULT 0,
    ADD COLUMN like_count integer NOT NULL DEFAULT 0,
    ADD COLUMN forked_from_id text REFERENCES journeys(id),
    ADD COLUMN marketplace_reviewed_at timestamptz,
    ADD COLUMN marketplace_reviewed_by text;

ALTER TABLE journeys
    ADD CONSTRAINT journeys_marketplace_status_check
    CHECK (marketplace_status IN ('private', 'pending_review', 'published', 'rejected'));

CREATE INDEX idx_journeys_marketplace_status ON journeys (marketplace_status);
CREATE INDEX idx_journeys_popularity_score ON journeys (popularity_score DESC);

CREATE TABLE journey_likes (
    uid text NOT NULL REFERENCES users(uid),
    journey_id text NOT NULL REFERENCES journeys(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (uid, journey_id)
);

ALTER TABLE journey_likes ENABLE ROW LEVEL SECURITY;
