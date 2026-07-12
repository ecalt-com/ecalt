# Parental Accounts & Child Safety Compliance Plan

**Goal:** Move from the current "child signs up, parent clicks an email link" model to industry-standard **parent-managed accounts**: parents create and manage accounts for their kids, see what they're doing, and control the account — with a consent system that meets worldwide legal standards (COPPA, GDPR Art. 8, UK Children's Code, India DPDP Act).

**Status:** Drafted 2026-07-10. Phase 0 implemented 2026-07-10 (see table).

| Phase | Status | Notes |
|---|---|---|
| 0 Compliance foundations | ✅ backend done, migration **applied to prod** | `006_parental_accounts.sql` live (tables `family_links`/`child_settings`/`consent_events` + append-only trigger verified, 9 events backfilled). Code: `core/jurisdiction.py`, `services/consent_service.py`, `services/firebase_admin.py`, users.py consent rework (read-only GET + POST decision), fail-closed `get_active_user`. **Needs backend deploy + frontend changes** (`phase0-frontend-changes.md`) + `FIREBASE_SERVICE_ACCOUNT_JSON` env var on Railway for under-13 Firebase purge. |
| 1 Parent accounts & linking | ✅ backend done | New `/api/v1/family` router: `POST/GET/DELETE /children` (Path A managed creation w/ Firebase email+password credential, chat off by default under 13), `POST /link-requests/{token}/approve\|decline` (Path B authenticated approval → creates family link). `verify_parent_of` (fail-closed) in `core/auth.py`; deletion cascade extracted to `services/account_service.py` (+ family tables, + Firebase credential purge); parent self-delete blocked while managed children exist (409); `UserProfile.role` exposed. Under-13 gated by `ENABLE_MANAGED_CHILDREN` (default off until Phase 2). **Needs deploy + frontend** (`phase1-frontend-changes.md`) + Email/Password provider enabled in Firebase console. |
| 2 Verifiable consent tiers | ✅ backend done, migration **applied to prod** | `007_consent_verification.sql` live (child_settings verification columns, `consent_followups` queue, new audit actions). Tier logic in `jurisdiction.required_verification_tier` (under-13 → card; India minors → card; else email-plus). Email-plus: 24h follow-up (scheduler job `consent_followup_dispatch`, hourly) + `POST /users/consent/report` objection endpoint (suspends child). Card: Stripe Checkout setup-mode `POST /family/children/{uid}/verify/card` + `/confirm`; card-tier children stay pending until verified. Re-consent: `needs_reconsent` on `GET /users/me/consent` + `POST /users/me/reconsent`. Parent consent record: `GET /family/children/{uid}/consent`. **Deferred:** Razorpay/DigiLocker India flow, automated re-consent emails + 30-day pause (Phase 5), dedicated Phase 2 tests (user: add later). Frontend: `phase2-frontend-changes.md`. |
| 3 Parent dashboard | ✅ backend done | `GET /family/children/{uid}/overview` (streak, totals, quiz stats, domains, journeys+progress %) and `/activity?days=` (steps, journeys, quizzes, conversation titles+counts); gated transcript endpoint `/conversations/{id}` (managed under-13s or `transcript_visibility='full'`); child-facing `GET /family/my-family` transparency contract; weekly parent digest (scheduler `family_digest_dispatch`, Sun 17:00 UTC, skips inactive children). SQL shapes validated against prod. No new migration needed. Tests deferred (user). Frontend: `phase3-frontend-changes.md`. |
| 4 Parental controls | ✅ backend done | `PATCH /family/children/{uid}/settings` (paused/chat/age-band/transcripts/digest) with real enforcement: `get_active_user` blocks paused (403 `account_paused`); `ensure_chat_allowed` gates `/chat/stream` (chat + tutor); explore/quiz endpoints upgraded `get_required_user`→`get_active_user`; parent-set `content_age_band` overrides journey generation. Self-serve revocation: `POST .../revoke-consent` (pause now + 14-day grace via `deletion_requests` status='scheduled' + daily scheduler job `scheduled_deletion_dispatch`) with `/cancel` undo + email receipt. Child export `GET .../export` (shared `build_user_export` in account_service). Family plan: children inherit parent's family sub (seat-capped) with shared budget in `check_budget`/`get_budget_status`. No migration needed. Frontend: `phase4-frontend-changes.md`. |
| 5 Lifecycle & edge cases | ✅ backend done | Daily `family_lifecycle_dispatch` job (04:00 UTC): age-up (graduate link, drop controls, NULL consent_version → adult re-consents on login, parent+child emails); pending-consent expiry (30d, hard delete + Firebase purge); automated re-consent notices + 30-day lapse pause; 12-month retention notices → 14-day grace deletion. `POST /users/consent/resend` (3/hr); `POST /family/children/{uid}/reconsent`; parent self-delete now blocks only for managed under-13s and unlinks+notifies teens. Generic `send_family_notice_email` helper. No migration needed. |
| 6 Legal content & rollout | ✅ done except UI copy | `docs/children-data-dpia.md` (DPIA + written retention policy per COPPA 2025); `launch-checklist.md` (infra, per-jurisdiction gates, post-launch verification); existing-user migration was zero-work (all adults, events backfilled in Phase 0). **UI copy rewrite** (Parents/Privacy/Terms/Under13Block) + `CONSENT_POLICY_VERSION` bump specced in `frontend-getting-started.md` Milestone 4. |

**Frontend:** start with `frontend-getting-started.md` (milestone-ordered master guide; per-phase contracts in `phase0..4-frontend-changes.md`).

---

## 1. How it works today (audited 2026-07-10)

### Sign-up / consent flow
- Google-only sign-in via Firebase (`frontend/src/lib/firebase.ts`). After first sign-in, `BirthYearGate.tsx` collects **birth year only**, then `POST /api/v1/users` (`backend/app/api/v1/endpoints/users.py:42`).
- **Under 13** → 403 `under_13`, no `users` row created, `Under13Block.tsx` shown. Hard block.
- **13–17** → child must enter a parent email (`ParentalConsentForm.tsx`). User row created with `account_status='parental_consent_pending'`, a UUID token row in `parental_consent` (7-day expiry), and `send_parental_consent_email()` (`email_service.py:126`) sends a link.
- Parent clicks link → `GET /users/consent/confirm?token=` flips the account to `active` and sets `consent_given_at`. Rendered by `ConsentConfirm.tsx` at `/consent/confirm`.
- **18+** → active immediately, `consent_given_at=now()`, `consent_version='1.0'` (hardcoded).
- `get_active_user` (`core/auth.py:66`) blocks consent-pending accounts from protected endpoints.

### What already exists that we can build on
- GDPR endpoints: `GET /users/me/consent`, `GET /users/me/export`, `DELETE /users/me` (full cascade + `deletion_requests` log).
- `age_group_flag` (`teen`/`adult`) on `users`; `age_group` on `user_interests` (content tuning).
- **Admin impersonation** (`admin_impersonation_sessions`, `get_acting_uid` in `core/auth.py:173`) — a proven "act-on-behalf-of / view-as" pattern the parent dashboard can mirror.
- **Family plan** in `plan_configs` (5 seats, active, Stripe + Razorpay price IDs) — but *seats are not implemented anywhere in code*. Parental accounts give this plan its meaning.
- `GET /geo/country` (`geo.py`) — IP country detection, usable for jurisdiction-aware consent ages.
- Rich per-child data already collected: journeys, `user_progress`, `quiz_results`, `knowledge_nodes`, `domain_mastery`, conversations, streaks — everything a parent dashboard needs is already in the DB.
- Prod DB check: all 11 current users are `adult`/`active`; `parental_consent` is empty → **no data migration burden, we can redesign freely**.

### There is no parent account concept
No parent role, no parent-child link, no dashboard, no controls. `Parents.tsx` literally tells parents to **"sign in with their child's account"** to review activity — a credential-sharing anti-pattern that must go.

---

## 2. Gaps found (legal + technical)

### Compliance gaps
| # | Gap | Why it matters |
|---|---|---|
| G1 | **`GET /consent/confirm` mutates state.** Email security scanners and link prefetchers (Outlook SafeLinks, corporate gateways) follow GET links automatically → consent can be "confirmed" without any human ever seeing the page. | Consent is legally void if not a deliberate act. Must be a POST triggered by an explicit button after the parent reviews a disclosure. |
| G2 | **No parent identity/adulthood verification.** The child can type any email — including their own second address. One click = consent. | COPPA requires *verifiable* parental consent; plain email-click is only acceptable ("email-plus") for internal-use data, and even then needs a delayed follow-up confirmation. India DPDP (rules finalized 2025) requires identity + age verification of the consenting parent. |
| G3 | **Consent records are destroyed.** `DELETE FROM parental_consent` on every re-signup (`users.py:101`) and on account deletion (`users.py:423`). | COPPA/GDPR require durable proof of when/how/by whom consent was given. Consent history must be immutable and survive account deletion (retention for legal defense is a permitted basis). |
| G4 | **Under-13 data is still collected before the block.** The Firebase Auth user (name, email, photo) is created by Google sign-in *before* the age gate runs. The backend refuses a row, but the child's PII persists in Firebase. | COPPA prohibits retaining data collected from under-13s. Need neutral age gate before auth, or delete the Firebase user on under-13 outcome. |
| G5 | **Hardcoded ages 13/18 for the whole world.** GDPR Art. 8 lets member states set the digital-consent age anywhere from 13 (UK, IE, DK, SE) to 16 (DE, NL, HU…), 15 (FR, GR), 14 (ES, IT, AT). India DPDP: **under 18** requires verifiable parental consent, and prohibits behavioral tracking/targeted ads at children. South Korea: 14. China PIPL: 14. Brazil LGPD: 18 with parental consent for children. | ECALT actively sells in India (Razorpay pricing) and internationally (Stripe). Needs a jurisdiction matrix, not constants. |
| G6 | **Birth year only.** A child born Dec 2013 is treated as 13 in Jan 2026 (actually 12). | Off-by-one age classification for up to ~1 year. Collect month + year (still data-minimal) and compute age properly. |
| G7 | **No consent lifecycle.** `consent_version` hardcoded `'1.0'`; no re-consent on policy change; no revocation flow (Parents page says "email support"); no age-up transition (a consented 13-year-old stays `teen`/consented forever, and never re-consents as an adult). | GDPR requires consent to be as easy to withdraw as to give; COPPA gives parents an ongoing right to review and revoke. Age-up is standard practice (Google Family Link, Apple). |
| G8 | `get_active_user` **fails open** on DB errors (`core/auth.py:85`) — a consent-pending child gets through if the status check throws. | Consent enforcement should fail closed for pending accounts (cache status in the token path if latency is a concern). |
| G9 | Under-13 block message says "ask a parent to create an account" — **no such flow exists**. | This plan makes the message true. |

### Industry-standard practices we're missing (benchmark: Google Family Link, Apple Family Sharing, Khan Academy, Duolingo)
1. **Parent creates the child account**, not child-initiated signup with a typed parent email.
2. **Parent dashboard**: list of children, per-child activity (topics, journeys, quizzes, streaks, time), settings, pause/delete.
3. **Consent as a reviewed, signed act**: parent sees a full disclosure of data collected, checks boxes, confirms — from *their own authenticated account*, creating an auditable record.
4. **Teen transparency**: the child is told exactly what the parent can see (Family Link shows kids what's monitored). For 13+, activity *summaries* are shown to parents, not raw chat transcripts, unless disclosed.
5. **Tiered verification**: email-plus → card micro-transaction → third-party ID/age verification (Privo, Yoti, k-ID, Epic KWS) selected per jurisdiction.
6. **Ongoing controls**: pause account, content age band, disable AI chat, weekly digest, revoke + delete.

---

## 3. Target design

### Roles & relationships
```
users.role: 'learner' (default) | 'parent'          -- a parent can also be a learner
family_links: parent_uid ↔ child_uid, status        -- active | revoked
                                                    -- a child has ≤1 managing parent (v1)
child_accounts (per child): managed BOOLEAN,        -- true if parent-created (under-13 path)
    content_age_band, chat_enabled, paused,
    weekly_digest_enabled, visibility_level
consent_events (append-only): uid, parent_uid, action (granted|refused|revoked|reconsent|age_up),
    method (email_plus|card|id_verification), policy_version, jurisdiction, ip_hash, created_at
```

### Two account-creation paths
**Path A — parent-created (enables under-13 support, the headline feature):**
1. Parent (adult, verified account) opens **Family** dashboard → "Add a child".
2. Enters child's name, birth month/year → sees the full COPPA/GDPR/DPDP disclosure → grants consent (checkbox + POST) at the verification tier the child's jurisdiction requires.
3. Child credential is created: **Firebase email/password** credential generated by the parent (child username + parent-set password or PIN) — Google OAuth can't be used for under-13s (Google's own ToS requires 13+ or Family Link). 13+ children may instead link their own Google account.
4. Child logs in; account is active immediately (consent pre-granted), flagged `managed=true`.

**Path B — child-initiated with parent approval (upgrade of today's teen flow):**
1. Child (≥13 or ≥ jurisdiction age) signs up with Google as today, enters parent email.
2. Parent's email link now lands on a page that requires the parent to **sign in / create a parent account**, review the disclosure, and confirm via POST → creates the `family_links` row + `consent_events` record.
3. Child account activates *and is now parent-linked* — so the parent gets the dashboard automatically, instead of a one-shot click and goodbye.

### Jurisdiction matrix (single source of truth, `app/core/jurisdiction.py`)
| Region | Consent-required below | Verification tier |
|---|---|---|
| US (COPPA) | 13 | email-plus minimum; card/ID for chat-enabled accounts |
| EU/EEA (GDPR Art. 8) | per-country 13–16 (default 16 if unknown) | reasonable-effort: authenticated parent account + email-plus |
| UK | 13 (+ Children's Code design duties) | email-plus |
| India (DPDP) | **18** | authenticated parent + verified identity signal (card charge via Razorpay or DigiLocker-class verification later) |
| Brazil (LGPD) | 18 (child <13 stricter) | email-plus |
| KR / CN | 14 | email-plus |
| Default / unknown | 16 | email-plus |

Country from: user-declared during signup (primary) with `GET /geo/country` as the sanity check/prefill. Store `jurisdiction` on the user at consent time.

### What parents can see (visibility contract — disclosed to both sides)
- Always: topics/journeys explored, progress %, quiz scores, streaks, time-of-use summary, knowledge map.
- Under-13 (managed): chat conversation *titles + AI-generated topic summaries*; full transcripts available on demand (COPPA parental review right).
- 13+ linked: summaries only by default; transcript access is a per-family setting **visible to the teen** ("Your parent can see: …" banner in `Learn`/`Journey`).

---

## 4. Phases

### Phase 0 — Compliance foundations & data model *(backend, no UX change)*
Fix the things that are wrong regardless of the new feature.
1. **Migration** `00X_parental_accounts.sql`:
   - `users`: add `role text default 'learner'`, `birth_month smallint`, `jurisdiction text`, `paused boolean default false`.
   - `family_links(id, parent_uid, child_uid, status, created_at, revoked_at)` + unique on `child_uid` where status='active'.
   - `consent_events` append-only (no UPDATE/DELETE grants), columns per §3. Backfill one `granted` event per existing consented user.
   - `child_settings(child_uid pk, managed, content_age_band, chat_enabled, weekly_digest_enabled, transcript_visibility)`.
   - Keep `parental_consent` as the *pending-token* table only; stop deleting rows — mark them `superseded`.
2. **`app/core/jurisdiction.py`**: consent-age matrix + `consent_age_for(country)`; use in `users.py` instead of literal `13`/`17`.
3. **Fix G1**: `POST /users/consent/confirm` (body: token + explicit `approved: true`); keep GET as a read-only token-status check for the page. Update `ConsentConfirm.tsx` to show the disclosure + Approve/Decline buttons.
4. **Fix G3**: consent confirm/refuse/expiry writes `consent_events`; account deletion retains `consent_events` (pseudonymized uid hash) and `deletion_requests`.
5. **Fix G4**: on under-13 outcome, delete the Firebase Auth user via Admin SDK (add `firebase-admin` or REST call) after showing the block; also move the age question **before** any profile write.
6. **Fix G6/G8**: collect birth month+year in `BirthYearGate.tsx`; compute age from (year, month); make `get_active_user` fail **closed** when the row says pending (cache `account_status` for 60s like `_admin_cache` to keep latency).
7. Tests: extend `tests/unit/test_age_verification.py` for jurisdiction matrix, month-accurate age, POST-confirm, fail-closed.

### Phase 1 — Parent accounts & family linking
1. `role='parent'` set when a user creates their first child or approves a consent request while signed in.
2. **New router `family.py`** (`/api/v1/family`):
   - `POST /children` — create managed child (Path A): validates parent is adult+active, child age vs jurisdiction, creates Firebase email/password credential (Admin SDK), `users` row (`managed=true`, active), `family_links`, `child_settings`, `consent_events(granted)`.
   - `GET /children` — list linked children with status.
   - `POST /link-requests/{token}/approve|decline` — Path B: replaces the anonymous confirm; requires authenticated parent; writes link + consent event.
   - `DELETE /children/{uid}` — parent-initiated child deletion (reuses the `DELETE /users/me` cascade, parent-authorized).
3. **Authorization helper** `get_parent_of(child_uid)` in `core/auth.py` — verifies an active `family_links` row (mirror of `_check_admin`).
4. Frontend:
   - `/family` route (parent-gated): children list, "Add a child" wizard (name → DOB → disclosure → consent → credential setup).
   - Path B consent page: sign-in wall + disclosure + Approve/Decline (replaces one-click `ConsentConfirm.tsx`).
   - Child login: add Firebase email/password sign-in on a kid-friendly `/kids-login` (username + password), alongside Google.
   - Update `Under13Block.tsx`: "Ask your parent to create your account at ecalt.com/family" (G9 becomes true).
5. Email templates: consent-request v2 (discloses collected data per current policy version), "child account created", "link approved".

### Phase 2 — Verifiable consent tiers (jurisdiction-aware)
1. **Email-plus** (baseline, all regions): after approval, send a delayed (24–48h) follow-up "You approved X's account — reply/click if this wasn't you" + record in `consent_events`.
2. **Card micro-verification** (US chat-enabled + India): $0.50/₹5 authorization via existing Stripe/Razorpay integration (`subscriptions.py` already has both), immediately voided; card success = adult signal. Store only the verification outcome.
3. **Third-party ID/age verification hook** (design only, implement when scale demands): interface `ConsentVerifier` with providers Privo/Yoti/k-ID; DPDP DigiLocker-class flow for India as a later drop-in.
4. **Consent versioning**: `POLICY_VERSION` constant; on bump, parents get a re-consent email and children of non-re-consented parents fall back to `paused` after 30 days (grace banner first).
5. Consent record UI: parent can view/download every `consent_events` entry for their child (`GET /family/children/{uid}/consent`).

### Phase 3 — Parent dashboard: visibility
1. Backend `GET /family/children/{uid}/overview`: streak, journeys (+progress %), top domains from `domain_mastery`, quiz stats from `quiz_results`, active days from `last_active_date`, knowledge-node count. All data already exists — read-only aggregation.
2. `GET /family/children/{uid}/activity?days=30`: recent journeys/steps/quizzes timeline; conversation **titles + topic summaries** (respecting `transcript_visibility`; full transcript endpoint only for managed under-13s or when the family setting allows).
3. Frontend `/family/child/:uid`: overview cards, activity timeline, knowledge map (reuse `ConstellationMap`/Passport components), consent record tab.
4. **Teen transparency**: banner/section in child's `Profile.tsx` — "Linked to parent account X. They can see: topics, progress, quiz scores[, conversations]." Required by UK Children's Code transparency duty; standard practice.
5. **Weekly digest email**: cron (notification queue infra exists — `notification_queue`, `notifications.py`) sending per-child summary to parents with `weekly_digest_enabled`.

### Phase 4 — Parental controls: management
1. `PATCH /family/children/{uid}/settings`: `paused`, `chat_enabled`, `content_age_band`, `transcript_visibility`, `weekly_digest_enabled`.
2. Enforcement:
   - `paused` → `get_active_user` returns 403 `account_paused` (child sees a friendly "Ask your parent" screen).
   - `chat_enabled=false` → 403 on `/chat/stream` and journey tutor.
   - `content_age_band` → feed into AI prompt context (journeys/steps/spark already accept `age_group` on `user_interests`; make the parent setting authoritative for managed children).
3. Self-serve consent revocation: `POST /family/children/{uid}/revoke-consent` → account paused immediately, `consent_events(revoked)`, 14-day countdown to full deletion (email with undo), then reuse deletion cascade. Replaces "email support@ecalt.com".
4. Child data export for parents: `GET /family/children/{uid}/export` (reuse `/users/me/export` internals, parent-authorized).
5. Family plan integration: subscribing parent's Family plan grants seats to linked children (`subscriptions.py`: budget check walks `family_links` to the parent's subscription; enforce `max_seats`).

### Phase 5 — Lifecycle & edge cases
1. **Age-up job** (daily cron): child crosses jurisdiction consent age → notify parent + child; account converts to self-managed at 18 (or consent age, configurable): link becomes `graduated`, parent visibility ends, child re-consents on next login as adult (`age_group_flag='adult'`, new `consent_events(age_up)`).
2. Parent deletes own account → children handling: block deletion while managed under-13 children exist (must delete/transfer them first); 13+ linked children get unlinked + notified.
3. Pending-consent expiry: unconfirmed Path B accounts hard-deleted after 30 days (COPPA data-minimization), `consent_events(expired)`; token resend endpoint with rate limit.
4. One-parent-per-child in v1; second-guardian invitation listed as future work.
5. Firebase cleanup worker for orphaned auth users (under-13 blocks, expired pendings).

### Phase 6 — Legal content, migration & rollout
1. Rewrite `Parents.tsx` (remove credential-sharing advice; document the dashboard), `PrivacyPolicy.tsx`, `Terms.tsx` — children's-data section: what's collected, verification methods, parental rights, retention schedule, per-jurisdiction consent ages. Bump `POLICY_VERSION`.
2. Direct-notice email copy review (COPPA "direct notice" content requirements: what's collected, how used, parental rights, revocation).
3. DPIA / children's-data risk assessment doc (required by UK Children's Code & GDPR for child-data processing at scale) — store in `docs/`.
4. Migration of existing users: all current users are adult/active → only backfill `consent_events`. Any future teen accounts created pre-launch get a parent-link invitation email.
5. Launch checklist per jurisdiction; feature-flag the under-13 path (`ENABLE_MANAGED_CHILDREN`) so it ships only after the verification tier for the target market is live.
6. Retention policy implementation: define + enforce (e.g., inactive child accounts deleted after N months with parent notice) — 2025 COPPA amendments require a written retention policy.

---

## 5. Suggested sequencing & risk notes
- **Phase 0 is shippable alone and fixes real compliance bugs today** (GET-mutation consent, destroyed consent records, Firebase under-13 residue). Do it first regardless of the rest.
- Phases 1+3 deliver the visible product ("parent creates & sees") — the core of the ask. Phase 2 can start at email-plus (cheap) and add card verification before enabling under-13 in COPPA/DPDP markets.
- Biggest new dependency: **Firebase Admin SDK** on the backend (create/delete auth users, password credentials). Today the backend only *verifies* tokens (`core/auth.py`); creating child credentials and deleting under-13 Firebase users both need Admin access (service-account key in Railway env).
- Under-13 chat with an AI is the highest-risk surface: keep `chat_enabled` default **off** for managed under-13s, on for 13+, until the safety posture is reviewed.
- Frontend work is substantial (dashboard, wizard, kids login); per project convention, each phase's frontend scope should get its own md spec before implementation.
