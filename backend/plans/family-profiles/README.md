# Family Profiles Plan

**Goal:** Under-13s (and optionally teens) use ECALT through **profiles on their parent's account**, Netflix/Disney+-style. The parent signs in with their own Google credentials, sees a "Who's learning?" picker (their own profile + one per child), and a **parent PIN** guards leaving a child profile and every parent-only surface. Child profiles have **no login of their own** — no child email, no child password.

**Status:** Drafted and implemented 2026-10-11 (uncommitted on `feature/dev`). Migration `013_family_profiles.sql` **applied to prod**. Remaining: Phase 4 rollout items below.

**Decisions (2026-10-11):**
1. **13–17 get both options** — a parent-created profile *or* their own Google login linked to the parent (existing Path B, unchanged). Under-13s get profiles only.
2. **Parent PIN** (not Google re-auth) to leave a child profile / enter parent surfaces. Google re-auth is only the "forgot PIN" path.
3. **Remove the old managed-child login** (`/kids-login`, Firebase email/password child credentials) entirely.

| Phase | Scope | Status |
|---|---|---|
| 0 | Migration + profile resolver + PIN backend | ✅ `core/auth.py`, `services/profile_service.py`, tests `tests/unit/test_profiles.py` |
| 1 | Profile creation replaces Firebase child credentials; null-email guards | ✅ `create_firebase_user` removed; `firebase_admin.purge_login`; scheduler audiences filter `profile_type='account'` |
| 2 | Frontend (see `frontend-changes.md`) | ✅ picker `/profiles`, PIN, kid-mode guard/notice, `/claim`, `/kids-login` removed |
| 3 | Lifecycle: claim flow (`auth_identities`), age-up for profiles | ✅ `POST /users/claim`, claim invites, `_age_up_unclaimed_profile`, `_lifecycle_turn_13` |
| 4 | Rollout: flag on, policy bump, copy, launch checklist | ⏳ copy updated; flag + policy bump + card-flow test still to do |

---

## 1. Current state (audited 2026-10-11)

**Code** — parental-accounts phases 0–6 are committed (`dc4814b`, `c5ee315`), see `plans/parental-accounts/`.
- Under-13 self sign-up is hard-blocked (`core/jurisdiction.py` `HARD_FLOOR_AGE = 13`).
- `POST /family/children` (`endpoints/family.py:83`) creates a managed child **as a separate Firebase email/password user** (`create_firebase_user`, `family.py:126`); the child signs in at `/kids-login`. Under-13 creation is gated by `ENABLE_MANAGED_CHILDREN=False` (`core/config.py:21`) → 403 `under_13_not_available`. **That flag is the only reason under-13s can't use the product today.**
- Teens (13–17): Google sign-up → parent email → authenticated parent approval (`/family/link-requests/{token}/approve`) → `family_links` row.
- Everything else is built on `family_links` + `child_settings` and works per-uid: dashboard (overview/activity/transcripts), controls (pause, chat, age band, transcript visibility, digest), card verification (Stripe setup mode), consent audit log, re-consent, revocation w/ 14-day grace, export, lifecycle job (age-up, expiry, retention), family-plan seats + shared budget (`subscription_service.get_family_member_uids`).
- Auth: Firebase ID token → `get_optional_user` → `get_required_user` (25 uses) → `get_active_user` (29 uses); `get_acting_uid` (9) / `get_active_acting_uid` (10) / `get_optional_acting_uid` (2) add admin impersonation via `X-Impersonate-Session`.

**Prod Supabase:**
- `users`: 17 adults (1 with `role='parent'`), 1 teen stuck in `parental_consent_pending`.
- `family_links` 0 rows, `child_settings` 0 rows, `consent_events` 75 rows → **no child data to migrate**.
- `users.uid` is the PK (text). `users.email` is nullable with no unique index → profile rows with `email IS NULL` need no constraint change.
- ~31 `uid`/`user_id` columns across public tables — all learner data is keyed by the user's uid.

**Problems with the current model for under-13s:** collects the child's email + password (data minimisation under COPPA/GDPR-K), makes a young child manage credentials, and needs the Firebase Email/Password provider enabled.

---

## 2. Design

### 2.1 A profile is a `users` row without a login
- New column `users.profile_type`: `'account'` (has a Firebase login — today's users) | `'profile'` (parent-managed, no login).
- Profile uid is server-generated: `prof_<uuid4 hex>`. `email` is NULL.
- The parent ↔ profile relation is the existing `family_links` row; `child_settings.managed = true`.
- **Every learner table, every dashboard query, controls, budget and lifecycle code keep working unchanged**, because the profile is just another uid. This is the main reason to prefer this over a separate `profiles` table (which would mean re-keying ~31 columns).

The parent's own profile *is* their own `users` row — nothing new is created for "the parent's profile".

### 2.2 Request resolution: parent token + `X-Profile-Id`
```
Authorization: Bearer <parent Firebase ID token>
X-Profile-Id: prof_ab12…            (absent or == own uid → parent's own profile)
```
In `core/auth.py`:
- Rename today's token check to `_token_uid(authorization) -> Optional[str]` (the *real* signed-in user). Phase 3 adds the `auth_identities` lookup here.
- New `_resolve_profile(real_uid, x_profile_id) -> str`:
  - no header, or header == `real_uid` → `real_uid`
  - else require: `users.profile_type='profile'` **and** an active `family_links(parent_uid=real_uid, child_uid=x_profile_id)` row. 60 s cache keyed `(real_uid, profile_id)`, same pattern as `_status_cache`; `invalidate_profile_cache(profile_id)` on delete/revoke/unlink.
  - any failure → **403 `profile_not_allowed`. Never silently fall back to the parent uid** (that would write a child's activity onto the parent, or vice versa) — same reasoning as impersonation's "reject rather than fall back".
- `get_optional_user` / `get_required_user` return the **resolved profile uid**. Because `get_active_user`, `get_acting_uid`, etc. all build on these, every learner endpoint becomes profile-aware with no per-endpoint change. `get_active_user` then enforces the profile's own `paused` / consent-pending status, and `ensure_chat_allowed` the profile's `chat_enabled` — already implemented per uid.
- `X-Impersonate-Session` and a non-self `X-Profile-Id` together → 400 (admins impersonate the profile uid directly instead).

### 2.3 Account-holder endpoints
New dependency `get_account_holder(...) -> str` returns the **real** uid and raises **403 `parent_profile_required`** if the request carries a non-self `X-Profile-Id`. Use it on:
- `endpoints/family.py` — everything except `GET /my-family` (which is the child-facing view and should use the resolved uid)
- `endpoints/subscriptions.py`, `endpoints/coupons.py` (billing belongs to the account)
- `endpoints/users.py`: `POST /users` (sign-up), `DELETE /users/me`, `/users/me/export`, the consent/reconsent endpoints, `/users/consent/*`
- `endpoints/admin.py` (via `get_admin_user`, which should also use `_token_uid`)

Fail-safe: if one is missed, a child profile's request hits `_require_adult_parent` and gets a 403, because a profile is never `adult`/`account`.

### 2.4 Parent PIN
- Table `parent_pins(uid pk → users, pin_hash, failed_attempts, locked_until, updated_at)`. 4–6 digits, hashed with stdlib `hashlib.scrypt` + per-row salt (no new dependency).
- `POST /family/pin` — set (first time; needed before the first child profile is created) or change (requires the current PIN).
- `POST /family/pin/reset` — "forgot PIN": requires a **fresh Google sign-in** (token `auth_time` < 5 min) instead of the PIN.
- `POST /family/pin/verify` → `{unlock_token, expires_in: 900}`. 5 failures → 15-minute lock (`423 pin_locked`).
- `unlock_token` is an HMAC-signed `{uid, exp}` (key derived from `NOTIFICATION_SIGNING_SECRET` with domain separation — no new env var), sent as `X-Parent-Unlock`.
- **Server-enforced** (not just UI): when the account holder has ≥1 active managed profile, `get_account_holder` *mutations* also require a valid `X-Parent-Unlock` — family settings/delete/revoke/verify, billing checkout/cancel, `DELETE /users/me`. Accounts with no profiles are unaffected.
- **Threat model, stated plainly:** the PIN stops a child on a shared device from switching to the parent profile or changing controls through the UI. A determined child with devtools could still strip `X-Profile-Id` and read the parent's *own learner data* or chat as the parent. Controls, billing and deletion stay protected server-side. This is the same model Netflix/Disney+ profile locks use; a "device locked to profile" mode (Phase 4+, optional) closes the remaining gap by binding a device token to one profile.

### 2.5 Per age group

| | Under 13 | 13–17, profile | 13–17, own login (Path B, unchanged) |
|---|---|---|---|
| Created by | Parent (profile) — only route | Parent (profile) | Teen via Google, parent approves |
| Login | Parent's session + PIN | Parent's session + PIN | Teen's own Google |
| Consent check | Card (`required_verification_tier`, unchanged) | Email-plus; card in India | Email-plus; card in India |
| Chat default | Off (parent can enable) | On | On |
| Parent visibility | Full (parent can open the profile) | Full — **disclosed to the teen in the profile UI** | Summaries by default; `transcript_visibility` setting |
| Age-up | At 13: stays a profile; parent offered "give them their own login" | At 18: claim flow (§2.6) | At 18: existing graduation |

Note on teen profiles: a parent who can open the profile sees everything, so the summaries-only privacy default cannot apply. The profile UI must say so ("This profile is managed by your parent, who can open it"). Teens who want privacy use their own login. An optional teen-set profile lock is listed under open questions.

### 2.6 Claiming a profile (giving a child their own login) — Phase 3
- Table `auth_identities(firebase_uid pk, uid → users, created_at)`. `_token_uid` checks it first (cached): a signed-in Firebase uid that maps to a profile uid **becomes** that uid. No data is moved; the profile keeps its id and history.
- Parent creates a one-time claim code (`POST /family/children/{uid}/claim-invite`, 7-day expiry, account-holder + unlock). The child signs in with Google at `/claim?code=…` → `POST /users/claim` writes `auth_identities`, sets `profile_type='account'`, fills `email` from the token, writes a `consent_events` record (`action='granted'`, `method='claim'`).
- Allowed from 13 (needs Google's own 13+ age floor). After claiming, a teen is equivalent to a Path B teen (family link remains; visibility falls back to `transcript_visibility`).
- Age-up at 18 of an **unclaimed** profile: the lifecycle job must not "graduate" a profile nobody can sign in to. Instead it emails the parent a claim invite and keeps the link active, with controls dropped; if it's still unclaimed after 90 days, existing retention notices → deletion apply.

---

## 3. Phases

### Phase 0 — Foundations (backend)
1. Migration `migrations/013_family_profiles.sql`:
   - `users.profile_type text NOT NULL DEFAULT 'account' CHECK (profile_type IN ('account','profile'))`
   - `parent_pins` table (above)
   - `auth_identities` table (created now, used in Phase 3)
   - index `family_links (parent_uid, child_uid) WHERE status='active'` if not already covered
2. `core/auth.py`: `_token_uid`, `_resolve_profile` + cache + invalidation, `get_account_holder`, `X-Parent-Unlock` verification, header-conflict check with impersonation.
3. Switch the account-holder endpoints listed in §2.3 to `get_account_holder`.
4. PIN endpoints in `family.py` (or a small `services/pin_service.py`).
5. Config: none — the unlock key is derived from `NOTIFICATION_SIGNING_SECRET`. CORS already allows all headers (`main.py:153`), so the new headers need no change.
6. Tests (`tests/unit/test_profiles.py`): resolver allow/deny matrix (own uid, linked profile, unlinked, revoked link, `profile_type='account'` child, impersonation conflict); account-holder rejects a profile header; PIN lockout; unlock expiry. Patch `get_db` in every test — `backend/.env` points at prod.

### Phase 1 — Profile creation replaces child credentials
1. `POST /family/children`: drop `email`/`password`; add optional `avatar`. Generate `prof_…` uid, insert `users(profile_type='profile', email NULL, …)`. Keep the age, jurisdiction, card/email-plus tier, consent event (`method='parent_created_profile'`) and `family_links`/`child_settings` logic exactly as it is. Require a PIN to exist (`409 pin_required`).
2. New `GET /family/profiles` → `{ account: {uid, display_name, photo_url}, profiles: [{uid, display_name, avatar, age_group, account_status, paused, chat_enabled, verification_required}], pin_set }` for the picker. (Can be a thin view over the existing `list_children` query.)
3. **Remove** Firebase child credentials: `create_firebase_user` in `services/firebase_admin.py` and its call in `family.py`; `send_child_account_created_email` copy no longer mentions a login. Guard `delete_firebase_user` calls (`family.py:941`, `users.py:183/700`, `scheduler.py:701/838`) to skip `profile_type='profile'` / `prof_` uids.
4. **Null-email audit** — profiles have no email. Every user-targeted email/push must skip `email IS NULL`, or go to the parent where the message is about the child. Files that read user emails: `endpoints/notifications.py`, `services/scheduler.py` (streak/notification jobs; age-up already guards with `if u.get("email")`), `services/coupon_service.py`, `endpoints/admin.py`, `endpoints/users.py`. Add `AND u.profile_type = 'account'` to marketing/reminder audience queries.
5. `GET /users/me` returns the **resolved** profile, plus `is_profile: bool` and `account_holder_uid` so the UI knows it's in kid mode.
6. Leave `ENABLE_MANAGED_CHILDREN=False` until Phase 4.

### Phase 2 — Frontend
See `frontend-changes.md`.

### Phase 3 — Lifecycle & claim
1. `auth_identities` lookup in `_token_uid` (cache, invalidate on claim).
2. Claim invite + `/users/claim` endpoints (§2.6), consent event, parent receipt email.
3. `scheduler._lifecycle_age_up`: branch on `profile_type` — unclaimed profile at 18 → claim invite to parent and keep the link; claimed/own-login → existing graduation. At 13: notify the parent with a "give them their own login" offer and update the content age band.
4. Pending-consent expiry and retention jobs: no Firebase purge for profiles (guarded in Phase 1).

### Phase 4 — Rollout
1. Test the card-verification flow end to end with a profile on dev, then set `ENABLE_MANAGED_CHILDREN=true` on Railway (dev first, then prod).
2. Legal copy: Privacy Policy / Parents / Terms / Under13Block (no child email collected; profiles under the parent's account; PIN; claim at 13+). Then bump `CONSENT_POLICY_VERSION` in `core/jurisdiction.py` — data practices changed, so existing consents re-prompt.
3. Update `plans/parental-accounts/launch-checklist.md`: **remove** "enable Email/Password provider in Firebase" (done). `FIREBASE_SERVICE_ACCOUNT_JSON` is still needed (under-13 Google-sign-in purge, teen deletions).
4. The one prod teen stuck in `parental_consent_pending`: leave it to the existing 30-day pending-expiry job, or resend the consent email (`POST /users/consent/resend`).
5. Update `docs/children-data-dpia.md` (less data collected; shared-device risk + PIN mitigation).

---

## 4. Open questions
- **Teen profile lock:** let a teen set their own profile PIN so the parent can't open the profile (the parent still gets dashboard summaries)? This adds privacy, but the parent can no longer see everything. Default: not in v1.
- **Device lock mode** ("this tablet is Aarav's"): bind a device token to one profile so stripping headers doesn't work. Worth it if families mostly use shared devices.
- **Max profiles:** reuse `MAX_CHILDREN_PER_PARENT` and family-plan seats (5) as-is? Assumed yes.

---

## 5. Implementation notes (2026-10-11)

- **Where profile resolution lives:** `get_optional_user` (→ every learner dependency). Parent-only endpoints moved to `get_account_holder` / `get_unlocked_account_holder` / `get_active_account_holder` / `get_parent_session`: all of `/family/*` except `GET /my-family` and `GET /profiles`; `POST /users`, consent resend/reconsent, `/users/me/export`, `DELETE /users/me`; `/subscriptions/checkout` (unlock), `/sync` + `/razorpay/verify` (no unlock — survive the payment redirect); `/coupons/apply`; WhatsApp opt-in/confirm.
- **Parent self-delete** now blocks while *any* child profile exists (a profile can't outlive its account holder), plus managed under-13s as before.
- **Not done / follow-ups:**
  - Each child profile on a non-family plan gets its own free trial — consider making profiles share the parent's plan regardless of plan type.
  - Unclaimed profile at 18: no automatic 90-day deletion; the ordinary 12-month inactivity retention applies.
  - Teen profile lock and device-lock mode (open questions above) not built.
  - Frontend lint couldn't run (`eslint` not installed in `frontend/node_modules`); `npm run build` passes.
  - Backend suite: 62 failures pre-exist on `feature/dev` (uncommitted endpoint changes make tests reach an unmocked DB); identical before/after this work. Run tests with `DATABASE_URL=postgresql://x:y@127.0.0.1:1/none` so they can't touch Supabase.
