# Phase 4 — Admin Dashboard (lowest priority)

The admin section is desktop-first by nature. Recommendation: target **tablet (768px) and up** as fully supported, and make phone widths *functional* (scrollable, nothing clipped) rather than optimized. Decide this explicitly before starting.

## 4.1 Tables without horizontal-scroll wrappers

`FunnelTab` and `UserDetailPanel` already wrap tables in `overflow-x-auto` — copy that pattern to:

- `pages/admin/tabs/OverviewTab.tsx:57` — recent-users table
- `pages/admin/tabs/AIProvidersTab.tsx:47` — providers table
- `pages/admin/tabs/AIProvidersTab.tsx:208` — second table (model/pricing list)

Pattern: `<div className="overflow-x-auto"><table className="w-full min-w-[560px] text-xs">…</table></div>` — the `min-w` keeps columns readable while the wrapper scrolls.

## 4.2 Non-responsive form grids

- `pages/admin/tabs/CouponsTab.tsx:143` — `grid grid-cols-2 gap-3` (create-coupon form) → `grid-cols-1 sm:grid-cols-2`
- `pages/admin/tabs/CouponsTab.tsx:390` — `grid grid-cols-2 gap-2` (detail panel) → same fix

## 4.3 Fixed-dimension editor panels

- `pages/admin/tabs/PromptsTab.tsx:126` and `pages/admin/tabs/NotificationTemplatesTab.tsx:93` — `min-h-[600px]` two-pane editors. On phones the side-by-side panes don't fit.
  - Fix: stack panes vertically below `md:` (`flex-col md:flex-row`), and relax to `min-h-0 md:min-h-[600px]`.
- Filter/select controls with `min-w-[120px]`–`min-w-[200px]` (`CouponsTab.tsx:239,319`, `AIProvidersTab.tsx:319`): fine individually, but confirm their parent rows have `flex-wrap` so they wrap instead of overflowing.

## 4.4 Admin tab bar — `pages/Admin.tsx`

11 tabs in the tab strip. At phone widths verify the strip scrolls horizontally (`overflow-x-auto` + `flex-nowrap` + `shrink-0` children) rather than wrapping into a tall block or clipping.

## 4.5 Charts

`SimpleBarChart`, `FeatureTrendChart`, `BudgetBar` — confirm each renders from container width (not a fixed pixel width) at 360px. If any uses fixed SVG width, apply the same viewBox + `width:100%` fix as ConstellationMap (Phase 1.1).

## Exit criteria

- [ ] Support tier decision recorded (recommended: optimized ≥768px, functional below)
- [ ] Every admin table scrolls horizontally instead of overflowing the page
- [ ] Editor tabs (Prompts, Notification Templates) usable on a tablet in portrait
- [ ] No clipped controls at 360px — everything reachable via scroll
