# Phase 2 — Frontend changes required

Backend Phase 2 (verifiable consent tiers) is implemented: email-plus follow-up
notices, card micro-verification via Stripe Checkout (setup mode, nothing charged),
jurisdiction-tiered activation, re-consent on policy bumps, and a parent-facing
consent record. Migration applied to prod; scheduler job `consent_followup_dispatch`
runs hourly.

**Tier logic (backend-decided, surfaced in responses):** under-13 anywhere → `card`;
any minor in India → `card`; other teens → `email_plus`. Children on the `card` tier
are created/approved with `account_status: "parental_consent_pending"` and only
activate after the parent completes card verification.

---

## 1. `/consent/report` page (new, public)

The email-plus follow-up email ("you approved X's account — wasn't you?") links to
`{FRONTEND_URL}/consent/report?child={uid}&token={hmac}`.

- Page shows an explanation and a single destructive-styled button
  ("Yes, suspend this account"). **No auto-POST on load** — same principle as the
  consent page.
- On click: `POST /api/v1/users/consent/report` (no auth) with
  `{ "child_uid": <from ?child>, "token": <from ?token> }` →
  `{ "status": "reported", "message": "…" }`; 400 `invalid_token` otherwise.
- Show the returned message; suspension is immediate.

## 2. Family dashboard: verification state + card verification

`GET /api/v1/family/children` items now include:
`verification_tier` (`"email_plus" | "card" | "id"`),
`verification_status` (`"unverified" | "pending" | "verified"`), `verified_at`.

For a child with `verification_tier: "card"` and status ≠ `verified` (their
`account_status` will be `parental_consent_pending`), show a **"Verify with card"**
CTA on the child card:

1. `POST /api/v1/family/children/{uid}/verify/card` → `{ "checkout_url": "…" }`
   → `window.location.href = checkout_url`. (Stripe hosted page, setup mode —
   copy should say "€0/₹0 — card check only, nothing is charged".)
   Errors: 503 `not_configured`, 502 `stripe_error`.
2. Stripe redirects back to `/family?verify_session={SESSION_ID}&child={uid}`.
   On mount, if those params exist:
   `POST /api/v1/family/children/{child}/verify/card/confirm` with
   `{ "session_id": … }` → `{ "status": "verified", … }` → refresh the list,
   show success toast. Errors: 400 `verification_incomplete` / `invalid_session`,
   403 `session_mismatch`.

The add-child wizard (Phase 1 doc) should also handle the new creation response
fields: `verification_required: true` → after the done screen, lead straight into
the card verification flow instead of "child can now sign in".

## 3. Consent page: `verification_required` responses

Both the anonymous `POST /users/consent/confirm` and the authenticated
`POST /family/link-requests/{token}/approve` can now return:

```jsonc
{ "status": "verification_required", "message": "…", /* authenticated also: */ "child_uid": "…", "verification_tier": "card" }
```

- Anonymous path: show the message ("this region requires identity verification —
  sign in to continue") and surface the sign-in button.
- Authenticated path: consent + family link are already recorded; route the parent
  to `/family` where the "Verify with card" CTA completes activation.

## 4. Re-consent banner (policy version bumps)

`GET /api/v1/users/me/consent` now returns `needs_reconsent: bool` and
`current_policy_version`. When `needs_reconsent` is true, show a banner/modal
("Our privacy policy has been updated — please review and accept") linking to the
policy, with an Accept button → `POST /api/v1/users/me/reconsent` →
`{ "status": "reconsented", "policy_version": "…" }`.

## 5. Consent record tab (Family dashboard child view)

`GET /api/v1/family/children/{uid}/consent` →

```jsonc
{
  "consent": { "account_status": "…", "consent_given_at": "…", "consent_version": "1.0", "jurisdiction": "US" },
  "verification": { "verification_tier": "email_plus", "verification_status": "verified", "verified_at": "…" },
  "current_policy_version": "1.0",
  "events": [ { "action": "granted", "method": "parent_created", "policy_version": "1.0", "jurisdiction": "US", "created_at": "…" }, … ]
}
```

Render as a simple timeline ("Consent granted — by card verification — 10 Jul 2026")
with a "Download record" button (serialize the JSON client-side).

---

## Not yet implemented (later phases)

- Razorpay-based card verification for India (Stripe checkout works but UPI-first
  users may lack cards; DigiLocker-class verification is the Phase 2+ 'id' tier).
- Automated re-consent emails + 30-day pause for non-re-consented parents (Phase 5
  lifecycle jobs).
