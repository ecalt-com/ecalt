# Phase 1 — Core Learner Flow (highest priority)

The Journey → Step → Quiz path is where users spend their time; mobile breakage here costs retention directly.

## 1.1 ConstellationMap fixed width — `components/constellation/ConstellationMap.tsx:52-56`

**Problem:** Non-mini mode renders the SVG with a hard `width=400, height=400` attribute. On screens narrower than ~432px (400 + page padding) it overflows and forces horizontal scroll wherever it's embedded (Passport / MindSignature).

**Fix:**
- Keep the `viewBox="0 0 400 400"` (it makes the SVG scalable) but drop the fixed `width`/`height` attrs in non-mini mode.
- Set `width: 100%; max-width: 400px; height: auto; aspect-ratio: 1/1` via className on the SVG instead.
- Mini mode (180px) is fine as-is.

**Verify:** Passport and MindSignature at 360px — map fills width, no body scrollbar.

## 1.2 QuizCard touch targets and hover-only states — `components/QuizCard.tsx`

**Problem:**
- Action buttons use `text-xs px-2.5 py-1.5` (~30px tall) — well under the 44px touch guideline (lines ~154, 161, 290).
- 9 `hover:` styles with no `active:` equivalents — on touch there is no press feedback at all.
- Hint row (line ~272-290) pairs `flex-1` input with a `shrink-0` button; at 360px confirm the button text doesn't wrap awkwardly.

**Fix:**
- Bump primary actions to `py-2.5` minimum and add `min-h-[44px]` on tappable rows (or use a shared `.btn-touch` utility — see Phase 3).
- Add `active:` variants mirroring each `hover:` (e.g. `active:bg-amber-700`).
- Keep visual size compact by padding the hit area, not the visible chrome, where design requires small buttons: wrap in a larger padded button with inner styling.

## 1.3 StepNode — `components/StepNode.tsx`

**Problem:**
- `flex gap-4` + 40px node circle leaves ~280px of content width at 360px; combined with `text-[11px]` metadata (line 139), legibility is marginal.
- 3 `hover:` styles, no `active:`.
- Header button (line 121) is fine size-wise (`p-4`), keep.

**Fix:**
- Reduce gutter on mobile: `gap-3 sm:gap-4`.
- Raise `text-[11px]` metadata to `text-xs` (12px) — see Phase 3 type-scale rule.
- Add `active:` press states.

## 1.4 Passport stat tiles — `pages/Passport.tsx:76`

**Problem:** `grid grid-cols-4 gap-3 sm:gap-4` gives ~78px tiles at 360px — numbers + labels get cramped/truncated.

**Fix:** `grid-cols-2 sm:grid-cols-4`. Verify tile content alignment when stacked 2×2.

## 1.5 OnboardingModal interest picker — `components/OnboardingModal.tsx:128`

**Problem:** `grid grid-cols-3 gap-2` inside a `max-w-md` modal → ~104px cells at 360px. Likely acceptable for short labels, but verify longest interest label doesn't wrap to 3 lines.

**Fix (if needed):** `grid-cols-2 min-[400px]:grid-cols-3`, or shrink label font on mobile.

## 1.6 Journey page sanity pass — `pages/Journey.tsx`

Container is already `max-w-3xl mx-auto px-4` (line 262) — good. Verify only:
- Completion modal (line 38) scrolls correctly when keyboard/suggestion list makes it taller than viewport (`overflow-y-auto` is present — confirm on a 667px-tall viewport).
- Chip row (lines 298-305) wraps via `flex-wrap` — confirmed present, no action.

## Exit criteria

- [ ] No horizontal scroll at 360px on /journey/:id, /journeys, /passport, /learn
- [ ] All quiz interactions reachable and tappable with a thumb (44px effective target)
- [ ] ConstellationMap scales to container width
- [ ] Press feedback visible on touch for every interactive element in the flow
