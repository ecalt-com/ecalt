# Phase 2 — Public / Marketing Pages

First-touch surfaces: Home, Pricing, Explore, Welcome, Verify, ComingSoon, ConsentConfirm, Privacy, Profile.

## 2.1 Home — `pages/Home.tsx`

Already the most responsive page (17 breakpoint prefixes). Sanity pass only:
- Hero glow blob (`w-[600px] h-[400px]`, line 531) sits inside an `overflow-hidden` section — confirmed safe, no action.
- Walk the full page at 360px and check section paddings, CTA button sizes, and any side-by-side rows that should stack.

## 2.2 HomeCosmic — `pages/HomeCosmic.tsx` — DECISION NEEDED

88 styled elements, **zero** responsive prefixes — but it is **not referenced in `App.tsx` routes**. It appears to be dead/experimental code.

- If dead → delete it (or move to an `experiments/` folder) rather than retrofit responsiveness.
- If planned for revival → it needs its own full responsive pass; budget separately.

**Confirm with owner before touching.**

## 2.3 ComingSoon — `pages/ComingSoon.tsx`

Catches `/sign-in`, `/get-started`, and the 404 wildcard, so it does get mobile traffic. Zero responsive prefixes.
- Verify the `w-[500px] h-[500px]` blob (line 15) is inside an `overflow-hidden`/`pointer-events-none` container; add `overflow-hidden` to the page wrapper if missing.
- Check heading scale at 360px (`text-4xl`+ headings often need `text-3xl sm:text-4xl`).

## 2.4 Verify — `pages/Verify.tsx`

Public share/verification page — likely opened from a phone via shared link, so it matters more than its traffic suggests.
- `min-h-[260px]` (line 109) is fine (min-height doesn't overflow).
- Only 1 responsive prefix on the whole page: audit card paddings (`p-8` → `p-5 sm:p-8`) and any wide flex rows.

## 2.5 Pricing — `pages/Pricing.tsx`

Grids already responsive. Verify:
- Plan cards stack at mobile widths and CTA buttons are full-width on mobile.
- Price + period line doesn't wrap mid-number at 360px.

## 2.6 Explore / Journeys — `pages/Explore.tsx`, `pages/Journeys.tsx`

Both have responsive grids already. Verify card internals (`JourneyCard.tsx`, `MissionCard.tsx`) at 360px:
- Long journey titles truncate (`line-clamp`/`truncate`) instead of stretching cards.
- Tag/chip rows wrap.

## 2.7 Welcome / ConsentConfirm / Privacy / Profile

- `Welcome.tsx`: blob safe (inside `pointer-events-none` wrapper). Check the CTA stack and any 2-col rows.
- `ConsentConfirm.tsx`: zero prefixes — form page reached from email links on phones. Check form width, paddings, button sizes.
- `Privacy.tsx`: long-form text — confirm `px-4` container and that any tables/code blocks wrap.
- `Profile.tsx`: 105 styled elements, only 2 prefixes. Walk every section (subscription card, settings rows, danger zone) at 360px; settings rows with label + control side-by-side likely need `flex-col sm:flex-row`.

## Exit criteria

- [ ] No horizontal scroll at 360px on /, /pricing, /explore, /welcome, /verify/:hash, /consent/confirm, /profile and the ComingSoon routes
- [ ] HomeCosmic decision recorded (delete vs. retrofit)
- [ ] All forms usable one-handed on a 375px device
