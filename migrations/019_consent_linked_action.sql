-- 019: allow the 'linked' action in consent_events.
-- Used by POST /family/claim-children: when a parent signs in with the email
-- address that granted consent through the anonymous email link, the missing
-- family_links row is created retroactively and audited as action='linked'.
-- Idempotent: drop + re-add the CHECK constraint with the extended list.

ALTER TABLE public.consent_events
    DROP CONSTRAINT IF EXISTS consent_events_action_check;

ALTER TABLE public.consent_events
    ADD CONSTRAINT consent_events_action_check CHECK (action = ANY (ARRAY[
        'requested'::text, 'granted'::text, 'refused'::text, 'revoked'::text,
        'reconsent'::text, 'age_up'::text, 'expired'::text, 'self_consent'::text,
        'followup_sent'::text, 'reported'::text, 'verified'::text, 'linked'::text
    ]));
