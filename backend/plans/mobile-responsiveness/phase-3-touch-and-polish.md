# Phase 3 — Touch & Polish (cross-cutting)

Global fixes that apply across every page. Do these once, centrally, instead of per-component.

## 3.1 Shared touch-target utility

**Problem:** Compact buttons (`text-xs px-2.5 py-1.5` ≈ 30px tall) appear throughout QuizCard, admin tabs, modal footers — under the 44px iOS / 48dp Android guideline.

**Fix:** Add a utility in `src/index.css`:

```css
@layer components {
  .btn-touch {
    @apply min-h-[44px] inline-flex items-center justify-center;
  }
}
```

- Apply to every interactive element a thumb must hit. Where the design needs visually small buttons, keep the visible chrome small but extend the hit area (transparent padding or `before:` pseudo-element inset).
- Audit checklist of known offenders: `QuizCard.tsx` (hint/eval/retry buttons), `OnboardingModal.tsx:157,220` (skip links, `py-1`), `GateModal.tsx:108`, chip-style buttons in `Journey.tsx`.

## 3.2 `active:` press states for touch

**Problem:** The app uses `hover:` extensively (QuizCard ×9, StepNode ×3, JourneyCard ×2, plus nav/admin) with no `active:` equivalents. Touch devices get zero press feedback; hover styles can also "stick" after tap on iOS.

**Fix:**
- Rule going forward: every `hover:` on an interactive element gets a matching `active:` (usually the same value or one shade deeper).
- Optionally gate hover-only effects behind `@media (hover: hover)` for decorative cases (card lift effects) so they don't stick on touch. Tailwind: enable/use the `hover:` variant as-is but add `active:scale-[0.98]`-style feedback on cards.

## 3.3 Safe-area insets (notched phones)

**Problem:** `Navigation.tsx:43` is `fixed top-0` with `py-4`; on devices with a notch/Dynamic Island in landscape, and for any future bottom bars, content can collide with system UI. No `env(safe-area-inset-*)` usage exists anywhere.

**Fix:**
- Add `viewport-fit=cover` to the viewport meta in `index.html`.
- In `index.css`: pad the fixed nav with `padding-top: env(safe-area-inset-top)` and page bottoms with `env(safe-area-inset-bottom)` (matters for the Journey completion modal and any sticky CTAs).

## 3.4 Type-scale floor

**Problem:** `text-[10px]` and `text-[11px]` appear in QuizCard (line 248), StepNode (line 139), Journey (line 62), KnowledgeUniverse (`nodeSize()` returns `text-[11px]`). Sub-12px text is hard to read on small high-DPI screens.

**Fix:** Establish a floor of `text-xs` (12px) for any text carrying information; reserve smaller sizes only for purely decorative labels. Sweep with: `grep -rn 'text-\[1[01]px\]' src/`.

## 3.5 Overscroll & momentum

- Add `overscroll-behavior-y: none` on modal overlays (`OnboardingModal`, `GateModal`, Journey completion modal) so background doesn't scroll-chain behind them.
- Confirm long internal scrollers (admin panels, modal bodies) have `-webkit-overflow-scrolling: touch` behavior (default in modern iOS, just verify nothing sets `overflow: hidden` on `body` permanently).

## 3.6 Regression guard

- Add a short `MOBILE.md` note (or section in frontend CLAUDE.md) stating the conventions: 44px targets, hover+active pairing, 12px text floor, test widths.
- Optional: a Playwright smoke test that loads `/`, `/journeys`, `/journey/:id` at 360×740 and asserts `document.body.scrollWidth <= window.innerWidth`.

## Exit criteria

- [ ] `.btn-touch` (or equivalent) applied to all interactive elements in user-facing flows
- [ ] Every `hover:` paired with `active:` in user-facing components
- [ ] Safe-area insets on fixed chrome; `viewport-fit=cover` set
- [ ] No informational text below 12px
- [ ] Conventions documented for future PRs
