# WhatsApp Number Collection — UX & Implementation Plan

> Goal: collect a verified phone number (with explicit WhatsApp consent) from signed-in users.  
> Constraint: opt-in is **mandatory before any WhatsApp send** — never collect silently.

---

## Where & When to Ask (Three Touch Points)

We use three complementary touch points so no single path is the only chance.

| Touch point | When it fires | Audience | Skip behaviour |
|---|---|---|---|
| **A — Onboarding Step 2** | Right after topic selection on first sign-in | Every new user | Skip → preference saved as `declined_at_onboarding` |
| **B — Post-session nudge banner** | After user completes their 3rd chat session | Users who skipped onboarding step | Dismiss → suppress for 30 days |
| **C — Profile settings page** | User visits `/profile` at any time | Any signed-in user | Always available |

---

## Touch Point A — Onboarding Step 2 (`OnboardingModal.tsx`)

### Current flow
```
Sign in → OnboardingModal (topic picker) → /learn
```

### New flow
```
Sign in → OnboardingModal Step 1 (topic picker) → Step 2 (WhatsApp opt-in) → /learn
```

### Step 2 UI

```
┌─────────────────────────────────────────┐
│  ✦                                      │
│  Get updates that matter to you         │
│  We'll notify you when something        │
│  connects to your learning.             │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │ +91  │  98765 43210              │   │  ← phone input with country code picker
│  └──────────────────────────────────┘   │
│                                         │
│  [ Enable WhatsApp notifications ]      │  ← primary CTA (violet)
│                                         │
│  Skip for now                           │  ← text link, equally prominent
│                                         │
│  By continuing you agree to receive     │
│  learning updates on WhatsApp.          │
│  You can opt out anytime in settings.   │
└─────────────────────────────────────────┘
```

### Component changes (`OnboardingModal.tsx`)

1. Add `step` state: `1 | 2`
2. Step 1 "Start exploring" button → advances to step 2 instead of submitting
3. Step 1 "Skip for now" → skips both steps, submits immediately (existing behaviour)
4. Step 2 submits phone + consent, then calls `dismissOnboarding()` + `navigate('/learn')`
5. Step 2 "Skip for now" → submits without phone, then navigates

### Validation
- Strip non-digits, require 10–15 digits (E.164 range)
- Country code dropdown defaults to user's browser locale (`Intl.DateTimeFormat().resolvedOptions().locale`)
- Show inline error message on invalid format — do not block navigation

---

## Touch Point B — Post-Session Nudge Banner (`Learn.tsx`)

### When it shows
- User is signed in
- `whatsapp_opted_in === false` AND `whatsapp_declined_onboarding === false OR declined > 30 days ago`
- User has completed ≥ 3 chat messages in the current session (tracked by existing `refreshTrigger` counter)

### UI
```
┌─────────────────────────────────────────────────────────────┐
│  📲  Get a nudge when we find a connection in your topics   │
│  +91 [ phone number       ]  [ Turn on WhatsApp ]  [ × ]   │
└─────────────────────────────────────────────────────────────┘
```

- Appears as a fixed banner at the bottom of the center chat panel
- Dismissing sets a `localStorage` key `ecalt_wa_nudge_dismissed` with a timestamp
- On submit, same API call as Touch Point A

---

## Touch Point C — Profile / Notification Settings Page

### New route: `/profile`

New page at `frontend/src/pages/Profile.tsx`.

```
┌──────────────────────────────────────────────────────┐
│  Profile                                             │
│                                                      │
│  Display name   Biswambar Pradhan                    │
│  Email          developer@gmail.com                  │
│                                                      │
│  ─── Notifications ─────────────────────────────    │
│                                                      │
│  Email updates              [ ● ON  ]                │
│                                                      │
│  WhatsApp notifications     [ ○ OFF ]                │
│    +91 [ 98765 43210 ]                               │
│    [ Save & enable WhatsApp ]                        │
│                                                      │
│  Quiet hours  From [ 22:00 ] to [ 07:00 ]            │
│  Timezone     [ Asia/Kolkata ▾ ]                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

- Add `/profile` to `App.tsx` routes (auth-gated, redirects to `/` if not signed in)
- Add "Profile" link to `Navigation.tsx` user avatar dropdown

---

## Backend Changes Required

### 1. DB — `notification_preferences` table (from Phase 1 of notification plan)

Extend with two extra columns:
```sql
whatsapp_declined_onboarding  BOOLEAN DEFAULT FALSE
whatsapp_nudge_last_dismissed TIMESTAMPTZ   -- tracks 30-day suppression
```

### 2. New API endpoints

```
GET   /api/v1/notifications/preferences
      → returns { email_enabled, whatsapp_enabled, whatsapp_opted_in,
                  whatsapp_phone, quiet_hours_start, quiet_hours_end, timezone }

PATCH /api/v1/notifications/preferences
      body: { whatsapp_phone?, whatsapp_opted_in?, email_enabled?,
              quiet_hours_start?, quiet_hours_end?, timezone? }
      → upserts notification_preferences row for the current user

POST  /api/v1/notifications/whatsapp/opt-in
      body: { phone: "+919876543210" }
      → sends Twilio WhatsApp message: "Reply YES to confirm ECALT notifications"
      → stores phone + sets whatsapp_opted_in=FALSE (pending confirmation)

POST  /api/v1/notifications/whatsapp/confirm
      body: { phone: "+919876543210" }
      → sets whatsapp_opted_in=TRUE
      → (in dev: skip Twilio, just set opted_in=TRUE)
```

### 3. `users.py` — expose notification status on `/me`

Extend the `UserProfile` response with:
```python
whatsapp_opted_in: bool = False
has_notification_prefs: bool = False
```
So the frontend knows at sign-in whether to show touch points without an extra API call.

---

## Frontend New Files / Changes

| File | Change |
|---|---|
| `components/OnboardingModal.tsx` | Add step 2 — phone input + consent checkbox |
| `pages/Profile.tsx` | New page — user profile + notification settings |
| `pages/Learn.tsx` | Post-session nudge banner (Touch Point B) |
| `App.tsx` | Add `/profile` route |
| `components/Navigation.tsx` | Add "Profile" link to user avatar menu |
| `lib/api.ts` | Add `getNotificationPrefs()`, `saveNotificationPrefs()`, `optInWhatsApp()` |

---

## Consent & Legal Requirements

- WhatsApp opt-in copy: _"By enabling, you agree to receive learning updates via WhatsApp. Reply STOP to opt out anytime."_ — shown on both onboarding and profile page.
- Phone number stored in E.164 format only.
- `whatsapp_opted_in` never set to `TRUE` server-side unless Twilio confirmation is received (production) or explicit dev bypass.
- One-click opt-out: `DELETE /api/v1/notifications/preferences/whatsapp` sets `whatsapp_opted_in=FALSE`, `whatsapp_phone=NULL`.
- GDPR: phone number included in any future "delete my account" flow.

---

## Implementation Order

1. Backend: `notification_preferences` table + `PATCH /api/v1/notifications/preferences` endpoint
2. Backend: extend `/api/v1/users/me` to return `whatsapp_opted_in`
3. Frontend: `OnboardingModal` Step 2 (Touch Point A) — highest reach, implement first
4. Frontend: `Profile.tsx` + `/profile` route (Touch Point C)
5. Frontend: `Navigation.tsx` profile link
6. Backend + Frontend: Twilio opt-in confirm flow (`opt-in` + `confirm` endpoints)
7. Frontend: Post-session nudge banner in `Learn.tsx` (Touch Point B) — lowest priority
