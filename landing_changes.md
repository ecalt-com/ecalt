# Landing Page — Change Plan

## What this document covers

Implementation plan for swapping the ECALT home route (`/`) to a new cosmic-themed landing page (`HomeCosmic.tsx`), while keeping the old page instantly revertable via a single line change in `App.tsx`.

---

## Revert to old page (one line)

In `src/App.tsx`, line 13 is the only toggle:

```tsx
// NEW (cosmic):
const Home = lazy(() => import('./pages/HomeCosmic'))

// OLD (revert by flipping this one line):
// const Home = lazy(() => import('./pages/Home'))
```

Nothing else changes. All routes, context providers, auth flow, and the rest of the app are untouched.

---

## Files

| Action | Path | Notes |
|---|---|---|
| **No change** | `src/pages/Home.tsx` | Old landing page stays exactly as-is |
| **Modify** | `src/App.tsx` | Line 13 only — swap the `Home` lazy import |
| **Modify** | `index.html` | Add 3 Google Font `<link>` tags in `<head>` |
| **Create** | `src/styles/cosmic.css` | All cosmic-specific CSS — imported only by HomeCosmic |
| **Create** | `src/pages/HomeCosmic.tsx` | New landing page component |

No other files are touched. Explore, Learn, Journeys, Passport, Pricing, Admin — all unchanged.

---

## What stays from the old page

| Feature | Where it comes from |
|---|---|
| `<Navigation />` | Kept — sits above the cosmic hero |
| `<PageMeta />` | Kept — same SEO tags |
| `<GateModal />` | Kept — auth gate for the spark CTA |
| `askSpark` / `getSessionStatus` | Kept — S3 field CTA fires the spark flow |
| Session ID (`ecalt_sid`) | Kept — anonymous spark rate tracking |
| Continue card (recent journey) | Kept — shown above hero for signed-in users |
| Streak badge | Kept — shown alongside continue card |

---

## New design sections

### S1 — Hero

- ECALT brand tag (Space Mono, gold)
- Star fact: "Light leaving Proxima Centauri takes 4.2 years…"
- Divider line
- Headline: "Most of what you were taught has the same delay"
- Body copy
- Scroll cue (animated drip line)

No input box in the hero. The spark input lives in S3.

---

### S2 — Knowledge Delay Timeline

- Intro: "These ideas existed long before they reached you"
- Central spine line
- 6 timeline events, alternating left/right:
  - Medicine — Germs cause disease — 40yr delay
  - Physics — Time bends — 55yr delay
  - Psychology — Neuroplasticity — 60yr+ delay
  - Economics — Behavioural irrationality — 32yr delay
  - Computer Science — Neural networks — 70yr+ delay
  - Right now — "Discoveries waiting for you" (lit dot, CTA card)
- Dots light up on scroll via IntersectionObserver
- Mobile: collapses to single-column with left spine

---

### S3 — Personal Gap (integrated with spark flow)

This section replaces the hero spark box from the old page as the primary call to action.

**Field input** (`<input>` + tag cloud):
- User types a field (e.g. "medicine") or clicks a tag
- On Enter / tag click → immediately shows the static gap result from `FIELD_DATA` map (no API call yet — this is instant UI)
- Gap bar animates from 0% → 28% width
- Shows "X–Y year gap" + field insight text

**Gap result CTAs:**

| Button | Behaviour |
|---|---|
| "Close my gap" | Calls `askSpark({ question: field, session_id })` — same as current Home's `handleSpark`. Shows GateModal on 429 (rate limit) or on "Start Mission". If already authed, navigates to `/explore?q={field}` directly. |
| "See my Potential Indicator" | Smooth-scrolls to #s5 |

This means S3 is the functional equivalent of the old hero's `<AskBox>` — it drives the spark session and auth gate the same way.

**State carried over from old Home:**
- `phase` (hero → loading → sparked → error)
- `sessionSparks` (used / remaining)
- `gateOpen` / `gateReason`
- `GateModal` with `mission` + `question` props

---

### S4 — Pricing / Promise

- Headline: "Choose how far you want to close the gap"
- Body copy
- **3 plan cards are visual/marketing only** — they do NOT hardcode prices or hit the API
- Each card's CTA links to `/pricing` (the existing Pricing page handles real plan data, Stripe, coupons)
- "Begin closing the gap" → `/pricing`
- "10 minutes free" → triggers same spark flow as S3 CTA (calls `askSpark`)

---

### S5 — Potential Indicator

- Label + headline: "Not a certificate. A map of your closing gap."
- Canvas constellation (12 nodes, 15 edges, rAF animation)
- Caption copy
- This mirrors the existing MindSignature constellation conceptually but is purely decorative here — no API call, no auth required

---

## CSS approach

All cosmic styles go in `src/styles/cosmic.css`, imported only at the top of `HomeCosmic.tsx`:

```tsx
import '../styles/cosmic.css'
```

This means:
- No bleed into any other page
- Reverting the import in App.tsx also stops the CSS from loading
- No changes to `index.css` or `tailwind.config.ts`

The CSS file contains:
- CSS custom properties (`--void`, `--star`, `--gold`, `--gold2`, `--dim`, etc.)
- Font declarations referencing the Google Fonts added to `index.html`
- All section styles (s1–s5)
- Timeline, gap visual, plan cards, cursor, footer
- `@keyframes` (fadeUp, drip, pulse)
- `.reveal` / `.in` scroll-reveal utilities

Tailwind classes are **not used** in `HomeCosmic.tsx` — the cosmic design uses raw CSS custom properties and doesn't fit the Tailwind token system.

---

## Component structure inside HomeCosmic.tsx

```
HomeCosmic (default export)
│
├── State: phase, gateOpen, gateReason, sessionSparks, sessionId,
│          recentJourney, streakDays, selectedField, showResult
│
├── Effects:
│   ├── add class 'cosmic-mode' to <html> on mount, remove on unmount
│   │   (CSS: html.cosmic-mode { cursor: none } — scoped, not global)
│   ├── getSessionStatus on mount (restore spark count)
│   └── getPassport + getUserProfile when user signs in (continue card + streak)
│
├── Handlers:
│   ├── handleFieldSubmit(field) — shows static gap result
│   └── handleSparkCTA(field) — calls askSpark, manages phase state
│
├── <PageMeta /> — existing component, same props as old Home
├── <Navigation /> — existing component, unchanged
├── <CustomCursor /> — dot + lagging ring, rAF animation
├── <StarField />    — canvas, rAF star loop, resize listener
│
├── Continue card — same markup as old Home (shown when recentJourney + phase=hero)
│
├── <section id="s1"> — Hero (no input)
├── <section id="s2"> — Timeline
│   └── <TimelineEvent /> × 6 — IntersectionObserver per event
│
├── <section id="s3"> — Personal Gap
│   ├── Field <input>
│   ├── Tag cloud (12 tags)
│   └── <PersonalGapResult /> — animated bar + insight + CTAs (phase-aware)
│
├── <section id="s4"> — Promise / Pricing
│   └── 3× <CosmicPlanCard /> — visual only, each links to /pricing
│
├── <section id="s5"> — Potential Indicator
│   └── <PotentialIndicatorCanvas /> — canvas, rAF constellation
│
├── <footer>
│
└── <GateModal /> — existing component, same props as old Home
```

---

## Google Fonts addition to index.html

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link
  href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Space+Mono:wght@0,400;0,700&family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&display=swap"
  rel="stylesheet"
>
```

These fonts only load when `HomeCosmic` is visited — Vite's lazy loading means the CSS import and font requests only fire when the route renders.

---

## Implementation order

1. Add Google Fonts to `index.html`
2. Create `src/styles/cosmic.css`
3. Create `src/pages/HomeCosmic.tsx` (bottom-up: canvas components first, then sections, then main export)
4. Change line 13 in `src/App.tsx` to point to `HomeCosmic`
5. Test: spark flow, auth gate, continue card, mobile layout, revert toggle
