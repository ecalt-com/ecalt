# Family Profiles — Frontend Changes

> **Implemented 2026-10-11** (uncommitted on `feature/dev`). Kept as the contract reference.

Backend contract: `README.md` in this folder. Ship this together with backend Phases 0–1. Profiles stay invisible to users until `ENABLE_MANAGED_CHILDREN=true` (Phase 4) — but since **teen** profiles aren't flag-gated, the picker/PIN must work before the backend deploys Phase 1.

## 1. Header plumbing (do first)

The active profile must be sent on **every** API call, the same way the impersonation session is.

- New `lib/profileStore.ts`, mirroring `lib/impersonationStore.ts`: module-level `get/setActiveProfileId()` and `get/setParentUnlock()` so non-React code can read them.
- `lib/api.ts` `request()`: add `X-Profile-Id` when an active profile is set and isn't the account holder's own uid; add `X-Parent-Unlock` when an unexpired unlock token exists. Export an `authHeaders(token)` helper that builds `Authorization` + `X-Impersonate-Session` + `X-Profile-Id` + `X-Parent-Unlock`.
- **These files build headers by hand and must switch to `authHeaders()`**, or they'll silently act as the parent (streaming chat is the critical one):
  `components/OnboardingModal.tsx`, `components/learn/KnowledgeUniverse.tsx`, `components/learn/ConversationInterface.tsx`, `components/learn/TodaysSpark.tsx`, `components/journey/JourneyTutor.tsx`, `lib/familyApi.ts`, `lib/SubscriptionContext.tsx`, `lib/AuthContext.tsx`, `pages/Pricing.tsx`, `pages/Profile.tsx`, `pages/Privacy.tsx`, `pages/MindSignature.tsx`, `pages/Welcome.tsx`, `pages/Admin.tsx` + `pages/admin/**` (admin: never send `X-Profile-Id`).
- Persist the active profile per device in `localStorage` (`ecalt.activeProfile`, wrapped in try/catch). Keep the unlock token in memory only (lost on reload → PIN again).
- On 403 `profile_not_allowed` (profile deleted/unlinked): clear the active profile and go to the picker.

## 2. Profile context & picker

- `lib/ProfileContext.tsx`: loads `GET /family/profiles` → `{account, profiles, pin_set}`; exposes `activeProfile`, `isKidMode` (active profile ≠ account), `switchTo(uid)`, `unlock(pin)`.
- After `POST /users` bootstrap: if the account has ≥1 profile and no stored active profile → route to **`/profiles` "Who's learning?"**: avatar tiles for the parent + each child + "Add a child" (PIN-gated). Accounts with no profiles never see it.
- Switching **into** a child profile: no PIN. Switching **out of** a child profile, to the parent or to another child: PIN modal → `POST /family/pin/verify` → store the unlock token → switch.
- Profile switcher in the nav (avatar menu) → opens the picker.
- After every switch, refetch `/users/me`, the subscription/budget and anything cached per user (journeys, streak, notifications) — reset per-user React Query/context state.

## 3. Kid mode shell (`isKidMode`)

- Hide: Family, Pricing/upgrade CTAs, account settings / delete account / data export in Profile, admin.
- PIN-gate (modal, then proceed with the unlock header): any navigation to `/family`, `/pricing`, `/profile` account sections, "switch profile". Sign-out is allowed without a PIN (harmless — the child can't sign back in as the parent).
- Banner/notice in the profile menu: under 13 — "Your grown-up manages this profile"; teen profile — "This profile is managed by your parent, who can open it." (required disclosure, README §2.5).
- Existing `account_paused` / `chat_disabled` handling already works per uid — no change.

## 4. PIN UX

- `components/family/PinPad.tsx`: 4–6 digit entry, masked, numeric keypad on mobile.
- Set the PIN as **step 1 of AddChildWizard** when `pin_set=false` (`POST /family/pin`).
- Change PIN and "Forgot PIN" in Family → Settings. Forgot → `reauthenticateWithPopup(GoogleAuthProvider)` → fresh token → `POST /family/pin/reset`.
- Errors: `invalid_pin` (show attempts left if returned), `423 pin_locked` (show unlock time), `parent_unlock_required` from any mutation → open the PIN modal and retry once.

## 5. AddChildWizard (`components/family/AddChildWizard.tsx`)

- **Remove** the email + password step and the "they can now sign in at /kids-login" success copy (line ~327).
- New steps: (PIN if not set) → name + avatar/colour → birth month/year + country → disclosure + consent → card verification if `verification_required` (existing flow) → done: "Find {name} on the Who's learning? screen".
- `409 pin_required` → jump to the PIN step.

## 6. Remove the old child login

- Delete `pages/KidsLogin.tsx` and its route (`App.tsx:39`, `App.tsx:90`); add `/kids-login → /` redirect for old emails/bookmarks.
- `lib/AuthContext.tsx`: remove `signInWithEmail` / `signInWithEmailAndPassword` (lines 5, 23, 42, 178–179, 349).
- Remove `/kids-login` links in `pages/Parents.tsx:104`, `pages/Family.tsx:240`.
- `lib/familyApi.ts`: drop `email`/`password` from the create-child type; add `getProfiles`, `setPin`, `verifyPin`, `resetPin`; later `createClaimInvite`.

## 7. Claim flow (Phase 3)

- Family → child → Settings: "Give {name} their own login" (13+ only) → shows a code/link to send.
- `/claim?code=` page: Google sign-in → `POST /users/claim` → normal app, now as that learner. If the Google account already has an ECALT account → show the backend error, no merge.

## 8. Copy

- `Under13Block.tsx`: "Ask a parent or guardian to add you as a profile on their ECALT account."
- `Parents.tsx`, `PrivacyPolicy`, `Terms`: profiles under the parent account; no child email or password collected; PIN; claim at 13+. Ships before the `CONSENT_POLICY_VERSION` bump (README Phase 4).
