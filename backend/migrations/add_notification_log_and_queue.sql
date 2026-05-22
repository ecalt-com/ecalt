-- notification_log and notification_queue tables (Phase 1)

CREATE TABLE IF NOT EXISTS notification_log (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    uid                 TEXT        REFERENCES users(uid) ON DELETE CASCADE,
    notification_type   TEXT        NOT NULL,
    channel             TEXT        NOT NULL,       -- email | whatsapp
    sent_at             TIMESTAMPTZ DEFAULT now(),
    opened_at           TIMESTAMPTZ,                -- set by tracking pixel / Twilio webhook
    subject             TEXT,
    message_preview     TEXT                        -- first 100 chars, for debugging
);

CREATE INDEX IF NOT EXISTS idx_notif_log_uid_sent
    ON notification_log (uid, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_notif_log_opened
    ON notification_log (uid, opened_at)
    WHERE opened_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS notification_queue (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    uid                 TEXT        REFERENCES users(uid) ON DELETE CASCADE,
    notification_type   TEXT        NOT NULL,
    channel             TEXT        NOT NULL,       -- email | whatsapp
    scheduled_for       TIMESTAMPTZ NOT NULL,
    payload             JSONB       DEFAULT '{}',
    status              TEXT        DEFAULT 'pending',  -- pending | sent | cancelled
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notif_queue_pending
    ON notification_queue (scheduled_for)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_notif_queue_uid
    ON notification_queue (uid);
