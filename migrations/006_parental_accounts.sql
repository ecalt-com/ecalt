-- Parental accounts Phase 0: compliance foundations & data model.
-- Additive only — fully backward compatible with the deployed backend.
-- See backend/plans/parental-accounts/README.md.

-- 1. users: role (parent|learner), month-accurate age, jurisdiction, pause flag.
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'learner',
  ADD COLUMN IF NOT EXISTS birth_month smallint CHECK (birth_month BETWEEN 1 AND 12),
  ADD COLUMN IF NOT EXISTS jurisdiction text,
  ADD COLUMN IF NOT EXISTS paused boolean NOT NULL DEFAULT false;

-- 2. Parent ↔ child relationship. A child has at most one active managing parent (v1).
CREATE TABLE IF NOT EXISTS public.family_links (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_uid  text NOT NULL,
  child_uid   text NOT NULL,
  status      text NOT NULL DEFAULT 'active'
              CHECK (status IN ('active', 'revoked', 'graduated')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at  timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS family_links_one_active_parent
  ON public.family_links (child_uid) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS family_links_parent_idx
  ON public.family_links (parent_uid);

-- 3. Per-child settings, written by the managing parent (enforced in later phases).
CREATE TABLE IF NOT EXISTS public.child_settings (
  child_uid              text PRIMARY KEY,
  managed                boolean NOT NULL DEFAULT false,  -- true = parent-created account (Path A)
  content_age_band       text,
  chat_enabled           boolean NOT NULL DEFAULT true,
  weekly_digest_enabled  boolean NOT NULL DEFAULT true,
  transcript_visibility  text NOT NULL DEFAULT 'summaries'
                         CHECK (transcript_visibility IN ('summaries', 'full')),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

-- 4. Immutable consent audit log. COPPA/GDPR require durable proof of when, how,
--    and by whom consent was given — records survive account deletion (uid is
--    pseudonymized then, which is the only UPDATE the trigger below permits).
CREATE TABLE IF NOT EXISTS public.consent_events (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uid            text NOT NULL,
  parent_uid     text,
  parent_email   text,
  action         text NOT NULL CHECK (action IN
                 ('requested', 'granted', 'refused', 'revoked',
                  'reconsent', 'age_up', 'expired', 'self_consent')),
  method         text,   -- email_link | email_plus | card | id_verification | signup
  policy_version text,
  jurisdiction   text,   -- ISO 3166-1 alpha-2 at consent time
  ip_hash        text,   -- sha256 of consenting party's IP, never the raw IP
  details        jsonb,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consent_events_uid_idx ON public.consent_events (uid);

CREATE OR REPLACE FUNCTION public.consent_events_append_only()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'consent_events is append-only: DELETE is not allowed';
  END IF;
  IF (to_jsonb(NEW) - 'uid') IS DISTINCT FROM (to_jsonb(OLD) - 'uid') THEN
    RAISE EXCEPTION 'consent_events is append-only: only uid pseudonymization is allowed';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS consent_events_append_only ON public.consent_events;
CREATE TRIGGER consent_events_append_only
  BEFORE UPDATE OR DELETE ON public.consent_events
  FOR EACH ROW EXECUTE FUNCTION public.consent_events_append_only();

-- 5. Backfill: one self-consent event per already-consented user so the audit
--    log is complete from day one.
INSERT INTO public.consent_events (uid, action, method, policy_version, jurisdiction, details)
SELECT uid, 'self_consent', 'signup',
       COALESCE(consent_version, '1.0'), jurisdiction,
       jsonb_build_object('backfill', true, 'consent_given_at', consent_given_at)
  FROM public.users
 WHERE consent_given_at IS NOT NULL;

-- 6. RLS: backend connects as table owner (bypasses RLS); anon/authenticated get nothing.
ALTER TABLE public.family_links   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.child_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consent_events ENABLE ROW LEVEL SECURITY;
