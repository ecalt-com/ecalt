# Mobile Responsiveness — Phased Plan

Audit date: 2026-06-11 · Scope: `frontend/src` (all routed pages + shared components)

## Audit summary

The foundation is solid — this is a polish job, not a rebuild:

**Already mobile-friendly:**
- `index.html` has a correct viewport meta tag.
- `Navigation.tsx` has a working hamburger menu (`md:hidden` toggle + fixed-overlay dropdown).
- All modals (`OnboardingModal`, `GateModal`, Journey completion modal) use the safe `fixed inset-0 p-4` + `max-w-md w-full` pattern.
- `CuriosityInput` uses `text-base` (16px) — no iOS auto-zoom on focus.
- Nearly all multi-column grids already carry `sm:`/`md:` breakpoint variants.
- Decorative glow blobs with fixed px sizes (`Welcome`, `Passport`, `Home`, `ComingSoon`) are `absolute` + `pointer-events-none` inside `overflow-hidden` parents — harmless.

**Real gaps found:**

| Issue | Where | Phase |
|---|---|---|
| Fixed 400px SVG width overflows <432px screens | `components/constellation/ConstellationMap.tsx:52-56` | 1 |
| Sub-44px touch targets, hover-only feedback | `QuizCard.tsx`, `StepNode.tsx`, `JourneyCard.tsx` | 1 |
| `grid-cols-4` stat tiles cramped at 360px | `pages/Passport.tsx:76` | 1 |
| `grid-cols-3` interest picker untested at narrow widths | `components/OnboardingModal.tsx:128` | 1 |
| Zero responsive prefixes on several public pages | `HomeCosmic` (unrouted — confirm dead), `ComingSoon`, `ConsentConfirm` | 2 |
| Hover-only states across the app (no `active:` for touch) | global | 3 |
| No safe-area insets for notched phones (fixed nav) | `Navigation.tsx`, global CSS | 3 |
| Tables without `overflow-x-auto` wrapper | `admin/tabs/OverviewTab.tsx:57`, `admin/tabs/AIProvidersTab.tsx:47,208` | 4 |
| Non-responsive `grid-cols-2` forms | `admin/tabs/CouponsTab.tsx:143,390` | 4 |
| `min-h-[600px]` / `min-w-[120-200px]` editor panels | `PromptsTab`, `NotificationTemplatesTab`, `CouponsTab`, `AIProvidersTab` | 4 |

## Phases

| Phase | File | Focus | Effort |
|---|---|---|---|
| 1 | [phase-1-core-learner-flow.md](phase-1-core-learner-flow.md) | Journey / Quiz / Passport — the money path | ~1 day |
| 2 | [phase-2-public-pages.md](phase-2-public-pages.md) | Home, Pricing, Explore, Welcome, Verify, misc pages | ~0.5 day |
| 3 | [phase-3-touch-and-polish.md](phase-3-touch-and-polish.md) | Touch targets, active states, safe areas, type scale | ~1 day |
| 4 | [phase-4-admin-dashboard.md](phase-4-admin-dashboard.md) | Admin tables/grids — tablet-first, lowest priority | ~1 day |

## Testing baseline (applies to every phase)

Verify at these widths in browser devtools before marking a phase done:
- **360px** (small Android), **375px** (iPhone SE), **390px** (iPhone 14/15), **768px** (tablet)
- Check both light and dark themes — the app is theme-driven via CSS vars.
- No horizontal scrollbar on `<body>` at any width is the hard pass/fail gate.
