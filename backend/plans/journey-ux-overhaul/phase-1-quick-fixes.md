# Phase 1 — Quick UI Fixes (frontend only)

> **Status: IMPLEMENTED 2026-06-11** (uncommitted). Also fixed the identical dead
> "Begin Journey" button on `Explore.tsx` (same bug, same mechanism). StepNode
> expansion is controlled-with-fallback (`expanded`/`onExpandToggle` optional props),
> so both pages drive it while standalone usage stays self-managed. Both Home.tsx
> tagline variants removed. `tsc` + `vite build` pass.

Two small, independent fixes. No backend changes, no migrations. ~1–2 hours.

## 1.1 Fix the dead "Start Journey / Continue" button

**Bug:** `frontend/src/pages/Journey.tsx:217` renders
`<button className="btn-primary text-center">` with **no onClick handler**.

**Intended behaviour:** clicking it should take the user into the journey — i.e.
expand the first incomplete step and scroll to it. ("Continue" = same action, the
first incomplete step is simply further down.)

**Implementation:**

1. Lift expansion state out of `StepNode` into the `Journey` page:
   - `Journey.tsx`: add `const [expandedStepId, setExpandedStepId] = useState<string | null>(null)`.
   - `StepNode.tsx`: replace internal `const [expanded, setExpanded] = useState(false)`
     with props `expanded: boolean` and `onExpandToggle: (id: string) => void`.
     `handleExpand` keeps its content-fetch logic but reads/sets expansion via props.
   - This plumbing is also a prerequisite for Phase 2 (locking) and Phase 3
     (quiz gating), so do it here once.
2. Add a ref map (or `id={`step-${step.id}`}` anchors) on each step wrapper.
3. Start button handler:
   ```tsx
   const startJourney = () => {
     const target = steps.find(s => !s.completed) ?? steps[0]
     if (!target) return
     setExpandedStepId(target.id)
     document.getElementById(`step-${target.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
   }
   ```
4. Do **not** touch `src/app/journey/[id]/page.tsx` (dead Next.js tree) — its
   identical dead button at line 109 is out of scope; consider deleting `src/app/`
   in a separate cleanup.

**Acceptance:**
- On a fresh journey, "Start Journey" expands step 1, scrolls to it, and lesson
  content starts loading.
- On a partially completed journey, "Continue" expands the first incomplete step.

## 1.2 Remove the hero tagline

**Location:** `frontend/src/pages/Home.tsx`
- Line 556: `Short Haiku responses only · No sign-up needed` (first-visit state) — **remove** (explicit request).
- Line 547: `Short Haiku responses only · Create account to save path` (after-spark
  state) — same claim, same `<p>` slot. **Recommend removing both** for consistency;
  confirm at review.

**Implementation:** delete the `<p className="text-xs text-slate-400">…</p>` element(s).
The surrounding `inline-flex flex-col` badges render fine without them (gap-2 collapses).

**Acceptance:** hero shows the spark badge/counter with no sub-caption, in both the
first-visit and post-spark states, light + dark mode.
