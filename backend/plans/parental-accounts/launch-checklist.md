# Parental Accounts — Launch Checklist

Work through top to bottom. Items marked ⚙️ are one-time infrastructure; 🌍 are
per-jurisdiction gates.

## 1. Infrastructure (before any deploy) ⚙️

- [ ] `FIREBASE_SERVICE_ACCOUNT_JSON` set on Railway (full service-account key
      JSON). Without it: under-13 Firebase purge is a no-op, child creation
      returns 503.
- [ ] **Email/Password provider enabled** in the Firebase console (kids login).
- [ ] `STRIPE_SECRET_KEY` present (already used for billing) — card verification
      reuses it. Verify Checkout **setup mode** works on the account (test mode
      run: create child in an IN-jurisdiction test account → verify card flow).
- [ ] Brevo/SMTP email transport configured (consent + lifecycle emails).
- [ ] Deploy backend; confirm scheduler jobs registered in logs:
      `consent_followup_dispatch`, `family_digest_dispatch`,
      `scheduled_deletion_dispatch`, `family_lifecycle_dispatch`.

## 2. Frontend (see `frontend-getting-started.md`)

- [ ] Phase 0 consent page (review + POST) — **blocking**: teen signups are
      broken between backend deploy and this shipping.
- [ ] Birth month + country in `BirthYearGate`.
- [ ] Family dashboard (list, add-child wizard, settings, danger zone).
- [ ] Kids login, consent report page, re-consent banner, teen transparency banner.
- [ ] Legal copy rewrite (Privacy Policy, Terms, Parents page) — then bump
      `CONSENT_POLICY_VERSION` in `app/core/jurisdiction.py` (this triggers
      re-consent notices automatically).

## 3. Jurisdiction gates 🌍

**Teens 13+ (US/EU/UK/rest, email-plus tier)** — live as soon as §1 + §2 ship.
- [ ] Verify email-plus follow-up arrives ~24h after an approval and the
      "wasn't me" link suspends the account.

**India (all minors are card tier)**
- [ ] Confirm Stripe card verification acceptable for the target audience, or
      hold teen signups until a DigiLocker-class provider is integrated.
- [ ] DPDP: confirm no behavioral-tracking features target children (see DPIA §1).

**Under-13s anywhere (managed accounts, card tier)**
- [ ] All of the above, plus a review of AI chat safety posture (chat defaults
      off — decide whether parents may enable it and under what disclosure).
- [ ] Then set `ENABLE_MANAGED_CHILDREN=true` on Railway.

## 4. Legal / documentation

- [ ] Review `docs/children-data-dpia.md`; have counsel sanity-check the
      children's-data sections of the Privacy Policy before the version bump.
- [ ] Support inbox (support@ecalt.com) monitored — consent objection emails and
      "this wasn't me" reports promise human follow-up.

## 5. Post-launch verification (first week)

- [ ] Create a real teen test account end-to-end (Path B): signup → parent email
      → authenticated approve → dashboard shows child → digest Sunday.
- [ ] Create a managed 13+ child (Path A) → kids login works → pause/chat-off
      enforcement verified from the child session.
- [ ] Revoke consent on a test child → paused immediately → cancel → restored.
- [ ] Check `consent_events` rows exist for every step above.
