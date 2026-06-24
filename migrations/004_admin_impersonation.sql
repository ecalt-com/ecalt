-- Admin impersonation sessions and audit log

CREATE TABLE IF NOT EXISTS admin_impersonation_sessions (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_uid   TEXT        NOT NULL REFERENCES users(uid),
  target_uid  TEXT        NOT NULL REFERENCES users(uid),
  reason      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 minutes',
  ended_at    TIMESTAMPTZ,
  ended_by    TEXT
);

CREATE INDEX IF NOT EXISTS idx_imp_sessions_admin  ON admin_impersonation_sessions (admin_uid, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_imp_sessions_target ON admin_impersonation_sessions (target_uid, created_at DESC);

CREATE TABLE IF NOT EXISTS admin_impersonation_audit (
  id          BIGSERIAL   PRIMARY KEY,
  session_id  UUID        NOT NULL REFERENCES admin_impersonation_sessions(id),
  admin_uid   TEXT        NOT NULL,
  target_uid  TEXT        NOT NULL,
  endpoint    TEXT        NOT NULL,
  method      TEXT        NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_imp_audit_session ON admin_impersonation_audit (session_id);
CREATE INDEX IF NOT EXISTS idx_imp_audit_target  ON admin_impersonation_audit (target_uid, created_at DESC);

-- Lock both tables down: no Data API access for any role
ALTER TABLE admin_impersonation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_impersonation_audit    ENABLE ROW LEVEL SECURITY;
