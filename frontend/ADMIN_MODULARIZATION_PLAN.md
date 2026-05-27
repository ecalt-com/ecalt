# Admin.tsx Modularization Plan

## Current State

`src/pages/Admin.tsx` is **3,020 lines** — a single monolithic component containing:

| Category | Count | Problem |
|---|---|---|
| TypeScript interfaces | ~26 at module level + 3 **inside the function** | Types scattered; `CouponRow`, `RedemptionRow`, `CouponStats` defined inside the component |
| Global constants | 5 (`PLAN_ICONS`, `PLAN_FEATURES`, `INTERACTION_LABELS`, `FEATURE_COLORS`, `OTHER_COLOR`) | Mixed with types and component code |
| Formatter utilities | 5 (`fmtCents`, `fmtPct`, `calcPct`, `fmtTokens`, `fmtMonth`) | Inline, not reusable |
| `useState` hooks | ~30 | All tabs share one state namespace |
| `useEffect` hooks | 2 | 12-endpoint `Promise.all` directly in component body |
| Handler functions | ~15 | All tabs' mutations in one place |
| Tab panels (JSX) | 9 (`overview`, `plans`, `ai`, `users`, `coupons`, `revenue`, `retention`, `funnel`, `content`) | All inline; largest tabs are 400–600 lines each |
| Inlined sub-components | 1 (`FeatureTrendChart` at module level) | Not in its own file |
| Duplicated UI patterns | `UserDetailPanel` copy-pasted in `users` tab and `ai` tab's "at risk users" section | Divergence risk |
| `inputCls`/`selectCls` strings | 2 (defined inside the function at line 941) | Should be constants |

---

## Target Architecture

```
src/
├── pages/
│   └── Admin.tsx                        # ~100 lines: shell layout + tab router only
└── pages/admin/
    ├── types.ts                         # ALL shared TS interfaces (exported)
    ├── constants.ts                     # PLAN_ICONS, PLAN_FEATURES, INTERACTION_LABELS,
    │                                    # FEATURE_COLORS, TABS, inputCls, selectCls, etc.
    ├── utils.ts                         # fmtCents, fmtPct, calcPct, fmtTokens, fmtMonth
    ├── hooks/
    │   ├── useAdminData.ts              # main 12-endpoint Promise.all data load
    │   └── useCouponStats.ts            # lazy coupon stats (loaded when tab first opens)
    ├── components/
    │   ├── StatCard.tsx                 # reusable label/value card (used in 5 tabs)
    │   ├── BudgetBar.tsx               # spent/budget progress bar with color thresholds
    │   ├── SimpleBarChart.tsx           # generic vertical bar chart (daily msgs, signups, etc.)
    │   ├── UserDetailPanel.tsx          # expandable user drawer (deduplicates Users + AI tabs)
    │   └── FeatureTrendChart.tsx        # moved from Admin.tsx module scope
    └── tabs/
        ├── OverviewTab.tsx
        ├── PlansTab.tsx
        ├── AIProvidersTab.tsx
        ├── UsersTab.tsx
        ├── CouponsTab.tsx              # most complex — full CRUD + bulk generate + redemptions
        ├── RevenueTab.tsx
        ├── RetentionTab.tsx
        ├── FunnelTab.tsx
        └── ContentTab.tsx
```

---

## Phase 1 — Extract Types, Constants & Utilities (Zero Risk)

**Goal:** Zero behaviour change. Pure file splits. Admin.tsx re-imports everything.

### 1.1 Create `src/pages/admin/types.ts`

Move every interface out of `Admin.tsx`:

- All 26 module-level interfaces (`PlanRow`, `NewPlanForm`, `Stats`, `UserRow`, `UserDetail`, `RevenueData`, `AIConfig`, `ModelOption`, `UsageByModel`, `DailyUsage`, `PlanMargin`, `AtRiskUser`, `ByInteractionRow`, `CacheTrendPoint`, `CostAnalysis`, `TopJourney`, `ContentData`, `StepDropoff`, `FunnelData`, `FeatureUsageSummary`, `FeatureTrendPoint`, `FeatureUsageData`, `RetentionData`)
- The 3 interfaces currently **inside the function** (lines 478–492: `CouponRow`, `RedemptionRow`, `CouponStats`) — move to module scope in `types.ts`

All are `export interface`.

### 1.2 Create `src/pages/admin/constants.ts`

Move from `Admin.tsx`:

```ts
export const PLAN_ICONS: Record<string, React.ElementType> = { ... }
export const PLAN_FEATURES: Record<string, string[]> = { ... }
export const INTERACTION_LABELS: Record<string, string> = { ... }
export const FEATURE_COLORS = [...]
export const OTHER_COLOR = 'bg-slate-400'
export const TABS = [...] as const          // currently defined inside Admin() at line 929
export const inputCls = '...'              // currently inside Admin() at line 941
export const selectCls = '...'             // currently inside Admin() at line 942
```

### 1.3 Create `src/pages/admin/utils.ts`

```ts
export const fmtCents = (c: number) => { ... }
export const fmtPct   = (spent: number, budget: number) => { ... }
export const calcPct  = (spent: number, budget: number) => { ... }
export const fmtTokens = (n: number) => { ... }
export const fmtMonth  = (iso: string) => { ... }
```

### 1.4 Create `src/pages/admin/components/FeatureTrendChart.tsx`

Move the `FeatureTrendChart` function (lines 382–446) to its own file. It already has the right shape — just needs `FeatureTrendPoint`, `INTERACTION_LABELS`, `FEATURE_COLORS`, `OTHER_COLOR`, `fmtCents`, and `fmtMonth` imported.

### 1.5 Update Admin.tsx imports

Replace all the moved code with imports. File should now be ~2,500 lines (types/constants/utils/FeatureTrendChart extracted, everything else still inline).

**Verification:** `npm run build` must pass with zero type errors.

---

## Phase 2 — Extract Custom Hooks (Data-Fetching Separation)

**Goal:** Remove all async/API logic from the component body. No JSX changes yet.

### 2.1 Create `src/pages/admin/hooks/useAdminData.ts`

Extract the main `useEffect` (lines 563–609) into a custom hook:

```ts
export function useAdminData(getToken: () => Promise<string | null>, navigate: NavigateFunction) {
  const [plans, setPlans]           = useState<PlanRow[]>([])
  const [stats, setStats]           = useState<Stats | null>(null)
  const [users, setUsers]           = useState<UserRow[]>([])
  const [aiConfigs, setAiConfigs]   = useState<AIConfig[]>([])
  const [availableModels, ...]      = useState<Record<string, ModelOption[]>>({})
  const [usageByModel, ...]         = useState<UsageByModel[]>([])
  const [dailyUsage, ...]           = useState<DailyUsage[]>([])
  const [revenue, ...]              = useState<RevenueData | null>(null)
  const [costAnalysis, ...]         = useState<CostAnalysis | null>(null)
  const [retentionData, ...]        = useState<RetentionData | null>(null)
  const [featureUsage, ...]         = useState<FeatureUsageData | null>(null)
  const [funnelData, ...]           = useState<FunnelData | null>(null)
  const [contentData, ...]          = useState<ContentData | null>(null)
  // ... useEffect with Promise.all ...
  return { plans, setPlans, stats, users, setUsers, aiConfigs, setAiConfigs,
           availableModels, usageByModel, setUsageByModel, dailyUsage,
           revenue, costAnalysis, retentionData, featureUsage, funnelData, contentData }
}
```

The hook takes `getToken` and `navigate` (to handle the 403 redirect), and returns all state + setters needed by handlers.

### 2.2 Create `src/pages/admin/hooks/useCouponStats.ts`

Extract the second `useEffect` (lines 611–620) into a hook:

```ts
export function useCouponStats(tab: string, getToken: () => Promise<string | null>) {
  const [couponStats, setCouponStats] = useState<CouponStats | null>(null)
  useEffect(() => { /* lazy load when tab === 'coupons' */ }, [tab, couponStats, getToken])
  return { couponStats }
}
```

### 2.3 Update Admin.tsx

Replace the two `useEffect`s and their related `useState`s with:

```ts
const data = useAdminData(getToken, navigate)
const { couponStats } = useCouponStats(tab, getToken)
```

Admin.tsx should now be ~2,100 lines. Handlers still live in Admin.tsx; all JSX still inline.

**Verification:** `npm run build` + check admin panel works end-to-end in browser.

---

## Phase 3 — Extract Shared UI Primitives (DRY Patterns)

**Goal:** Remove duplicated UI patterns. These components take only data props — no API calls.

### 3.1 Create `src/pages/admin/components/StatCard.tsx`

Used identically in **5 tabs** (Overview, Revenue, Retention, Content, Coupons):

```tsx
interface StatCardProps { label: string; value: string | number }
export function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="glass-card rounded-xl p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
    </div>
  )
}
```

### 3.2 Create `src/pages/admin/components/BudgetBar.tsx`

The spent/budget progress bar with rose/amber/emerald color thresholds is copy-pasted in:
- Users tab (line ~1852) 
- AI tab "at risk users" section (line ~1446)
- UserDetailPanel (to be created)

```tsx
interface BudgetBarProps { spent: number; budget: number; showValues?: boolean }
export function BudgetBar({ spent, budget, showValues }: BudgetBarProps) { ... }
```

### 3.3 Create `src/pages/admin/components/SimpleBarChart.tsx`

The vertical bar chart pattern (a row of `flex-1` divs with proportional height) appears for:
- Daily messages (14 bars)
- Weekly signups (12 bars)
- Cache hit rate (6 bars)
- Knowledge graph growth (14 bars)

```tsx
interface SimpleBarChartProps {
  data: { label: string; value: number; tooltip?: string }[]
  height?: string
  barColor?: string
  showEndLabels?: boolean
}
export function SimpleBarChart({ data, ... }: SimpleBarChartProps) { ... }
```

### 3.4 Create `src/pages/admin/components/UserDetailPanel.tsx`

The expandable user detail panel (profile meta, current month, token chips, feature breakdown table, 12-month history, lifetime stats, coupon redemptions) is **100% identical** in:
- Users tab (lines 1823–2001)
- AI tab "at risk users" section (lines 1426–1491)

Extract it into one component:

```tsx
interface UserDetailPanelProps {
  detail: UserDetail
  isLoading: boolean
}
export function UserDetailPanel({ detail, isLoading }: UserDetailPanelProps) { ... }
```

### 3.5 Update Admin.tsx

Replace all instances of these patterns with the new components. Admin.tsx should now be ~1,600 lines.

**Verification:** Visual comparison of admin panel in browser — no layout regressions.

---

## Phase 4 — Extract Tab Components (The Big Split)

**Goal:** Each tab becomes its own file. Extract in order from simplest (read-only) to most complex (CRUD).

Each tab component receives its required data and handlers as props. Handlers remain in Admin.tsx for now (moved to tabs in Phase 5).

### Props pattern for read-only tabs:

```tsx
// RevenueTab.tsx
interface RevenueTabProps { revenue: RevenueData | null }
export function RevenueTab({ revenue }: RevenueTabProps) { ... }
```

### Props pattern for tabs with mutations:

```tsx
// PlansTab.tsx
interface PlansTabProps {
  plans: PlanRow[]
  edits: Record<string, Partial<PlanRow>>
  saving: string | null
  provisioning: Record<string, string | null>
  newPlanForm: NewPlanForm
  creatingPlan: boolean
  onSetEdit: (planId: string, field: string, value: ...) => void
  onSavePlan: (planId: string) => void
  onProvision: (planId: string, gateway: 'stripe' | 'razorpay' | 'both') => void
  onSetNewPlanForm: React.Dispatch<React.SetStateAction<NewPlanForm>>
  onCreatePlan: () => void
}
```

### Extraction order:

| Step | File | Complexity | Lines (approx) |
|---|---|---|---|
| 4.1 | `RevenueTab.tsx` | Read-only | ~135 |
| 4.2 | `RetentionTab.tsx` | Read-only | ~140 |
| 4.3 | `FunnelTab.tsx` | Read-only | ~150 |
| 4.4 | `OverviewTab.tsx` | Read-only, uses `FeatureTrendChart` | ~140 |
| 4.5 | `ContentTab.tsx` | Has `expandedJourneyId` + async step dropoff | ~160 |
| 4.6 | `AIProvidersTab.tsx` | Mutations + `UserDetailPanel` + cost charts | ~390 |
| 4.7 | `PlansTab.tsx` | Mutations + create + gateway provision | ~200 |
| 4.8 | `UsersTab.tsx` | Mutations + expand + `UserDetailPanel` | ~270 |
| 4.9 | `CouponsTab.tsx` | Full CRUD + bulk generate + redemptions drawer | ~410 |

### Notes per tab:

**ContentTab (4.5):** `expandedJourneyId`, `journeyDropoff`, `loadingDropoff`, and `handleExpandJourney` are content-tab-only state. Pass as props for now; colocate in Phase 5.

**AIProvidersTab (4.6):** This tab renders both "AI cost analysis" and "model routing config" — two conceptually different things. They share the `costAnalysis` and `aiConfigs` data. Keeping them together for now is fine.

**CouponsTab (4.9):** `createFormRef` for smooth-scroll must live inside `CouponsTab` since it references a DOM node inside that component. Pass it down or move the ref into `CouponsTab` when extracting.

### After Phase 4, Admin.tsx looks like:

```tsx
export default function Admin() {
  const { getToken, user } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<TabId>('overview')
  
  const data = useAdminData(getToken, navigate, user)
  const { couponStats } = useCouponStats(tab, getToken, user)
  
  // ~15 handler functions (handleSavePlan, handleSaveAI, handleToggleAdmin, etc.)
  // ~15 coupon handler functions
  
  return (
    <>
      <PageMeta title="Admin" />
      <div ...>
        {/* back button, header, tab bar */}
        {tab === 'overview'   && <OverviewTab ... />}
        {tab === 'plans'      && <PlansTab ... />}
        {tab === 'ai'         && <AIProvidersTab ... />}
        {tab === 'users'      && <UsersTab ... />}
        {tab === 'coupons'    && <CouponsTab ... />}
        {tab === 'revenue'    && <RevenueTab ... />}
        {tab === 'retention'  && <RetentionTab ... />}
        {tab === 'funnel'     && <FunnelTab ... />}
        {tab === 'content'    && <ContentTab ... />}
      </div>
    </>
  )
}
```

Admin.tsx target: **~250 lines** after Phase 4.

**Verification after each sub-step:** Build must pass; test each tab visually.

---

## Phase 5 — Colocate Tab-Level State & Handlers (Optional / Advanced)

**Goal:** Each tab owns its own state and mutations. Admin.tsx becomes a pure shell (~80 lines). This is the "ideal" end state but requires the most refactoring risk.

### Changes per tab:

- Each tab component receives only `getToken` (from `useAuth`) + the read-only shared data (e.g., `plans`, `users`) that other tabs also need.
- All tab-specific state (e.g., `edits`, `saving`, `couponForm`) moves *into* the tab component.
- All tab-specific handlers (e.g., `handleSavePlan`, `handleCreateCoupon`) move into the tab component.
- The `useAdminData` hook still handles the initial parallel data load and provides the shared read data through context or props.

### Option A: Props drilling (simpler)

Admin.tsx calls `useAdminData` and passes read-only data as props to each tab. Each tab manages its own mutations locally.

### Option B: Admin context (cleaner for deeply nested)

Create a `AdminContext` that exposes the read data + refresh callbacks. Each tab calls `useAdminContext()` and does its own mutations.

```tsx
// AdminContext.tsx
const AdminContext = createContext<AdminContextValue | null>(null)
export function AdminProvider({ children }) {
  const data = useAdminData(...)
  return <AdminContext.Provider value={data}>{children}</AdminContext.Provider>
}
export const useAdminContext = () => useContext(AdminContext)!
```

**Recommendation:** Option A is sufficient for this codebase. Option B is better if the tab tree ever gets more deeply nested sub-components that need the data.

### When to do Phase 5:

- Only if the admin panel is actively developed (new tabs, new features)
- Not required for a clean Phase 4 result
- `CouponsTab` benefits the most — it has the most standalone state (~20 state variables)

---

## Final File Structure After All Phases

```
src/pages/
├── Admin.tsx                             # ~80–100 lines
└── admin/
    ├── types.ts                          # ~290 lines
    ├── constants.ts                      # ~60 lines
    ├── utils.ts                          # ~20 lines
    ├── hooks/
    │   ├── useAdminData.ts               # ~80 lines
    │   └── useCouponStats.ts             # ~25 lines
    ├── components/
    │   ├── StatCard.tsx                  # ~15 lines
    │   ├── BudgetBar.tsx                 # ~25 lines
    │   ├── SimpleBarChart.tsx            # ~35 lines
    │   ├── UserDetailPanel.tsx           # ~180 lines
    │   └── FeatureTrendChart.tsx         # ~65 lines
    └── tabs/
        ├── OverviewTab.tsx               # ~140 lines
        ├── PlansTab.tsx                  # ~200 lines
        ├── AIProvidersTab.tsx            # ~390 lines
        ├── UsersTab.tsx                  # ~270 lines
        ├── CouponsTab.tsx                # ~410 lines
        ├── RevenueTab.tsx                # ~135 lines
        ├── RetentionTab.tsx              # ~140 lines
        ├── FunnelTab.tsx                 # ~150 lines
        └── ContentTab.tsx               # ~160 lines
```

**Total:** ~3,020 lines distributed across 19 files. Largest file: `CouponsTab.tsx` at ~410 lines.

---

## Key Invariants to Preserve

1. **Build passes after every commit** — never break the build mid-phase.
2. **No behaviour changes** — this is a pure structural refactor; no logic changes until Phase 5.
3. **Prop types are explicit** — every tab component has a typed `Props` interface; no `any`.
4. **Imports are clean** — each file imports only what it uses; no barrel `index.ts` re-exports unless needed.
5. **`createFormRef`** belongs inside `CouponsTab` (DOM ref for scroll-to-create). Extract it when splitting.
6. **`expandedUid` / `userDetails` / `loadingDetail`** are shared between the `users` tab and the `ai` tab's "at risk users" section. In Phase 4, pass them as props to both. Colocate in Phase 5 only after deciding which tab "owns" user expansion (recommendation: `useExpandedUser` mini-hook consumed by both tabs).

---

## Implementation Order Summary

| Phase | Risk | Files Changed | Lines Removed from Admin.tsx |
|---|---|---|---|
| 1 — types / constants / utils | Very Low | +4 new files | ~380 lines |
| 2 — hooks | Low | +2 new files | ~200 lines |
| 3 — shared UI primitives | Low | +5 new files | ~300 lines |
| 4 — tab extraction | Medium | +9 new files | ~1,700 lines |
| 5 — colocate state (optional) | Medium-High | edit 9 tab files + Admin.tsx | ~130 lines |

After Phase 4: Admin.tsx is **~250 lines**.  
After Phase 5: Admin.tsx is **~80 lines**.
