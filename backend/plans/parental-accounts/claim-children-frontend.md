# Frontend: claim children linked by email-only consent (issue #23)

## Problem

A teen (13–17) who self-signed up named a parent email; the parent approved
through the **anonymous email link** (`POST /users/consent/confirm`). That
activates the teen but creates **no `family_links` row** — so when that parent
later signs up/signs in, the Parents dashboard shows no children, and they can
never see activity or transcripts.

Backend fix (shipped with this doc): `POST /family/claim-children`. It matches
the signed-in adult's email against confirmed `parental_consent` rows and
creates the missing link(s) for any not-yet-linked teen. Idempotent; returns:

```json
{ "linked": [{ "child_uid": "...", "display_name": "Teen User" }], "count": 1 }
```

Errors: `400 {error: "no_email"}`, `403 {error: "adult_account_required"}`.
The link is disclosed to the teen via the existing `/my-family` panel, and a
`consent_events` row (`action: "linked"`, `method: "email_match"`) is written.
Requires migration `019_consent_linked_action.sql`.

## Frontend changes

1. **`familyApi.ts`** — add:
   ```ts
   export const claimChildren = (token: string) =>
     api.post<{ linked: {child_uid: string; display_name: string|null}[]; count: number }>(
       '/family/claim-children', {}, token)
   ```

2. **`Parents.tsx` (dashboard)** — when the children list loads **empty**,
   call `claimChildren` once automatically:
   - `count > 0` → re-fetch children, show a one-time success note
     ("We found and linked {names} — you approved their account by email.").
   - `count === 0` → show the existing empty state unchanged.
   - Swallow `403 adult_account_required` silently (non-adult viewer).
   Auto-claim only on the empty state; don't call it on every dashboard load.

3. **Optional manual entry point** — on the empty state, a secondary button
   "I already approved my child's account" → calls `claimChildren`, then
   explains "no match" using the parent's own sign-in email: *"No approved
   child accounts are tied to {email}. Make sure you sign in with the email
   address your child entered during sign-up."*

4. **No settings UI changes** — once linked, the existing FamilyChild page
   already provides activity, the "Conversation access" (transcript) setting,
   and the gated transcript viewer.

## Edge cases

- Parent signed in with a different email than the one the teen entered → no
  match; the message in (3) covers it.
- Teen already linked (authenticated approve path) → skipped by the backend.
- Teen turned 18 → excluded (`age_group_flag` filter).
- Nothing here affects school students or family profiles.
