# Parental Accounts — Frontend Getting Started

The backend for all phases (0–5) is complete. This is the master guide for the UI
work: what to build, in what order, and where the detailed API contracts live.
Each phase already has a detailed spec in this folder — this doc sequences them
and adds the Phase 5/6 items that have no doc of their own.

| Detailed contract docs |
|---|
| `phase0-frontend-changes.md` — consent review page, birth month + country |
| `phase1-frontend-changes.md` — Family dashboard, add-child wizard, kids login |
| `phase2-frontend-changes.md` — card verification, report page, re-consent banner, consent record |
| `phase3-frontend-changes.md` — child detail page (overview/activity), transparency banner |
| `phase4-frontend-changes.md` — settings toggles, revocation flow, export, new 403s |

---

## Milestone 1 — Unbreak the consent flow (ship with/before backend deploy)

The deployed backend makes `GET /users/consent/confirm` read-only, so the current
`ConsentConfirm.tsx` would show "Account approved!" without approving. **This is
the only breaking change**; prod has zero pending teens today, so ship it together
with the backend deploy.

1. **`ConsentConfirm.tsx` rewrite** → per `phase0` doc §1 + `phase2` doc §3:
   load status via GET, render the disclosure, Approve/Decline buttons.
   - Signed-in adult → `POST /family/link-requests/{token}/approve|decline`
     (links the family, better) — `phase1` doc §2.
   - Anonymous fallback → `POST /users/consent/confirm`.
   - Handle `verification_required` (India/under-13) → route to dashboard.
2. **`BirthYearGate.tsx`**: add month selector; prefill country from
   `GET /geo/country`; pass `birth_month` + `country` through `AuthContext`
   (`completeBirthYear` / `submitParentalConsent`) — `phase0` doc §2.
3. **Pending screen** (`consent_sent` phase in `App.tsx`): add a
   "Resend email" button → `POST /users/consent/resend` (429 after 3/hour;
   response echoes `parent_email`). *(Phase 5 — no other doc.)*

## Milestone 2 — Family dashboard MVP

4. **`/family` route + `Navigation.tsx` link** when `profile.role === 'parent'`
   (`GET /users/me` now returns `role`) — `phase1` doc §1.
5. **Children list** (`GET /family/children`) with per-child card: status,
   verification badge, progress snapshot.
6. **Add-child wizard** (name → DOB → consent disclosure + checkbox → credentials)
   — `phase1` doc §1; handle `verification_required` → card flow (`phase2` §2).
7. **Kids login**: enable Email/Password in Firebase console; add
   `signInWithEmailAndPassword` to `AuthContext`; `/kids-login` page — `phase1` §3.
8. **Child detail page** `/family/child/:uid` with tabs — `phase3` doc:
   Overview, Activity (+gated transcripts), Consent record (`phase2` §5).

## Milestone 3 — Controls & lifecycle surfaces

9. **Settings panel** (pause / chat / content level / transcripts / digest) —
   `phase4` doc §1.
10. **Danger zone**: revoke consent (countdown + undo), delete child, export —
    `phase4` §3–4.
11. **Child-side error states** — `phase4` §2: `account_paused` (full-screen),
    `chat_disabled` (inline in chat), plus existing `consent_pending`.
12. **Teen transparency banner** in `Profile.tsx` from `GET /family/my-family`
    — `phase3` §2. Required, not optional.
13. **Re-consent banner** for adults *and* a per-child "Re-accept policy" action
    on the dashboard (`POST /family/children/{uid}/reconsent`; self:
    `POST /users/me/reconsent`) — `phase2` §4. *(Child endpoint is Phase 5.)*
14. **`/consent/report` page** ("this wasn't me") — `phase2` §1.

## Milestone 4 — Legal copy (Phase 6)

15. **`Parents.tsx` rewrite** — remove the "sign in with your child's account"
    advice; describe the Family dashboard, the two account-creation paths,
    verification tiers, controls, and the visibility contract (mirror
    `parent_can_see` wording). FAQ answers about deletion should point at the
    dashboard, not support email.
16. **`PrivacyPolicy.tsx`** — add/replace the children's-data section: what's
    collected per age band, consent methods (email-plus, card verification),
    parental rights (review, export, delete, withdraw), retention schedule
    (mirror `docs/children-data-dpia.md` §4), per-jurisdiction consent ages.
17. **`Terms.tsx`** — parent-managed account terms: parent responsibility for
    credentials, age-up transition at 18, seat limits on the Family plan.
18. **`Under13Block.tsx`** copy → "Ask your parent to create your account from
    their Family dashboard" (phrase as "coming soon" while
    `ENABLE_MANAGED_CHILDREN` is off).
19. After 15–18 ship: **bump `CONSENT_POLICY_VERSION`** in
    `backend/app/core/jurisdiction.py` — re-consent banners and parent notices
    then trigger automatically.

## Emails already handled (no UI needed)

Consent request, child-created receipt, link-approved receipt, email-plus
follow-up, revocation receipt, weekly digest, age-up (parent + child), re-consent
notice, retention notices, unlink notice — all backend-sent. The only email-adjacent
UI is the pages their links target: `/consent/confirm` (M1) and `/consent/report` (M3).

## Suggested order of PRs

M1 is one small PR and unblocks the backend deploy. M2 is the big one — split as
(dashboard+list), (wizard), (kids login), (child detail). M3 items are each small
and independent. M4 is copy-only and gates the policy-version bump.
