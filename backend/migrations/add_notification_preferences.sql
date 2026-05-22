-- Notification preferences (Phase 1 of notification plan + WhatsApp number-collection plan)
-- One row per user. Created lazily on first PATCH or opt-in.

CREATE TABLE IF NOT EXISTS notification_preferences (
    uid                            TEXT PRIMARY KEY REFERENCES users(uid) ON DELETE CASCADE,
    email_enabled                  BOOLEAN     DEFAULT TRUE,
    whatsapp_enabled               BOOLEAN     DEFAULT FALSE,
    whatsapp_opted_in              BOOLEAN     DEFAULT FALSE,   -- TRUE only after Twilio confirmation
    whatsapp_phone                 TEXT,                        -- E.164 (e.g. +919876543210)
    whatsapp_declined_onboarding   BOOLEAN     DEFAULT FALSE,   -- user skipped opt-in at onboarding step
    whatsapp_nudge_last_dismissed  TIMESTAMPTZ,                 -- 30-day suppression for post-session banner
    quiet_hours_start              INTEGER     DEFAULT 22,      -- local hour 0-23
    quiet_hours_end                INTEGER     DEFAULT 7,
    timezone                       TEXT        DEFAULT 'UTC',
    preferred_channel              TEXT        DEFAULT 'email', -- email | whatsapp
    updated_at                     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notif_prefs_whatsapp_phone
    ON notification_preferences (whatsapp_phone)
    WHERE whatsapp_phone IS NOT NULL;
