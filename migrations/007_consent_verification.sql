-- Parental accounts Phase 2: verifiable consent tiers.
-- Additive; backward compatible with the deployed backend.

-- 1. Per-child verification state. Tier is decided by jurisdiction + age
--    (app/core/jurisdiction.py): 'email_plus' baseline, 'card' for under-13s
--    and India (DPDP), 'id' reserved for future third-party verification.
ALTER TABLE public.child_settings
  ADD COLUMN IF NOT EXISTS verification_tier text NOT NULL DEFAULT 'email_plus'
    CHECK (verification_tier IN ('email_plus', 'card', 'id')),
  ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'unverified'
    CHECK (verification_status IN ('unverified', 'pending', 'verified')),
  ADD COLUMN IF NOT EXISTS verified_at timestamptz;

-- 2. Email-plus follow-up queue: a delayed "you approved this — wasn't you?"
--    notice, dispatched by the scheduler ~24h after consent.
CREATE TABLE IF NOT EXISTS public.consent_followups (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uid           text NOT NULL,          -- child
  parent_uid    text,
  parent_email  text NOT NULL,
  child_name    text,
  send_after    timestamptz NOT NULL,
  sent_at       timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consent_followups_due_idx
  ON public.consent_followups (send_after) WHERE sent_at IS NULL;

ALTER TABLE public.consent_followups ENABLE ROW LEVEL SECURITY;

-- 3. New audit actions for the verification lifecycle.
ALTER TABLE public.consent_events DROP CONSTRAINT IF EXISTS consent_events_action_check;
ALTER TABLE public.consent_events ADD CONSTRAINT consent_events_action_check
  CHECK (action IN ('requested', 'granted', 'refused', 'revoked',
                    'reconsent', 'age_up', 'expired', 'self_consent',
                    'followup_sent', 'reported', 'verified'));
