# ECALT Frontend — Developer Reference

ECALT is a React + TypeScript SPA built with Vite and deployed on Vercel. It is entirely client-side (no SSR). All data goes through the FastAPI backend on Railway (`../backend`), reached via same-origin `/api/*` calls that Vercel rewrites (prod) or the Vite proxy forwards (dev).

> **Stray Next.js files — ignore them.** `next.config.mjs`, `next-env.d.ts`, `.next/` and `src/app/**` (layout.tsx, page.tsx, globals.css, …) are leftovers from an abandoned Next.js experiment. They are **not** in `tsconfig.json`'s `include`, not imported anywhere and not built. The real app entry is `src/main.tsx` → `src/App.tsx`. Never add code under `src/app/`.

---

## Stack at a Glance

| Layer | Choice |
|---|---|
| Framework | React 18 (SPA, no SSR) |
| Language | TypeScript 5 (`strict`, `noUnusedLocals`, `noUnusedParameters`) |
| Build tool | Vite 8, dev port 3000 |
| Routing | React Router v6 (`v7_startTransition` + `v7_relativeSplatPath` future flags) |
| Styling | Tailwind CSS v3 (`darkMode: 'class'`) + CSS vars in `index.css` |
| Auth | Firebase v12 — Google popup sign-in only. Children use **profiles** on the parent's login (see Family profiles) |
| Payments | Stripe (global, redirect checkout) + Razorpay (India, in-page checkout.js) |
| Diagrams | mermaid v11 (step diagrams, `securityLevel: 'strict'`), D3 v7 (constellation map) |
| Icons / classes | lucide-react, clsx |
| SEO | react-helmet-async |
| Observability | Sentry `@sentry/react`, Vercel Analytics + Speed Insights |
| Deployment | Vercel (`vercel.json`) — static `dist/` + rewrites |

---

## Commands

```bash
cd frontend
npm install
cp .env.example .env        # fill in Firebase vars
npm run dev                  # localhost:3000; /api/* proxied → VITE_API_URL || localhost:8000
npm run build                # tsc type-check + vite build → dist/   (run this to verify changes)
npm run preview              # serve dist/ at localhost:4173
npm run lint                 # eslint src --ext ts,tsx
```

There is no frontend test suite — **`npm run build` (which runs `tsc`) is the correctness gate.** Unused locals/params fail the build. Run `npm run lint` too, and check UI changes in the browser (light + dark, ~375px width).

`@` alias: `import '@/components/Foo'` → `src/components/Foo` (most code uses relative imports).

---

## Directory Structure

```
frontend/src/
├── main.tsx                     # Sentry init, history.scrollRestoration='manual', createRoot
├── App.tsx                      # Provider tree, lazy routes, post-sign-in gates, global banners
├── index.css                    # CSS vars + component classes (.glass, .glass-card, .btn-primary…)
├── styles/cosmic.css            # Only used by pages/HomeCosmic.tsx
├── lib/
│   ├── api.ts                   # request<T>() + typed wrappers for most endpoints
│   ├── familyApi.ts             # Family / parental-consent endpoint wrappers (uses request())
│   ├── types.ts                 # Shared TS types (Journey, Quiz*, Visual*, …)
│   ├── AuthContext.tsx          # Firebase auth + post-sign-in compliance phase machine + role
│   ├── SubscriptionContext.tsx  # /subscriptions/me — plan, budget, message counts, isAdmin
│   ├── GeoContext.tsx           # /geo/country → country code; isIndia() helper
│   ├── PaymentConfig.tsx        # /subscriptions/config → Stripe publishable key, Razorpay key id
│   ├── ImpersonationContext.tsx # Admin "view as user" sessions (start/stop, expiry timer)
│   ├── impersonationStore.ts    # Module-level session id so api.ts can read it without React
│   ├── ProfileContext.tsx       # Family profiles: picker state, switchTo(), PIN prompt (useProfiles())
│   ├── SchoolContext.tsx        # Schools the account is staff at, active school, can(action) (useSchool())
│   ├── schoolApi.ts             # Schools endpoint wrappers + types, canDo(), schoolErrorMessage()
│   ├── profileStore.ts          # Module-level active profile + parent unlock token for api.ts
│   ├── avatars.ts               # Avatar choices for child profiles
│   ├── razorpay.ts              # loadRazorpayScript() + order/subscription response types
│   ├── ThemeContext.tsx         # light/dark, localStorage.ecalt_theme, exposes isDark
│   ├── ToastContext.tsx         # addToast(message, type), 3.2 s auto-dismiss
│   ├── firebase.ts              # Firebase app/auth/GoogleAuthProvider singletons
│   ├── usePageTitle.ts, useReducedMotion.ts
├── pages/                       # One file per route (see Routes)
│   ├── admin/                   # Admin page split: tabs/, components/, hooks/, types, utils, constants
│   └── school/                  # School staff area: SchoolLayout (shell + outlet), Dashboard, Staff, Settings
└── components/
    ├── auth/                    # BirthYearGate, Under13Block, ParentalConsentForm (+ ConsentSentScreen)
    ├── school/DpaModal.tsx      # Data processing agreement acceptance (school owner)
    ├── family/                  # AddChildWizard, PinPad, PinPrompt, ProfileAvatar,
    │                            # ProfileRouting (picker redirect, KidModeGuard, KidModeNotice)
    ├── journey/JourneyTutor.tsx # In-journey AI tutor chat
    ├── learn/                   # ConversationInterface (SSE chat), KnowledgeUniverse, TodaysSpark,
    │                            # WarmthIndicator, WhatsAppNudgeBanner
    ├── visual/                  # Visual Learning Objects: VisualLearningObject (renderer registry),
    │   ├── renderers/           #   one renderer per renderer_type (process_flow, cycle, timeline, image…)
    │   ├── shared.tsx, telemetry.ts
    ├── constellation/ConstellationMap.tsx   # D3 force layout (bypasses React DOM)
    ├── StepNode.tsx             # Journey step card: lazy content, quiz, feedback, visuals
    ├── QuizCard.tsx, StepFeedbackBar.tsx, StepUpgradePanel.tsx, StepDiagram.tsx
    ├── MarkdownContent.tsx      # Custom markdown renderer (no library) + diagram extraction
    ├── Navigation.tsx, GateModal.tsx, OnboardingModal.tsx, ReconsentBanner.tsx,
    ├── ImpersonationBanner.tsx, AccountPausedScreen.tsx, MindSignatureDisclaimer.tsx,
    └── JourneyCard.tsx, MarketplaceCard.tsx, MissionCard.tsx, Spark*.tsx, PageMeta.tsx, …
```

---

## Routes

All pages are `React.lazy` + `Suspense` (`PageSkeleton` spinner) and wrapped in `<ErrorBoundary>`. The landing page can be swapped to `HomeCosmic` by toggling the commented import at the top of `App.tsx`.

| Path | Page | Notes |
|---|---|---|
| `/` | Home | Guest spark works without account |
| `/learn` | Learn | 3-panel chat hub; redirects to `/` if not authed |
| `/explore` | Explore | Journey generator (`?q=`), preview → confirm flow; auth required |
| `/journeys` | Journeys | Browse/filter journeys |
| `/marketplace` | Marketplace | Community journeys — like / fork |
| `/journey/:id` | Journey | Steps, progress, quizzes, tutor; progress requires auth |
| `/passport` | Passport | Lock screen if not authed (no redirect) |
| `/profile` | Profile | Account, notifications, WhatsApp, privacy/data controls |
| `/privacy` | → `/profile` | Redirect |
| `/privacy-policy`, `/terms`, `/parents`, `/contact` | Static pages | Public |
| `/pricing` | Pricing | Plans + coupon; Stripe or Razorpay depending on geo |
| `/admin` | Admin | No client guard — API 403 bounces non-admins |
| `/mind-signature` | MindSignature | Constellation + narrative + hash |
| `/verify/:hash` | Verify | Public signature lookup |
| `/welcome` | Welcome | Post-sign-up landing |
| `/consent/confirm`, `/consent/report` | ConsentConfirm / ConsentReport | Parent-facing, token in query; child gates suppressed here |
| `/family` | Family | Parent dashboard (children, link requests, add child) |
| `/family/child/:uid` | FamilyChild | Per-child overview, activity, transcripts, settings, consent, export/delete |
| `/profiles` | Profiles | "Who's learning?" picker for accounts with child profiles |
| `/claim` | Claim | Teen (13+) attaches their own Google login to their profile with a parent's code; sign-up gates skipped here |
| `/school`, `/school/classes[/:classId]`, `/school/students`, `/school/staff`, `/school/settings` | school/SchoolLayout + Dashboard / Classes / ClassDetail / Students / Staff / Settings | School staff only (nested routes). Parent-only for `KidModeGuard` |
| `/school/print/cards/:classId` | school/LoginCardsPrint | Printable student login cards (issues new sign-ins); outside the staff shell |
| `/class`, `/class/badge` | ClassSignIn, BadgeSignIn | **Student** sign-in: class code → name/roll → picture password or PIN; badge token in the URL fragment |
| `/my-classes` | StudentHome | School student home (assigned courses) |
| `/school-invite` | SchoolInviteAccept | Staff invite link (`?token=`, moved to sessionStorage at once); exempt from the profile picker |
| `/kids-login` | → `/` | Redirect — child email/password logins were removed |
| `/sign-in`, `/get-started`, `*` | ComingSoon | Placeholder / 404 |

---

## Provider Tree

```
HelmetProvider
  ThemeProvider
    AuthProvider
      ProfileProvider           ← family profiles + PIN prompt (needs useAuth)
      SchoolProvider            ← GET /schools/mine (needs useAuth + useProfiles; skipped in kid mode)
      ImpersonationProvider     ← needs getToken from AuthProvider
        GeoProvider             ← GET /api/v1/geo/country (unauth)
          PaymentConfigProvider ← GET /api/v1/subscriptions/config (unauth)
            SubscriptionProvider
              ToastProvider
                BrowserRouter
                  AppShell      ← Routes + compliance gates + OnboardingModal + ReconsentBanner + ImpersonationBanner
    <Analytics/> <SpeedInsights/>   (inside ThemeProvider, outside AuthProvider)
```

---

## Authentication & Compliance Gates

### Sign-in methods
- `signIn()` — Google popup (`signInWithPopup`). A `signingIn` ref prevents double-invocation.
- `getToken()` — stable (`useCallback` + `userRef`), safe as a `useEffect` dep; Firebase refreshes silently.
- `role: 'learner' | 'parent' | null` comes from the backend profile.

### Post-sign-in phase machine (`postSignInPhase`)
After sign-in (and on page reload with a restored session) AuthContext calls `POST /api/v1/users` and drives:

| Phase | Trigger | UI rendered by `AppShell` |
|---|---|---|
| `birth_year` | `needs_birth_year` | `BirthYearGate` → `completeBirthYear()` |
| `under_13` | hard-blocked age | `Under13Block` |
| `consent_pending` | `account_status === 'parental_consent_pending'` | `ParentalConsentForm` (parent email) |
| `consent_sent` | parent email submitted | `ConsentSentScreen` |
| `none` + `onboarding_done === false` | — | `OnboardingModal` |

- The reload re-check exists so users can't bypass the birth-year gate by refreshing. Don't remove it.
- Consent-pending teens re-POST `/users` with their birth year recovered from the profile (`enterConsentPending`).
- On `/consent/*` routes the child's consent overlays are suppressed (parents often open the link on the child's device); the birth-year gate still shows.

### Account status errors
Backend returns 403 with `detail.error` = `consent_pending` or `account_paused` for blocked accounts. Use `apiErrorCode(err)` from `api.ts` to read it; `AccountPausedScreen` handles the paused case.

### Auth-gating pattern
```tsx
if (!authLoading && !user) { navigate('/', { replace: true }); return null }
if (authLoading) return <Spinner />
```
Never redirect before `loading === false` — a hard refresh would kick the user out.

---

## API Layer

### `request<T>(path, init?, token?)` in `lib/api.ts`
- Sets `Content-Type: application/json`, `Authorization: Bearer <token>` when given.
- Headers come from `authHeaders(token)`: `Authorization`, `X-Impersonate-Session` (admin impersonation, from `impersonationStore`), `X-Profile-Id` (active child profile, from `profileStore`) and `X-Parent-Unlock` (parent PIN unlock).
- On 403 `parent_unlock_required` it opens the PIN prompt (registered by `ProfileContext`) and retries once.
- Non-OK → throws `ApiError` with `.status` and `.detail`. Message is `detail` (string) or `detail.message`. Structured errors look like `{ error, message }` → `apiErrorCode(err)`.
- 204 → `undefined`.
- Base URL: `VITE_API_URL || ''` (empty = same origin).

**Rule: new endpoint calls go in `api.ts` (or `familyApi.ts` for family/consent) using `request()`.** If you must use `fetch()` (SSE streams, file downloads), build headers with `authHeaders(token)` — a call without `X-Profile-Id` silently acts as the parent. The only intentional exceptions are AuthContext's account-level `POST /users` and `GET /users/me` (role) and the admin pages.

### Wrapper groups (`api.ts`)
- Spark / session: `askSpark`, `getSessionStatus`
- Journeys: `exploreQuestion`, `previewJourney`, `confirmJourney`, `getJourneys`, `getJourney`, `getJourneySuggestions`
- Marketplace: `getMarketplace`, `toggleJourneyLike`, `forkJourney`, `submitToMarketplace`
- Progress / passport: `getProgress`, `markStepComplete`, `markStepIncomplete`, `getPassport`
- Step content: `getStepContent`, `regenerateStepContent`, `getStepVisual`, `postVisualEvent`, `submitStepFeedback`
- Quiz: `generateQuiz`, `generateQuizSet`, `getQuizHint`, `skipStepQuiz`, `submitQuizAnswer`
- Users / notifications: `getUserProfile`, `completeOnboarding`, `saveProfession`, `get/saveNotificationPrefs`, `optInWhatsApp`, `confirmWhatsApp`, `optOutWhatsApp`
- Chat / knowledge: `getConversations`, `getConversation`, `deleteConversation`, `getKnowledgeNodes`, `getDailySpark`

### `schoolApi.ts`
Schools (backend `plans/school-courses/`): `getMySchools`, `getSchool`, `updateSchool`, `acceptDpa`, staff (`listStaff`, `inviteStaff`, `revokeInvite`, `changeStaffRole`, `removeStaff` — on yourself it means "leave"), invite links (`previewSchoolInvite` without sign-in, `acceptSchoolInvite`), ECALT admin (`adminListSchools`, `adminCreateSchool`, `adminUpdateSchool`, `adminInviteOwner`). `canDo(role, action)` mirrors the backend permission matrix for hiding controls (the API stays the authority); `schoolErrorMessage(code)` maps school error codes to copy. Budgets are cents in the API, dollars in the admin UI.

### `familyApi.ts`
Children CRUD, link-request approve/decline, card verification (start/confirm), child overview/activity/transcript, `getMyFamily`, consent record, `patchChildSettings`, revoke/cancel-revoke/reconsent, `exportChildData`, self consent (`getMyConsent`, `reconsentSelf`), and token-based parent consent (`getConsentStatus`, `decideConsent`, `resendConsentEmail`, `reportConsent`).

### Remaining direct `fetch()` users
`AuthContext` (POST `/users`), `GeoContext`, `PaymentConfig`, `SubscriptionContext`, `ConversationInterface` + `JourneyTutor` (SSE), and older code (`Pricing`, `Profile`, `Welcome`, `Verify`, `MindSignature`, `Admin` + `admin/hooks` + several admin tabs, `KnowledgeUniverse`, `TodaysSpark`, `OnboardingModal`). `pages/Privacy.tsx` is unrouted (`/privacy` redirects to `/profile`). All of them except AuthContext and admin now use `authHeaders(token)`.

---

## Key Features

### Payments (`Pricing.tsx`)
- Country from `GeoContext`. `isIndia(country) && plan.base_price_inr_paise` → Razorpay; otherwise Stripe.
- **Stripe:** `POST /subscriptions/checkout` → redirect to `checkout_url`.
- **Razorpay:** `loadRazorpayScript()`, backend returns `checkout_type: 'subscription' | 'order'`; open checkout.js with `razorpayKeyId` from `PaymentConfig`, then post the handler response back to the backend for verification.
- Plan copy/icons (`PLAN_DETAILS`) are hardcoded in the frontend; prices/budgets come from the API.
- `CouponApply` uppercases codes, then calls `refresh()` on `SubscriptionContext`.

### Journey page & steps
- `StepNode` lazy-loads content on first expand and caches it. Content can include quizzes (`QuizCard`), feedback (`StepFeedbackBar`), budget upsell (`StepUpgradePanel`), and a Visual Learning Object.
- Progress is sequential and toggled optimistically by the parent page; revert + toast on error.
- `JourneyTutor` is an SSE tutor chat scoped to the journey.

### Visual Learning Objects (`components/visual/`)
`VisualLearningObject` maps backend `renderer_type` → renderer via a plain registry object. Unknown types render nothing (forward-compat). To add a pattern: create `renderers/XRenderer.tsx` and register one line. Interaction/completion events go through `telemetry.ts` → `postVisualEvent`. All visual features are gated by backend `VISUAL_*` flags — a disabled flag means the API returns no visual.

### MarkdownContent + diagrams
Custom renderer (no markdown lib). First peels out one ` ```mermaid ` fence or one inline `<svg>` (server-sanitized) so the block splitter can't break it; `StepDiagram.MermaidDiagram` renders mermaid with `securityLevel: 'strict'`, theme-aware via `isDark`. Then handles `##` headings, `- ` lists, `**bold**`, and "Try This" callouts; anything else is a paragraph. Diagram failures degrade to nothing.

### Chat SSE (`ConversationInterface`, `JourneyTutor`)
`fetch` + `ReadableStream` (not `EventSource` — needs POST body). Parse `data: ` lines across chunk boundaries; events `start` (conversation_id), `token`, `done`. A 402 before streaming removes the speculative messages and shows `UpgradePrompt`.

### Budget exhaustion (402)
Backend returns 402 with `detail = { error, upgrade_url: '/pricing' }`. Chat → `UpgradePrompt`; step content → `StepUpgradePanel`; Explore → error block.

### Admin (`pages/Admin.tsx` + `pages/admin/`)
Tabs: Overview, Plans, AI Providers, Prompts, Notification Templates, Users (with `UserDetailPanel` + impersonation), Coupons, Revenue, Retention, Funnel, Content, Marketplace Queue, Schools (create/suspend/terminate schools, seats, AI budget, owner invites; says so when the backend's `SCHOOLS_ENABLED` is off), Impersonation Log. Data loading lives in `admin/hooks/useAdminData.ts`. Edits are local until "Save". Add a new tab as `admin/tabs/XTab.tsx` and register it in `Admin.tsx`.

**AI prompts edited in the Prompts tab live in the DB (`ai_provider_config`) — they override code defaults in the backend.**

### Impersonation
Admin starts a session from the Users tab → `ImpersonationContext` stores it, `impersonationStore` exposes the id to `request()`, `ImpersonationBanner` shows while active, auto-stops at expiry. All requests then act as the target user; the backend audits them.

### Family / parental accounts
- Parents: `/family` dashboard, `AddChildWizard` (verification where required), `/family/child/:uid` for controls.
- **Verification** (backend `plans/family-profiles/parental-consent-verification.md`): under-13s everywhere and all minors in India need the parent verified. A parent with a **paid subscription** is verified automatically — `createChild` returns `verification_required: false` and the profile is active. Otherwise "Verify with card" calls `startCardVerification` and redirects to Stripe. For a paying parent with an already-pending profile, `startCardVerification` returns `status: 'verified'` and a `checkout_url` pointing at `/family`, so the existing redirect just reloads the dashboard. Don't assume `checkout_url` is always a Stripe URL.
- Teens: consent flow via the phase machine above; `ReconsentBanner` prompts re-acceptance after a policy-version bump.
- Parents approve consent via emailed `/consent/confirm?token=…` links.

### Schools (`../backend/plans/school-courses/`)
- Staff are ordinary adult accounts. `SchoolContext` loads `GET /schools/mine` once per session (never in kid mode or for school students); the nav shows **School** when it's non-empty. A 404 (backend flag off) just means no school UI.
- `/school` routes are nested under `SchoolLayout`, which loads the active school and passes `{school, setSchool, reload}` to child pages via `useSchoolPage()`. 403 `school_access_suspended` → full-page notice; 404 `school_not_found` → refresh the school list.
- Staff calls (everything under `/schools/{id}`) need the parent PIN unlock when the account has family profiles — `request()` prompts for it automatically.
- `AuthContext.accountKind` (`'account' | 'profile' | 'school_student'`) comes from `POST /users`; school students skip every sign-up gate. `isStudentUid(uid)` (`stu_` prefix) is available immediately after Firebase restores a session — use it to skip parent/staff-only lookups (profiles, subscription, reconsent, schools) and to pick the student `Navigation` variant.
- **Students:** `signInWithClassToken(customToken)` uses `browserSessionPersistence` (shared classroom devices). `StudentGuard` (`ProfileRouting.tsx`) keeps students on `/my-classes`, `/journey/:id`, `/class*` and legal pages. `request()` turns a 401 `school_session_expired` into sign-out + `/class?expired=1`. Picture-password icons live in `lib/pictureIcons.ts` — **never reorder** (the backend stores indices).
- Full contract and what's built vs planned: `../backend/plans/school-courses/frontend-changes.md`.

### Family profiles
Children use ECALT as **profiles on the parent's Google login** — no child email or password. Contract: `../backend/plans/family-profiles/`.
- `lib/profileStore.ts` (module-level, like `impersonationStore`): active profile per account in `localStorage` (`ecalt.activeProfile.<uid>`), parent unlock token in `sessionStorage` (cleared on entering a child profile), PIN-prompt hook for `api.ts`.
- `lib/ProfileContext.tsx` (`useProfiles()`): loads `GET /family/profiles`; exposes `isKidMode`, `activeProfile`, `needsPicker`, `switchTo(uid)` (PIN to leave a child profile; full page reload so every context restarts as the new profile), `ensureParentUnlock(reason)` (call before raw-fetch parent actions: checkout, export, delete). Renders `PinPrompt`.
- `components/family/ProfileRouting.tsx`: picker redirect (to `/profiles` until the device picks), `KidModeGuard` (parent-only pages → "for grown-ups" screen), `KidModeNotice` (disclosure to the child/teen).
- In kid mode: Family/Admin nav hidden, `/family`, `/pricing`, `/profile`, `/admin`, `/welcome` guarded, onboarding skips WhatsApp, `ReconsentBanner` hidden.
- `AddChildWizard`: set PIN (if none) → name + avatar + birth → consent → create profile → card verification when required. `FamilyChild` settings has "Give them their own login" (claim code, 13+).
- 403 codes: `parent_unlock_required` (PIN), `parent_profile_required` (switch to parent), `profile_not_allowed` (stale profile → picker).
- **Leaving a child profile:** the PIN calls (`/family/pin/verify`, `/family/pin/reset`) go out while `X-Profile-Id` is still set, and the backend accepts them on purpose. Every other parent-only call made from kid mode gets `parent_profile_required` — switch to the parent with `switchTo(account.uid)` first.
- **Stuck in a child profile on your own device** (e.g. testing): delete `localStorage` key `ecalt.activeProfile.<account uid>` and reload to get the picker.
- **Under-13s never get a login or password** — only a profile on the parent's login. `/claim` is 13+ only.
- Profile users have no email — don't assume `user.email` (the Firebase user is always the parent).

---

## Styling

- CSS vars in `index.css` `:root` / `.dark`: `--bg`, `--surface`, `--card-bg`, `--card-border`, `--t1/2/3`, `--nav-bg`, `--nav-border`, `--scroll-thumb*`, shimmer vars. Dark mode = `dark` class on `<html>` (ThemeContext).
- Component classes in `@layer components`: `.glass`, `.glass-card`, `.light-card`, `.gradient-text`, `.btn-primary`, `.btn-ghost`, `.step-connector`, `.hero-dot-grid`.
- Most components use Tailwind `dark:` variants directly rather than the `theme-*` color mappings.
- Keyframes `slide-up`, `gradient-x`, `shimmer` exist in both `index.css` and `tailwind.config.ts` on purpose (`animate-in` is a plain class Tailwind JIT can't see).
- Respect `useReducedMotion()` for new animations.
- Mobile responsiveness matters — Learn hides side panels below `lg`; test at ~375px.

---

## Environment Variables (`VITE_` prefix required)

| Variable | Required | Purpose |
|---|---|---|
| `VITE_FIREBASE_API_KEY` | Yes | Firebase API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Yes | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Yes | Firebase project ID (must match backend `FIREBASE_PROJECT_ID`) |
| `VITE_API_URL` | No | API base / Vite proxy target. Empty in prod (same-origin) |
| `VITE_SENTRY_DSN` | No | Sentry not initialised if absent |

Stripe/Razorpay public keys are **not** env vars — they come from `/api/v1/subscriptions/config` at runtime.

---

## Deployment (Vercel)

`vercel.json` (build `npm run build`, output `dist/`):

1. `/sitemap.xml` → prod Railway `/api/v1/sitemap`
2. `/api/*` on host `ecalt-dev.vercel.app` or `ecalt-git-feature-dev-…vercel.app` → **dev** backend `ecalt-api-dev.up.railway.app`
3. `/api/*` (everything else) → **prod** backend `ecalt-production.up.railway.app`
4. `/(.*)` → `/` (SPA fallback)

Branches: `feature/dev` → dev preview + dev backend; `master` → production.

Security headers on all routes: `X-Frame-Options: DENY`, `nosniff`, strict referrer, Permissions-Policy, and a strict **CSP**. **Any new third-party script, API host, iframe or backend domain must be added to the CSP in `vercel.json`** (`script-src`, `connect-src`, `frame-src`) or it will silently fail in prod. It currently allows Google/Firebase, Stripe, Razorpay, Vercel analytics/live, and both Railway backends. `script-src` has **no `'unsafe-inline'`** (#25): no inline `<script>` in `index.html`, no `on*=` attributes in injected HTML, no `eval`/`new Function` — load scripts from an allowed host instead. `e2e/csp.authed.spec.ts` fails on any blocked script.

---

## Conventions & Gotchas

- **Optimistic updates** for step completion: update state → call API → revert + error toast on failure.
- **Toasts:** `addToast(msg)` success, `addToast(msg, 'error')`, `addToast(msg, 'info')`.
- **Anonymous sparks** use `localStorage.ecalt_sid` (UUID) as `session_id`.
- **Coupon codes** are uppercased client-side before sending.
- **D3 constellation** mutates the DOM directly in a `useEffect`; don't mix React children into it.
- **Home waitlist form is UI-only** — no API call.
- **Plan copy is hardcoded** in `Pricing.tsx` / admin constants — changing copy needs a frontend deploy.
- **Stray `src/app/` Next.js files** — never edit or import them (see top of file).
- When a backend feature needs frontend work, the project convention is to document the frontend changes in an md plan (see `../backend/plans/<feature>/frontend-changes.md`) before implementing.

---

## Common Tasks

| Task | Where |
|---|---|
| New page | `pages/X.tsx` (default export) → `React.lazy` import + `<Route>` wrapped in `<ErrorBoundary>` in `App.tsx` |
| New API call | Typed wrapper in `lib/api.ts` (or `familyApi.ts`) using `request()`; shared types in `lib/types.ts` |
| New admin tab | `pages/admin/tabs/XTab.tsx`, register in `pages/Admin.tsx` |
| New visual renderer | `components/visual/renderers/XRenderer.tsx` + one line in the `VisualLearningObject` registry |
| New external domain/script | Add to the CSP in `vercel.json` |
| New env var | `VITE_` prefix, add to `.env.example` and Vercel project env |

## Before You Finish

1. `npm run build` passes (type-check + bundle).
2. `npm run lint` is clean.
3. Auth-gated pages wait for `authLoading === false` before redirecting.
4. New API calls go through `request()` (impersonation header preserved).
5. UI works in light and dark mode and at ~375px; animations respect `useReducedMotion()`.
6. Any new third-party host is in the `vercel.json` CSP.
