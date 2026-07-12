# Phase 0 — Frontend changes required

Backend Phase 0 (compliance foundations) is implemented. Three frontend updates are
needed to complete it. Until the ConsentConfirm change ships, the consent flow is
**broken for new teen signups**: the backend GET no longer activates accounts (that was
compliance bug G1), so the current page would show "Account approved!" without actually
approving. Prod currently has zero pending/teen users, so nothing is affected today —
but ship this together with (or before) the backend deploy.

---

## 1. `ConsentConfirm.tsx` — review + explicit decision (required)

The API contract changed:

**`GET /api/v1/users/consent/confirm?token=X`** is now **read-only**. Responses:

```jsonc
// 200 — token valid, awaiting the parent's decision
{ "status": "pending_review", "child_name": "Teen User", "parent_email": "parent@example.com" }
// 200 — terminal states
{ "status": "already_confirmed", "message": "..." }
{ "status": "refused", "message": "..." }
// 400 — detail.error: "invalid_token" | "token_expired"
```

**`POST /api/v1/users/consent/confirm`** records the decision:

```jsonc
// request
{ "token": "<uuid>", "approved": true }   // or false
// 200 responses
{ "status": "confirmed", "message": "Account approved. ..." }
{ "status": "refused",   "message": "Understood — the account will not be activated." }
// 400 — same error shapes as GET
```

Page behavior:
1. On load, `GET` with the token.
2. `pending_review` → show a **consent review screen**, not an auto-confirmation:
   - Child's name (`child_name`).
   - Disclosure block (same content as the consent email): what ECALT collects
     (name/email from Google sign-in, learning questions and journeys, AI-generated
     knowledge topics) and what it never does (sell data, ads, third-party sharing).
   - Links to `/terms` and `/privacy-policy`.
   - Two buttons: **Approve account** → `POST {approved: true}`; **Decline** → `POST {approved: false}`.
3. Render `confirmed` / `refused` / `already_confirmed` / `expired` / `invalid` end states.
   The existing `success`/`expired`/`invalid` UI can be reused; add `refused`.
4. Do not auto-POST on page load under any circumstances — a human click is the
   entire point of this change.

## 2. `BirthYearGate.tsx` + `AuthContext.tsx` — birth month + country (required)

`POST /api/v1/users` accepts two new optional fields:

```jsonc
{ "birth_year": 2010, "birth_month": 7, "country": "IN", ... }
```

- **`birth_month`** (1–12): add a month selector next to the year. The backend computes
  age conservatively (birthday month not yet passed → one year younger), which is why
  month matters: year-only can misclassify a 12-year-old as 13.
- **`country`**: ISO 3166-1 alpha-2. Fetch `GET /api/v1/geo/country` when the gate is
  shown (prefill; allow the user to correct it via a small country selector if
  desired — prefill-only is acceptable for Phase 0). Send it with the upsert. It is
  stored as the user's consent jurisdiction and drives verification tiers in Phase 2.
- `submitParentalConsent` in `AuthContext.tsx` must also pass `birth_month` and
  `country` on its second `POST /users` call (the one that includes `parent_email`) —
  store them in state alongside `pendingBirthYear`.

## 3. `Profile.tsx` — consent record surface (optional, nice-to-have)

`GET /api/v1/users/me/export` now includes a `consent_events` array
(`action`, `method`, `policy_version`, `jurisdiction`, `created_at`). No UI change is
strictly required; if Profile has a Privacy & Data section, a small "Consent history"
list can render it later (full parent-facing UI arrives in Phase 3).

---

## Not changed

- The consent email link URL is the same (`/consent/confirm?token=…`).
- All error shapes (`detail.error` = `invalid_token` / `token_expired`) are unchanged.
- 18+ signup flow is unchanged apart from the two new optional fields.
