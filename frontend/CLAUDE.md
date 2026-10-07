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
| Auth | Firebase v12 — Google popup sign-in **and** email/password (managed kids' accounts) |
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

There is no frontend test suite — `npm run build` (which runs `tsc`) is the correctness gate. Unused locals/params fail the build.

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
│   ├── razorpay.ts              # loadRazorpayScript() + order/subscription response types
│   ├── ThemeContext.tsx         # light/dark, localStorage.ecalt_theme, exposes isDark
│   ├── ToastContext.tsx         # addToast(message, type), 3.2 s auto-dismiss
│   ├── firebase.ts              # Firebase app/auth/GoogleAuthProvider singletons
│   ├── usePageTitle.ts, useReducedMotion.ts
├── pages/                       # One file per route (see Routes)
│   └── admin/                   # Admin page split: tabs/, components/, hooks/, types, utils, constants
└── components/
    ├── auth/                    # BirthYearGate, Under13Block, ParentalConsentForm (+ ConsentSentScreen)
    ├── family/AddChildWizard.tsx
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
| `/kids-login` | KidsLogin | Email/password sign-in for parent-created child accounts |
| `/sign-in`, `/get-started`, `*` | ComingSoon | Placeholder / 404 |

---

## Provider Tree

```
HelmetProvider
  ThemeProvider
    AuthProvider
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
- `signInWithEmail(email, password)` — used by `/kids-login` for managed child accounts created by a parent.
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
- Adds `X-Impersonate-Session: <id>` automatically when an admin impersonation session is active (read from `impersonationStore`).
- Non-OK → throws `ApiError` with `.status` and `.detail`. Message is `detail` (string) or `detail.message`. Structured errors look like `{ error, message }` → `apiErrorCode(err)`.
- 204 → `undefined`.
- Base URL: `VITE_API_URL || ''` (empty = same origin).

**Rule: new endpoint calls go in `api.ts` (or `familyApi.ts` for family/consent) using `request()`.** Direct `fetch()` bypasses the impersonation header — only use it for SSE streams or pre-auth bootstrapping.

### Wrapper groups (`api.ts`)
- Spark / session: `askSpark`, `getSessionStatus`
- Journeys: `exploreQuestion`, `previewJourney`, `confirmJourney`, `getJourneys`, `getJourney`, `getJourneySuggestions`
- Marketplace: `getMarketplace`, `toggleJourneyLike`, `forkJourney`, `submitToMarketplace`
- Progress / passport: `getProgress`, `markStepComplete`, `markStepIncomplete`, `getPassport`
- Step content: `getStepContent`, `regenerateStepContent`, `getStepVisual`, `postVisualEvent`, `submitStepFeedback`
- Quiz: `generateQuiz`, `generateQuizSet`, `getQuizHint`, `skipStepQuiz`, `submitQuizAnswer`
- Users / notifications: `getUserProfile`, `completeOnboarding`, `saveProfession`, `get/saveNotificationPrefs`, `optInWhatsApp`, `confirmWhatsApp`, `optOutWhatsApp`
- Chat / knowledge: `getConversations`, `getConversation`, `deleteConversation`, `getKnowledgeNodes`, `getDailySpark`

### `familyApi.ts`
Children CRUD, link-request approve/decline, card verification (start/confirm), child overview/activity/transcript, `getMyFamily`, consent record, `patchChildSettings`, revoke/cancel-revoke/reconsent, `exportChildData`, self consent (`getMyConsent`, `reconsentSelf`), and token-based parent consent (`getConsentStatus`, `decideConsent`, `resendConsentEmail`, `reportConsent`).

### Remaining direct `fetch()` users
`AuthContext` (POST `/users`), `GeoContext`, `PaymentConfig`, `SubscriptionContext`, `ConversationInterface` + `JourneyTutor` (SSE), and older code (`Pricing`, `Profile`, `Welcome`, `Verify`, `MindSignature`, `Admin` + `admin/hooks` + several admin tabs, `KnowledgeUniverse`, `TodaysSpark`, `OnboardingModal`). `pages/Privacy.tsx` is unrouted (`/privacy` redirects to `/profile`). When touching these, prefer migrating to `request()`; if you keep `fetch`, add the impersonation header manually (see `SubscriptionContext`).

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
Tabs: Overview, Plans, AI Providers, Prompts, Notification Templates, Users (with `UserDetailPanel` + impersonation), Coupons, Revenue, Retention, Funnel, Content, Marketplace Queue, Impersonation Log. Data loading lives in `admin/hooks/useAdminData.ts`. Edits are local until "Save". Add a new tab as `admin/tabs/XTab.tsx` and register it in `Admin.tsx`.

**AI prompts edited in the Prompts tab live in the DB (`ai_provider_config`) — they override code defaults in the backend.**

### Impersonation
Admin starts a session from the Users tab → `ImpersonationContext` stores it, `impersonationStore` exposes the id to `request()`, `ImpersonationBanner` shows while active, auto-stops at expiry. All requests then act as the target user; the backend audits them.

### Family / parental accounts
- Parents: `/family` dashboard, `AddChildWizard` (managed child with email/password; card verification where required), `/family/child/:uid` for controls.
- Children: consent flow via the phase machine above; `ReconsentBanner` prompts re-acceptance after a policy-version bump.
- Parents approve consent via emailed `/consent/confirm?token=…` links.

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

Security headers on all routes: `X-Frame-Options: DENY`, `nosniff`, strict referrer, Permissions-Policy, and a strict **CSP**. **Any new third-party script, API host, iframe or backend domain must be added to the CSP in `vercel.json`** (`script-src`, `connect-src`, `frame-src`) or it will silently fail in prod. It currently allows Google/Firebase, Stripe, Razorpay, Vercel analytics/live, and both Railway backends.

---

## Conventions & Gotchas

- **Optimistic updates** for step completion: update state → call API → revert + error toast on failure.
- **Toasts:** `addToast(msg)` success, `addToast(msg, 'error')`, `addToast(msg, 'info')`.
- **Anonymous sparks** use `localStorage.ecalt_sid` (UUID) as `session_id`.
- **Coupon codes** are uppercased client-side before sending.
- **D3 constellation** mutates the DOM directly in a `useEffect`; don't mix React children into it.
- **Home waitlist form is UI-only** — no API call.
- **Plan copy is hardcoded** in `Pricing.tsx` / admin constants — changing copy needs a frontend deploy.
- When a backend feature needs frontend work, the project convention is to document the frontend changes in an md plan (see `../backend/plans/`) before implementing.
