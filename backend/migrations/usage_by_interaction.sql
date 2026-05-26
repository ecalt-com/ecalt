-- Usage by interaction type — run once in Supabase SQL editor
-- Tracks per-feature AI usage aggregated monthly per user

CREATE TABLE IF NOT EXISTS usage_by_interaction (
    uid                  TEXT        NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    period_start         DATE        NOT NULL,   -- always 1st of month
    interaction_type     TEXT        NOT NULL,   -- 'daily_chat' | 'journey' | 'spark' | etc.
    input_tokens         BIGINT      NOT NULL DEFAULT 0,
    output_tokens        BIGINT      NOT NULL DEFAULT 0,
    cached_input_tokens  BIGINT      NOT NULL DEFAULT 0,
    estimated_cost_cents FLOAT       NOT NULL DEFAULT 0,
    request_count        INT         NOT NULL DEFAULT 0,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (uid, period_start, interaction_type)
);

CREATE INDEX IF NOT EXISTS idx_ubi_uid_period
    ON usage_by_interaction (uid, period_start);

-- RLS: users can only read their own rows; service role can write
ALTER TABLE usage_by_interaction ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_read_own_usage" ON usage_by_interaction
    FOR SELECT USING (auth.uid()::text = uid);
