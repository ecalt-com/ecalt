-- Family profiles: children use ECALT as profiles on the parent's login.
-- Additive only — safe to apply before the backend deploys.
-- See backend/plans/family-profiles/README.md.

-- 1. A profile is a users row with no login of its own ('prof_<hex>' uid,
--    email NULL). 'account' rows have a Firebase login (every existing user).
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS profile_type text NOT NULL DEFAULT 'account',
  ADD COLUMN IF NOT EXISTS avatar text;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_profile_type_check') THEN
    ALTER TABLE public.users
      ADD CONSTRAINT users_profile_type_check CHECK (profile_type IN ('account', 'profile'));
  END IF;
END $$;

-- 2. Parent PIN guarding exits from a child profile and parent-only surfaces.
CREATE TABLE IF NOT EXISTS public.parent_pins (
  uid              text PRIMARY KEY,
  pin_hash         text NOT NULL,          -- scrypt$<salt hex>$<hash hex>
  failed_attempts  smallint NOT NULL DEFAULT 0,
  locked_until     timestamptz,
  updated_at       timestamptz NOT NULL DEFAULT now()
);

-- 3. Firebase login -> users.uid mapping. Lets a child claim their profile with
--    their own Google sign-in without re-keying any learner data.
CREATE TABLE IF NOT EXISTS public.auth_identities (
  firebase_uid  text PRIMARY KEY,
  uid           text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS auth_identities_uid_key ON public.auth_identities (uid);

-- 4. One-time claim invites created by the parent.
CREATE TABLE IF NOT EXISTS public.profile_claims (
  code         text PRIMARY KEY,
  uid          text NOT NULL,              -- the profile being claimed
  parent_uid   text NOT NULL,
  expires_at   timestamptz NOT NULL,
  claimed_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS profile_claims_uid_idx ON public.profile_claims (uid);

-- Server-side only tables: no client (anon/authenticated) access.
ALTER TABLE public.parent_pins     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile_claims  ENABLE ROW LEVEL SECURITY;
