# Phase 1 — Frontend changes required

Backend Phase 1 (parent accounts, family linking, managed child creation) is
implemented. All endpoints below require `Authorization: Bearer <token>` unless
noted. Error responses follow the usual `{detail: {error, message}}` shape.

**Feature flag note:** under-13 child creation returns 403 `under_13_not_available`
until `ENABLE_MANAGED_CHILDREN` is set on the backend (Phase 2). 13–17 works now.
`FIREBASE_SERVICE_ACCOUNT_JSON` must be configured on Railway or child creation
returns 503 `not_configured`.

---

## 1. `/family` dashboard page (new, auth required)

Show for signed-in users; primary entry point for parents. `GET /api/v1/users/me`
now returns `role: "learner" | "parent"` — use it to decide whether to show a
"Family" link in `Navigation.tsx` (always show the page itself to any adult who
navigates there; an empty state invites them to add a child).

### List children

`GET /api/v1/family/children` →

```jsonc
{
  "children": [
    {
      "child_uid": "…", "display_name": "Kid", "email": "kid@example.com",
      "account_status": "active", "age_group_flag": "teen" | "child",
      "birth_year": 2011, "birth_month": 6, "paused": false, "streak_days": 3,
      "managed": true,            // parent-created (Path A) vs approved teen (Path B)
      "chat_enabled": true, "content_age_band": null,
      "weekly_digest_enabled": true, "transcript_visibility": "summaries",
      "linked_at": "2026-07-10T…"
    }
  ]
}
```

Render a card per child (name, age group, streak, managed badge). Settings toggles
are display-only in Phase 1 — the settings PATCH endpoint arrives in Phase 4.

### Add a child (wizard)

`POST /api/v1/family/children`:

```jsonc
// request
{
  "display_name": "Kid",
  "birth_year": 2011,
  "birth_month": 6,            // optional but strongly encouraged (month-accurate age)
  "email": "kid@example.com",  // child's login email — may be a parent-managed alias
  "password": "min 8 chars",   // child's login password, set by the parent
  "country": "IN"              // optional; prefill from GET /api/v1/geo/country
}
// 201 response
{ "child_uid": "…", "display_name": "Kid", "email": "…",
  "age_group": "teen" | "child", "chat_enabled": true, "managed": true }
```

Wizard steps (industry pattern — Google Family Link style):
1. Child's name + date of birth (year + month selectors).
2. **Consent disclosure** — what ECALT collects (name/login email, learning
   questions and journeys, AI-generated knowledge topics), what it never does
   (sell data, ads, third-party sharing), parental rights (view, export, delete,
   withdraw consent), links to Terms + Privacy Policy, and an explicit
   "I am this child's parent/guardian and I consent" checkbox gating the next step.
3. Login credentials: child email + password (+ confirm). Tell the parent to share
   these with the child.
4. Done screen: child can now sign in at the kids login (see §3).

Error handling:
| status | `detail.error` | UI |
|---|---|---|
| 403 | `under_13_not_available` | "Accounts for under-13s are coming soon" notice on the DOB step |
| 403 | `adult_account_required` / `no_account` | Only active adult accounts can add children |
| 400 | `not_a_minor` | Adults must sign up themselves |
| 400 | `family_full` | Max 5 children |
| 409 | `email_exists` | Ask for a different child email |
| 503 | `not_configured` | "Temporarily unavailable" |

Note: the parent's own account is created via the normal Google sign-up (they must
have completed the birth-year gate as an adult).

### Delete a child

`DELETE /api/v1/family/children/{child_uid}` → 204. Show a strong confirm dialog
("permanently deletes all of {name}'s journeys, progress and conversations").
This is the COPPA parental deletion right; it also revokes consent.

---

## 2. Consent page (`/consent/confirm`) — authenticated approval (Path B)

Extends the Phase 0 review page. Preferred flow: the parent signs in, so approval
also links the child to their family dashboard.

- `POST /api/v1/family/link-requests/{token}/approve` (auth) →
  `{ "status": "confirmed", "child_uid": "…", "child_name": "…", "message": "…" }`
- `POST /api/v1/family/link-requests/{token}/decline` (auth) →
  `{ "status": "refused", "message": "…" }`
- Both can also return `already_confirmed`; errors mirror the anonymous endpoint
  (`invalid_token`, `token_expired`) plus 403 `self_approval` (the child signed in
  with their own pending account — tell them to ask their parent) and 403
  `adult_account_required`.

Page behavior:
1. GET status as in Phase 0 (`pending_review` + `child_name`).
2. If the visitor is **signed in as an active adult**: Approve/Decline buttons call
   the `/family/link-requests/...` endpoints. On approve, offer a "Go to Family
   dashboard" CTA.
3. If **not signed in**: show a "Sign in with Google to approve — you'll also get a
   dashboard to see what your child is learning" primary path. Keep the anonymous
   `POST /users/consent/confirm` as a secondary "Approve without an account" option
   (it still works but creates no dashboard link; it will be removed in Phase 2).

## 3. Kids login (email/password)

Managed children sign in with the email+password their parent created (Google OAuth
is not available under 13). Requires:

- `firebase.ts`: nothing — email/password uses the same `firebaseAuth` instance.
  **Enable the Email/Password provider in the Firebase console** (one-time, manual).
- `AuthContext.tsx`: add `signInWithEmail(email, password)` using
  `signInWithEmailAndPassword` from `firebase/auth`; same post-sign-in flow
  (`POST /api/v1/users` upsert). Managed children already have a `users` row with
  `birth_year` set, so `needs_birth_year` is false and no gate appears.
- A kid-friendly login entry: either a `/kids-login` page or an "I have a family
  account" email/password form on the existing sign-in surface.

## 4. Copy updates

- `Under13Block.tsx`: replace "Ask a parent or guardian to create an ECALT
  account — they can use it together with you!" with "Ask your parent to create an
  account for you from their Family dashboard at ecalt.com/family." (Keep in mind
  under-13 creation stays gated until Phase 2 — phrase as "coming soon" until
  `ENABLE_MANAGED_CHILDREN` is on.)
- `Parents.tsx`: the "sign in with their account" guidance is replaced by the
  Family dashboard (full rewrite lands in Phase 6; a minimal fix now is fine).

## 5. Self-deletion edge case (`Profile.tsx`)

`DELETE /api/v1/users/me` can now return **409 `managed_children_exist`** — show
"Delete your children's accounts from the Family dashboard before deleting your
own account."
