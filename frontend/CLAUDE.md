# ECALT Frontend — Developer Reference

ECALT is a React + TypeScript SPA deployed on Vercel. The frontend is entirely client-side with no SSR. All data fetching goes through a FastAPI backend on Railway, proxied via Vercel rewrites.

---

## Stack at a Glance

| Layer | Choice |
|---|---|
| Framework | React 18 (SPA, no SSR) |
| Language | TypeScript 5 |
| Build tool | Vite 5, port 3000 |
| Routing | React Router v6 (client-side) |
| Styling | Tailwind CSS v3 (class dark mode) + custom CSS vars in `index.css` |
| Auth | Firebase v12 SDK — Google sign-in only |
| Icons | lucide-react |
| Conditional classes | clsx |
| SEO | react-helmet-async |
| Visualisation | D3 v7 (constellation map) |
| Observability | Sentry `@sentry/react`, Vercel Analytics + Speed Insights |
| Deployment | Vercel (`vercel.json`) |

---

## Directory Structure

```
frontend/
├── src/
│   ├── main.tsx                    # Entry — Sentry init, scroll restoration, ReactDOM.createRoot
│   ├── App.tsx                     # Provider tree, all lazy routes, OnboardingModal gate
│   ├── index.css                   # CSS vars, .glass/.glass-card/.btn-primary/.shimmer etc.
│   ├── lib/
│   │   ├── api.ts                  # All typed fetch wrappers (most API calls live here)
│   │   ├── types.ts                # Shared TS types: Journey, Mission, SparkRequest, etc.
│   │   ├── AuthContext.tsx         # Firebase auth state + signIn/signOut/getToken
│   │   ├── SubscriptionContext.tsx # Budget/plan state from /subscriptions/me
│   │   ├── ThemeContext.tsx        # light/dark toggle, persisted to localStorage
│   │   ├── ToastContext.tsx        # Toast system (3.2 s auto-dismiss)
│   │   ├── firebase.ts             # Firebase app + auth + GoogleAuthProvider singletons
│   │   └── usePageTitle.ts         # document.title hook
│   ├── pages/
│   │   ├── Home.tsx                # Landing + free-tier spark (phase state machine)
│   │   ├── Learn.tsx               # 3-panel learning hub (auth required)
│   │   ├── Explore.tsx             # Full AI journey generator (auth required)
│   │   ├── Journeys.tsx            # Browse + filter all journeys
│   │   ├── Journey.tsx             # Single journey with step nodes + related
│   │   ├── Passport.tsx            # Capability passport (auth required)
│   │   ├── Pricing.tsx             # Plan cards + coupon input
│   │   ├── Admin.tsx               # Admin panel — stats / plans / AI config / users / coupons
│   │   ├── MindSignature.tsx       # Constellation + narrative + hash verification
│   │   ├── Verify.tsx              # Public signature lookup by hash
│   │   └── ComingSoon.tsx          # Placeholder for /sign-in, /get-started, 404
│   └── components/
│       ├── Navigation.tsx          # Fixed top nav — desktop + mobile, auth state
│       ├── GateModal.tsx           # Auth gate: shown when guest tries mission/upgrade
│       ├── OnboardingModal.tsx     # Topic picker shown once on first sign-in
│       ├── StepNode.tsx            # Journey step card with expand-to-load lesson content
│       ├── JourneyCard.tsx         # Journey grid card (Journeys page)
│       ├── MarkdownContent.tsx     # Lightweight custom markdown renderer
│       ├── ErrorBoundary.tsx       # React error boundary wrapping each route
│       ├── PageMeta.tsx            # react-helmet-async SEO tags + JSON-LD
│       ├── ThemeToggle.tsx         # Light/dark toggle button
│       ├── GoogleSignInButton.tsx  # Standardised Google sign-in button
│       ├── UpgradePrompt.tsx       # In-chat upgrade nudge on budget exhaustion
│       ├── CuriosityInput.tsx      # Explore page question input
│       ├── SparkMeter.tsx          # Spark dot counter
│       ├── SparkAnswer.tsx         # Spark result display component
│       ├── MissionCard.tsx         # Mission display card
│       ├── learn/
│       │   ├── ConversationInterface.tsx  # SSE streaming chat panel
│       │   ├── KnowledgeUniverse.tsx      # Right panel — concept node tags
│       │   ├── TodaysSpark.tsx            # Left panel — daily personalized question
│       │   └── WarmthIndicator.tsx        # Message count progress indicator
│       └── constellation/
│           └── ConstellationMap.tsx       # D3 force-layout constellation visualization
├── .env                            # Local secrets (VITE_* prefix)
├── .env.example                    # Template for required vars
├── tailwind.config.ts              # Extends CSS vars as Tailwind colors, all keyframes
├── vite.config.ts                  # Port 3000, /api proxy, @ alias → src/
├── vercel.json                     # /api/* → Railway, SPA fallback, security headers
├── tsconfig.json
└── package.json
```

---

## Routes

All pages are lazy-loaded with `React.lazy`. `PageSkeleton` (centered spinner) is the `Suspense` fallback. Each route is wrapped in `<ErrorBoundary>`.

| Path | Page | Auth behaviour |
|---|---|---|
| `/` | Home | Guest allowed; spark works without account |
| `/learn` | Learn | Redirect to `/` if not authed |
| `/explore` | Explore | Redirect to `/` if not authed |
| `/journeys` | Journeys | Public |
| `/journey/:id` | Journey | Public; progress tracking requires auth |
| `/passport` | Passport | Shows lock screen if not authed (no redirect) |
| `/pricing` | Pricing | Public |
| `/admin` | Admin | No client guard; API returns 403 for non-admins |
| `/mind-signature` | MindSignature | No client guard |
| `/verify/:hash` | Verify | Public |
| `/sign-in` | ComingSoon | — |
| `/get-started` | ComingSoon | — |
| `*` | ComingSoon (404) | — |

---

## Context Provider Tree

Providers wrap in this order (outer → inner):

```
HelmetProvider
  ThemeProvider         ← light/dark, localStorage.ecalt_theme
    AuthProvider        ← Firebase auth, exposes user/loading/needsOnboarding/signIn/signOut/getToken
      SubscriptionProvider  ← /subscriptions/me, exposes plan/usedCents/budgetCents/isLimited/isAdmin
        ToastProvider   ← addToast(message, type), 3.2 s dismiss
          BrowserRouter ← React Router
            AppShell    ← Routes + OnboardingModal (when needsOnboarding=true)
```

`Analytics` and `SpeedInsights` are rendered outside `ThemeProvider` at the App root level (they are side-effect only and need no context).

---

## Authentication

### Firebase setup (`lib/firebase.ts`)

Three env vars are required: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`. Only Google OAuth is wired up (`GoogleAuthProvider`).

### AuthContext flow

1. `user` state is **initialized synchronously** from `firebaseAuth.currentUser` (avoids 1 s flash on reload).
2. `onAuthStateChanged` fires async, finalises `user` and sets `loading = false`.
3. `signIn` calls `signInWithPopup`. A `signingIn` ref prevents double-invocations.
4. After a successful sign-in, `POST /api/v1/users` is called to upsert the user record.
5. If the response has `onboarding_done === false`, `needsOnboarding` is set → `OnboardingModal` is rendered globally from `AppShell`.
6. `getToken()` calls `user.getIdToken()` — Firebase silently refreshes if expired. It is **stable** (via `useCallback` + `useRef`) so it can be a `useEffect` dependency without loops.
7. `signOut` calls Firebase sign-out and resets `needsOnboarding`.

### Token pattern

Every authenticated call follows:
```tsx
const token = await getToken()
if (!token) return  // user signed out mid-request
// call API with Authorization: Bearer ${token}
```

---

## API Layer (`lib/api.ts`)

All typed wrappers call the internal `request<T>()` helper:
- Adds `Content-Type: application/json`
- Adds `Authorization: Bearer <token>` when token provided
- On non-OK: reads JSON body, attaches `.status` (number) and `.detail` (unknown) to the thrown `Error`

**Base URL:** `VITE_API_URL || ''`
- Empty string in production = same-origin → Vercel rewrites handle routing to Railway.
- In dev = Vite proxy forwards `/api/*` → `localhost:8000`.

### Typed API functions

| Function | Method + Path | Notes |
|---|---|---|
| `askSpark(body, token?)` | POST /api/v1/spark | Token optional (guest allowed) |
| `getSessionStatus(sessionId)` | GET /api/v1/session/{id} | No auth |
| `exploreQuestion(body, token)` | POST /api/v1/explore | Required auth |
| `getJourneys(token?)` | GET /api/v1/journeys | Optional auth (guest gets curated only) |
| `getJourney(id, token?)` | GET /api/v1/journeys/{id} | Optional auth |
| `getProgress(journeyId, token)` | GET /api/v1/progress/{id} | Required auth |
| `markStepComplete(jId, sId, token)` | POST /api/v1/progress/{j}/{s} | Required auth |
| `markStepIncomplete(jId, sId, token)` | DELETE /api/v1/progress/{j}/{s} | Required auth |
| `getPassport(token)` | GET /api/v1/passport | Required auth |
| `getStepContent(jId, sId, token?)` | GET /api/v1/journeys/{j}/steps/{s}/content | Optional auth |
| `getUserProfile(token)` | GET /api/v1/users/me | Required auth |
| `completeOnboarding(token)` | PATCH /api/v1/users/me/onboarding | Required auth |
| `getConversations(token)` | GET /api/v1/chat/conversations | Required auth |
| `getConversation(id, token)` | GET /api/v1/chat/conversations/{id} | Required auth |
| `deleteConversation(id, token)` | DELETE /api/v1/chat/conversations/{id} | Required auth |
| `getKnowledgeNodes(token)` | GET /api/v1/knowledge/nodes | Required auth |
| `getDailySpark(token)` | GET /api/v1/knowledge/spark | Required auth |

### Direct `fetch()` calls outside `api.ts`

Some components call the API directly without going through the typed wrappers:

| Component | Endpoint(s) |
|---|---|
| `AuthContext` | POST /api/v1/users (on sign-in) |
| `OnboardingModal` | PATCH /api/v1/users/me/interests |
| `ConversationInterface` | POST /api/v1/chat/stream (SSE — cannot use `request()`) |
| `SubscriptionContext` | GET /api/v1/subscriptions/me |
| `Pricing` | GET /api/v1/subscriptions/plans, POST /api/v1/subscriptions/checkout |
| `Pricing (CouponApply)` | POST /api/v1/coupons/apply |
| `Admin` | All `/admin/*` and `/coupons/admin/*` endpoints |
| `MindSignature` | GET/POST /api/v1/mind-signature/me, /generate, /generate/force |
| `KnowledgeUniverse` | GET /api/v1/knowledge/nodes, GET /api/v1/mind-signature/me |
| `TodaysSpark` | GET /api/v1/knowledge/spark |

---

## Pages

### Home (`/`)

Phase state machine:
```
hero → loading → sparked
               ↓ (429 = rate limit)
             GateModal(reason='limit')
                        ↓ (on "Start Mission" or "Save My Path")
                      GateModal(reason='mission')
hero → loading → error
```

- `ecalt_sid` in localStorage is the anonymous session ID for spark rate tracking.
- `getSessionStatus(sessionId)` is called on mount to restore the spark counter after page reload.
- When a signed-in user visits, `getPassport` + `getUserProfile` are called in parallel to show a "Continue" card and streak badge.
- `GateModal` auto-closes and navigates to `/explore?q={question}` when `user` changes to non-null while the modal is open.
- Keyboard shortcut: `/` focuses the ask input (guarded to not fire inside `input`/`textarea`).
- The email capture form (`waitlistDone` state) is purely UI — it does not call any API.

### Learn (`/learn`)

Fixed-height `h-screen` layout. Redirects to `/` if not authenticated.

3-panel layout (flex row):
- **Left** (hidden below `lg`): `TodaysSpark` — loads from `/api/v1/knowledge/spark`, click pre-fills the chat input via `sparkInput` prop.
- **Center**: `ConversationInterface` — SSE streaming chat.
- **Right** (hidden below `lg`): `KnowledgeUniverse` — concept tags from `/api/v1/knowledge/nodes`. `refreshTrigger` counter causes refetch after each message completes.

`isAdmin` from `SubscriptionContext` adds an "Admin" link to the top bar.

### Explore (`/explore`)

Auth guard redirects to `/` for guests. The question comes from `?q=` search param.

`fetchJourney` calls `exploreQuestion`, then sets `journey` and `steps` state. Steps start with `completed: false` (no progress is loaded on this page — that's `Journey.tsx`'s job).

Optimistic step toggle: `setSteps` immediately then reconciles on API error.

### Journey (`/journey/:id`)

Loads journey + progress in parallel. Related journeys are fetched best-effort after main load (scored by shared tag count, top 3).

`CompletionOverlay` is shown when all steps become completed (checked inside the `setSteps` callback to avoid stale closure).

`navigator.share` is tried first for the share button; falls back to `navigator.clipboard.writeText`.

### Passport (`/passport`)

Shows a lock screen (no redirect) for guests. Loads `getPassport` + `getUserProfile` in parallel.

`fullyCompleted` = journeys where `fully_completed === true`. `inProgress` = the rest.

### Pricing (`/pricing`)

Loads plan list from `GET /api/v1/subscriptions/plans` (public, no auth). Plan details (icons, feature bullets, CTA text) are **hardcoded** in `PLAN_DETAILS` — they are not returned by the API.

Checkout: `POST /api/v1/subscriptions/checkout` → redirects `window.location.href` to Stripe's `checkout_url`.

`CouponApply` sub-component (at page bottom): calls `POST /api/v1/coupons/apply`. On success, calls `refresh()` from `SubscriptionContext` to update the budget display.

The highlighted plan defaults to `?plan=individual` unless overridden via search param.

### Admin (`/admin`)

All data is loaded in a single `Promise.all` of 6 API calls on mount. If the plans response returns 403, navigates to `/`.

Five tabs:
1. **Overview** — stat cards + active plan summary
2. **Pricing Plans** — visual preview + editable form per plan (price cents, token budget, Stripe price ID, max seats)
3. **AI Providers** — usage table by model, daily bar chart (14 days), per-interaction-type provider/model dropdowns
4. **Users** — filterable list with admin grant/revoke toggle
5. **Coupons** — create form + list with activate/deactivate toggle

All edits are local state (`edits` / `aiEdits` dicts keyed by ID) and only sent on explicit "Save" click.

### MindSignature (`/mind-signature`)

`fetchSignature` → GET `/api/v1/mind-signature/me`. If `data.signature` is null, shows a generate CTA.

`handleGenerate(force)` → POST to `/generate` (eligibility-checked) or `/generate/force` (unconditional).

`ConstellationMap` receives `signature.constellation_data` (nodes + links already computed server-side).

Verification hash can be copied to clipboard or opened at `/verify/{hash}`.

---

## Components

### Navigation

Fixed top nav (`z-50`). Reads `pathname` to highlight active link.

Link sets:
- **Public** (always shown): Explore, Journeys, Pricing
- **Auth** (only when signed in): Learn, Passport, Mind Signature
- **Admin** (only when `isAdmin`): Admin

Mobile: hamburger opens an overlay dropdown. Backdrop click closes it.

`UserAvatar` falls back to initials in a violet circle when no `photoURL`.

### GateModal

Shown when an anonymous user tries to start/save a mission, or when sparks run out.

`reason` prop controls messaging:
- `'mission'` → "Your mission is ready" + shows mission preview
- `'limit'` → "Free sparks used up"

After `GoogleSignInButton` triggers sign-in, the `useEffect` watching `user` auto-closes the modal and navigates to `/explore?q={question}`.

"Continue as guest" navigates to `/explore` (losing the spark context).

### OnboardingModal

Shown globally from `AppShell` when `needsOnboarding === true`. Cannot be dismissed without at least clicking "Skip" (which still completes onboarding server-side).

On submit: `PATCH /api/v1/users/me/onboarding` + `PATCH /api/v1/users/me/interests` are called in parallel via `Promise.allSettled` (non-fatal). Then `dismissOnboarding()` and `navigate('/learn')`.

### StepNode

Self-contained expand/collapse. Content is loaded lazily on first expand and cached in local state forever (no re-fetch on re-collapse).

States: `loadingContent`, `contentError`, `budgetExceeded` (from 402 response).

The circle button (step number / checkmark) calls `onToggle(step.id)` — the toggle + API call happen in the parent page.

### MarkdownContent

No external library. Splits on double-newlines into blocks, then:
- `## text` → purple `<h4>` with accent bar
- All lines start with `- ` → `<ul>` with ✦ bullets
- Block contains "Try This" → amber callout `<div>`
- `**bold**` inline → `<strong>`
- Otherwise → `<p>`

### ConversationInterface

Direct `fetch('/api/v1/chat/stream', ...)` returning `text/event-stream`. Uses the native `ReadableStream` reader (no EventSource — needed for POST body support).

SSE parsing:
- Lines must start with `data: ` prefix
- `type: "start"` → captures `conversation_id`
- `type: "token"` → appends to last assistant message
- `type: "done"` → clears `streaming: true` flag

Buffer accumulates partial lines across chunk boundaries before splitting on `\n`.

402 response before streaming begins → removes the speculative user+assistant messages from state, shows `UpgradePrompt`.

`onMessageComplete` callback triggers `KnowledgeUniverse` refresh (increments `refreshTrigger` counter in Learn).

### KnowledgeUniverse

Fetches knowledge nodes and mind-signature status on mount and whenever `refreshTrigger` increments.

Node text size scales with `strength`: ≥0.8 → `text-sm`, ≥0.55 → `text-xs`, else → `text-[11px]`.

Domain colour map covers all 14 backend domains. Unknown domains fall back to slate.

### TodaysSpark

Calls `GET /api/v1/knowledge/spark` on mount. Fail silently. "Start exploring" button pushes the spark text into `ConversationInterface` via the `onSelect` → `sparkInput` prop chain.

---

## CSS Architecture & Design System

### CSS Custom Properties (`index.css` `:root` / `.dark`)

| Variable | Light | Dark |
|---|---|---|
| `--bg` | `#ffffff` | `#080b14` |
| `--surface` | `#f8fafc` | `#0f1629` |
| `--card-bg` | `#ffffff` | `rgba(15,22,41,0.7)` |
| `--card-border` | `#e2e8f0` | `rgba(30,45,74,0.6)` |
| `--t1` | `#0f172a` | `#f1f5f9` |
| `--t2` | `#475569` | `#94a3b8` |
| `--t3` | `#94a3b8` | `#475569` |
| `--shimmer1/2` | light grays | dark navies |

Dark mode is toggled by adding/removing `dark` class on `document.documentElement`.

### Component Classes (defined in `@layer components`)

| Class | Use |
|---|---|
| `.glass` | Nav pill, input wrappers — translucent white/dark with backdrop-filter |
| `.glass-card` | Cards, panels — solid white (light) / translucent dark with violet hover glow |
| `.light-card` | Home page cards — always white/light-dark, no backdrop filter |
| `.gradient-text` | ECALT logo — animated violet→cyan→amber gradient |
| `.btn-primary` | Violet filled button with focus ring |
| `.btn-ghost` | Transparent text button with hover |
| `.step-connector` | 2px gradient line between step circles |
| `.hero-dot-grid` | Dot pattern SVG background for hero |

### Animations (defined in `tailwind.config.ts`)

| Name | Usage |
|---|---|
| `glow-pulse` | Ambient blur circles on page backgrounds |
| `float` | Floating elements |
| `slide-up` / `animate-in` | Page content entrance |
| `shimmer` / `shimmer-light` / `shimmer-bg` | Loading skeletons |
| `gradient-x` | gradient-text animation |
| `toast-in` | Toast entry |
| `celebration` | CompletionOverlay + OnboardingModal entry |

**Important:** `@keyframes slide-up`, `gradient-x`, and `shimmer` are defined in both `index.css` and `tailwind.config.ts`. The `index.css` versions ensure the keyframes are always emitted even when the Tailwind JIT doesn't see the class names in JSX (e.g., for `animate-in` which is applied as a plain CSS class, not a `animate-slide-up` Tailwind class).

### Tailwind colour extensions

`tailwind.config.ts` maps CSS vars to `theme-{bg,surface,card,border,t1,t2,t3}` colours. These are rarely used in JSX (most components use inline `dark:` variants directly), but the mapping exists.

---

## SEO

`PageMeta` (`components/PageMeta.tsx`) uses `react-helmet-async` Helmet to inject:
- `<title>` — format `{title} | ECALT`, or bare `ECALT` on home
- `<meta name="description">`
- `<link rel="canonical">` (built as `https://ecalt.vercel.app{canonicalPath}`)
- `<script type="application/ld+json">` JSON-LD

JSON-LD schemas used:
- Home: `WebSite` with `SearchAction`
- Journey: `Course` with `CourseInstance`, `educationalLevel`, `teaches`

`vercel.json` security headers applied to all routes:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- CSP: allows `'self'`, Google APIs/Firebase, Vercel analytics, and WebSocket for Vercel preview. Blocks everything else.

---

## Environment Variables

All must be prefixed `VITE_` to be exposed to the browser bundle.

| Variable | Required | Purpose |
|---|---|---|
| `VITE_FIREBASE_API_KEY` | Yes | Firebase project API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Yes | Firebase auth domain (e.g. `proj.firebaseapp.com`) |
| `VITE_FIREBASE_PROJECT_ID` | Yes | Firebase project ID |
| `VITE_API_URL` | No | Override API base URL. Empty = same-origin (default for prod). Set to `http://localhost:8000` to bypass the Vite proxy. |
| `VITE_SENTRY_DSN` | No | Sentry DSN — Sentry not initialised if absent |

---

## Dev Workflow

```bash
cd frontend
npm install
cp .env.example .env        # fill in Firebase vars
npm run dev                  # localhost:3000; /api/* proxied → localhost:8000
```

The backend must be running on port 8000 for API calls to work in dev. The Vite proxy config (`vite.config.ts`) sets the target from `VITE_API_URL` or falls back to `http://localhost:8000`.

```bash
npm run build                # tsc type-check + vite build → dist/
npm run preview              # serve dist/ locally at localhost:4173
npm run lint                 # eslint src --ext ts,tsx
```

**`@` alias:** `import '@/components/Foo'` resolves to `src/components/Foo`.

---

## Deployment (Vercel)

`vercel.json` rewrites:

1. `/sitemap.xml` → `https://ecalt-production.up.railway.app/api/v1/sitemap`
2. `/api/:path*` → `https://ecalt-production.up.railway.app/api/:path*` (all API traffic forwarded to Railway)
3. `/(.*)`  → `/index.html` (SPA fallback for client-side routing)

Build: `npm run build`, output: `dist/`.

No server-side rendering. No Edge Functions. Pure static SPA + proxied API.

---

## Key Design Patterns

### Optimistic updates
`Explore.tsx` and `Journey.tsx` both toggle step completion optimistically:
1. `setSteps(prev => prev.map(...toggle...))` immediately
2. Call API
3. On API error: `setSteps(prev => prev.map(...revert...))`
4. On API error in `Journey.tsx`: also shows error toast

### Auth-gating pattern
Pages that require auth follow:
```tsx
if (!authLoading && !user) {
  navigate('/', { replace: true })  // or show a lock screen
  return null
}
if (authLoading) return <Spinner />
```
Never redirect before `loading = false` — otherwise the user will be kicked out on a hard refresh.

### Non-blocking parallel loads
`Journey.tsx` fires related-journeys fetch as a non-blocking `.catch(() => {})` after the main journey loads. `Home.tsx` fires `getPassport` + `getUserProfile` in `Promise.all` that is never awaited by the render path.

### Admin access (no client guard)
`/admin` has no `isAdmin` route guard. Instead, the `useEffect` on mount checks if the plans API returns 403 and navigates away if so. This avoids flickering on admin users.

### Session ID for anonymous sparks
`getSessionId()` in `Home.tsx`:
```ts
let id = localStorage.getItem('ecalt_sid') || ''
if (!id) { id = crypto.randomUUID(); localStorage.setItem('ecalt_sid', id) }
```
Sent as `session_id` in spark requests to enable server-side rate-gating without auth.

### SSE streaming (not EventSource)
`ConversationInterface` uses the native `fetch` + `ReadableStream` reader instead of `EventSource`. This is required because `EventSource` only supports GET; the chat stream needs POST with a JSON body.

### getToken stability
`getToken` in `AuthContext` is wrapped in `useCallback` with an empty dependency array and reads from a `userRef` (updated by `onAuthStateChanged`). This means:
- The function reference never changes → safe to use as `useEffect` dependency
- Always reads the latest Firebase user → no stale closure on auth state changes

### Budget exhaustion handling
- **Chat (ConversationInterface)**: 402 before streaming → removes speculative messages, shows `UpgradePrompt` inline inside the chat panel.
- **Step content (StepNode)**: 402 on expand → shows "budget exceeded" message with link to `/pricing`.
- **Explore**: 402 error sets `error` state → shown in error block with retry.

### Toast pattern
```tsx
const { addToast } = useToast()
addToast('Step complete ✓')           // success (default)
addToast("Couldn't save", 'error')    // error — rose background
addToast('Info message', 'info')      // info — violet background
```
Auto-dismissed after 3200 ms. Toasts stack vertically from the bottom center.

### Theme toggle
`ThemeContext.toggle()` flips `light` ↔ `dark`, updates `localStorage.ecalt_theme`, and adds/removes `dark` on `document.documentElement`. Tailwind's `darkMode: 'class'` picks it up from there.

---

## Known Quirks

- **No markdown library.** `MarkdownContent` is a custom renderer that handles only `##`, `-` lists, `**bold**`, and "Try This" callouts. Anything outside that subset renders as plain text.
- **D3 constellation.** `ConstellationMap` renders using D3 directly, bypassing React's virtual DOM. Mutations happen in a `useEffect` on `data` prop change.
- **Email capture is fake.** The waitlist form on `Home.tsx` sets `waitlistDone = true` locally but never calls any API.
- **Admin panel plan feature lists are hardcoded.** `PLAN_FEATURES` and `PLAN_DETAILS` in both `Pricing.tsx` and `Admin.tsx` are static objects in the frontend, not returned by the API. Updating plan copy requires a frontend deploy.
- **Coupon codes are uppercased on input.** Both `Pricing.tsx` (CouponApply) and `Admin.tsx` (coupon form) call `.toUpperCase()` on the user's input before sending — matching the backend's storage convention.
- **`Learn` page redirects synchronously.** Because `firebaseAuth.currentUser` initialises synchronously, `loading` may be false immediately on hard reload. The redirect `if (!loading && !user)` fires before the async `onAuthStateChanged` can confirm the session, which could cause a brief incorrect redirect. The `loading: true` initial state in `AuthContext` prevents this — wait for `loading = false`.
