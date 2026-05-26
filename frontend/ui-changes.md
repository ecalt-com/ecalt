# ECALT UI Changes — Legal Compliance

**Corresponds to:** `plan-legal.md`  
**Date:** 2026-05-23  
**Affects:** Frontend (Next.js) — signup flow, mind signature views, privacy dashboard

---

## 1. Signup Flow — Age Verification

### 1.1 New field: Birth Year input

**Where:** Google sign-in success callback, before user is routed to onboarding.

Currently the app calls `POST /users` immediately after Firebase auth with `{email, display_name, photo_url}`. This must be interrupted to collect birth year.

**UI flow:**

```
[Google Sign-In] → [Birth Year Screen] → POST /users (with birth_year)
                         │
               ┌─────────┴──────────┐
           age < 13               age ≥ 13
               │                      │
         [Under-13 Block]       ┌──────┴──────┐
                              13-17          ≥ 18
                                │               │
                        [Parental Consent   [Standard
                          Email Screen]      Onboarding]
```

**Birth Year Screen component:**

- Title: "How old are you?"
- Subtext: "We ask to keep ECALT safe for all learners."
- Input: dropdown or number input — year only (range: current_year - 100 to current_year)
- CTA: "Continue"
- Do NOT accept "I'd rather not say" — birth year is required for COPPA compliance
- Do NOT show birth year on any profile page after submission

### 1.2 Under-13 Block Screen

**Trigger:** Backend returns `403 {"error": "under_13"}`

**Component: `<Under13Block />`**

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   🎓  ECALT is for learners aged 13 and over   │
│                                                 │
│   To protect younger learners, we can't         │
│   create an account for you right now.          │
│                                                 │
│   Ask a parent or guardian to create            │
│   an ECALT account — they can use it            │
│   together with you!                            │
│                                                 │
│   [← Back to Home]                             │
│                                                 │
└─────────────────────────────────────────────────┘
```

- No "try again" button — the block is final for this session
- Sign out of Firebase immediately after rendering this screen (don't leave a partial session)
- Do not store the birth year in localStorage or any analytics event

### 1.3 Parental Consent Screen (age 13-17)

**Trigger:** `birth_year` puts user in 13-17 range

**Component: `<ParentalConsentForm />`**

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   📧  One more step                            │
│                                                 │
│   Because you're under 18, we need a           │
│   parent or guardian to approve your account.  │
│                                                 │
│   Parent/Guardian email                         │
│   [________________________]                   │
│                                                 │
│   We'll send them a quick confirmation email.   │
│   Your account will be ready once they confirm. │
│                                                 │
│   [Send Confirmation Email]                    │
│                                                 │
│   By continuing you agree to our               │
│   Terms of Service and Privacy Policy.          │
│                                                 │
└─────────────────────────────────────────────────┘
```

**After submission → Pending Screen:**

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   ✅  Email sent!                              │
│                                                 │
│   We've emailed your parent at                 │
│   parent@example.com                           │
│                                                 │
│   Once they confirm, you'll be able            │
│   to start learning on ECALT.                  │
│                                                 │
│   The link expires in 7 days.                  │
│                                                 │
│   [Sign out]                                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Parent confirmation landing page:** `GET /consent/confirm?token=<uuid>`

- New frontend route: `/consent/confirm`
- Reads `token` from query param
- Calls `GET /api/v1/users/consent/confirm?token=<token>`
- On success: show "Account approved! Your child can now log in." with link to home
- On expired/invalid: show "This link has expired. Please ask your child to request a new one."

### 1.4 Consent checkbox (age 17+)

Add to the existing onboarding screen (or the birth year screen):

```
☐  I agree to the Terms of Service and Privacy Policy
```

- Checkbox must be unchecked by default
- "Continue" button is disabled until checked
- Links open in new tab

---

## 2. Mind Signature — Legal Disclaimer

### 2.1 Every Mind Signature view must show the disclaimer

**Disclaimer text (verbatim — do not paraphrase):**
> "AI-generated capability indicator based on demonstrated learning engagement — not an accredited educational credential."

**Where it must appear:**
1. `/mind-signature` — user's own signature view
2. `/mind-signature/verify/[hash]` — public verify page
3. Any share card, preview, or embed of a Mind Signature

### 2.2 Component: `<MindSignatureDisclaimer />`

```tsx
// Renders the required legal disclaimer below every signature
export function MindSignatureDisclaimer() {
  return (
    <p className="text-xs text-muted-foreground mt-4 border-t pt-3">
      AI-generated capability indicator based on demonstrated learning engagement
      — not an accredited educational credential.
    </p>
  )
}
```

**Placement rules:**
- Always below the capability narrative, never in a collapsed/expandable section
- Font size: minimum 12px (do not use `text-[10px]` or smaller)
- Color: readable against background (WCAG AA contrast — do not use a color lighter than `text-muted-foreground`)
- Must be visible without scrolling if the signature content fits on one screen

### 2.3 Verify page — `app/mind-signature/verify/[hash]/page.tsx`

The verify page must include:
1. The disclaimer text prominently
2. A note that explains what a Mind Signature is and is not

**Layout section to add above the signature:**

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   🔍  Verified Mind Signature                  │
│                                                 │
│   This is an AI-generated capability indicator  │
│   based on demonstrated learning engagement.    │
│   It is NOT an accredited educational           │
│   credential, degree, or qualification.         │
│                                                 │
└─────────────────────────────────────────────────┘
```

This banner must appear before the signature content, not after.

---

## 3. Privacy Dashboard — `app/settings/privacy/page.tsx`

New page accessible from user settings. Required for GDPR/CCPA compliance.

### 3.1 Layout

```
Privacy & Data

Your data

  [Download my data]          [Delete my account]
  Get a copy of all           Permanently remove
  your ECALT data as          your account and all
  a JSON file.                associated data.

Consent

  You agreed to our Terms of Service and Privacy Policy
  on [date from consent_given_at].

  [Update consent preferences]   (links to privacy policy)

Age & Account Status

  Account type: Standard / Under-review (parental consent pending)
```

### 3.2 Data Export

**Button:** "Download my data"  
**Action:** `GET /api/v1/users/me/export`  
**UX:** Show loading spinner → browser downloads `ecalt-data-export.json` via `Content-Disposition: attachment`

No confirmation modal needed — exporting is non-destructive.

### 3.3 Account Deletion

**Button:** "Delete my account" (destructive, red)  
**Action flow:**

Step 1 — Confirmation modal:
```
┌─────────────────────────────────────────────────┐
│                                                 │
│   ⚠️  Delete your account?                    │
│                                                 │
│   This will permanently delete:                │
│   • Your profile and learning history          │
│   • All journeys and progress                  │
│   • All conversations                          │
│   • Your Mind Signatures                       │
│   • Your subscription (if active)              │
│                                                 │
│   This cannot be undone.                       │
│                                                 │
│   Type DELETE to confirm:                      │
│   [________________]                           │
│                                                 │
│   [Cancel]    [Delete Account]                 │
│                                                 │
└─────────────────────────────────────────────────┘
```

Step 2 — Call `DELETE /api/v1/users/me`

Step 3 — Sign out of Firebase, redirect to home with message: "Your account has been deleted."

---

## 4. Error States for Compliance Flows

| Error | User-facing message |
|---|---|
| `under_13` | "ECALT is for learners aged 13 and over. Ask a parent to create an account." |
| `consent_pending` | "Your account is waiting for parental approval. Check your parent's inbox." |
| `consent_expired` | "The confirmation link has expired. Please sign up again to send a new link." |
| `already_deleted` | "This account has already been deleted." |
| Parental consent token not found | "This confirmation link is invalid. Please ask your child to sign up again." |

---

## 5. Navigation / Discovery

- Add "Privacy" link to user settings menu
- Add "Privacy Policy" and "Terms of Service" links to the footer (if not already present)
- Mind Signature share link should include disclaimer in the `<meta>` og:description so it appears in social previews

---

## 6. Accessibility Requirements

All new compliance screens must meet WCAG 2.1 AA:
- Disclaimer text: minimum contrast ratio 4.5:1
- All form fields: labelled with `<label>` or `aria-label`
- Error messages: associated with inputs via `aria-describedby`
- Confirmation modal: focus trapped inside modal, `role="dialog"`, `aria-modal="true"`
- Delete confirmation input: `autocomplete="off"`, `spellcheck="false"`

---

## 7. Tracking / Analytics

- Do NOT send `birth_year` or `parent_email` to analytics (Mixpanel, PostHog, etc.)
- Safe to track: `signup_age_bucket` with values `"13-17"`, `"18+"`, `"blocked_under_13"` — no exact year
- Track `data_export_requested`, `account_deletion_requested` events for compliance audit trail
- Track `parental_consent_sent`, `parental_consent_confirmed` events

---

## 8. Implementation Order

| Step | Task | Component / Route | Est. |
|---|---|---|---|
| 1 | Birth year screen between Google auth and `POST /users` | `components/auth/BirthYearGate.tsx` | 2h |
| 2 | Under-13 block screen | `components/auth/Under13Block.tsx` | 30 min |
| 3 | Parental consent form + pending screen | `components/auth/ParentalConsentForm.tsx` | 2h |
| 4 | Parent confirmation landing page | `app/consent/confirm/page.tsx` | 1h |
| 5 | `MindSignatureDisclaimer` component | `components/mind-signature/Disclaimer.tsx` | 20 min |
| 6 | Inject disclaimer into signature view | `app/mind-signature/page.tsx` | 20 min |
| 7 | Inject disclaimer into verify page + add banner | `app/mind-signature/verify/[hash]/page.tsx` | 30 min |
| 8 | Privacy dashboard page | `app/settings/privacy/page.tsx` | 2.5h |
| 9 | Data export button + download flow | inside privacy page | 45 min |
| 10 | Delete account flow with confirmation | inside privacy page | 1h |
| 11 | Consent checkbox on onboarding | `app/onboarding/page.tsx` | 30 min |
| 12 | Footer links (ToS, Privacy Policy) | `components/layout/Footer.tsx` | 15 min |

**Total estimate:** ~11 hours frontend work
