# Coupon System — UI Extension Plan

> Scope: Admin panel coupon management + user-facing coupon surfaces.  
> Stack: React + TypeScript + Tailwind (existing design system — glass-card, violet tokens).

---

## Current State Audit

### Admin panel (`Admin.tsx` — Coupons tab)

| Feature | Status |
|---|---|
| Create form (all fields) | ✅ Works |
| List all coupons with badges | ✅ Works |
| Toggle active/inactive | ✅ Works |
| Edit a coupon inline | ❌ Missing |
| Delete a coupon | ❌ Missing |
| View who redeemed a coupon | ❌ Missing (endpoint exists, no UI) |
| Copy code to clipboard | ❌ Missing |
| Search / filter by status | ❌ Missing |
| Sort control | ❌ Missing |
| Duplicate/clone a coupon | ❌ Missing |
| Stats dashboard (totals) | ❌ Missing |
| Per-coupon redemption mini-chart | ❌ Missing |
| Bulk-generate codes form | ❌ Missing |
| Revoke a user's redemption | ❌ Missing |

### User-facing (`Pricing.tsx` + `Profile.tsx`)

| Feature | Status |
|---|---|
| Coupon apply input on Pricing page | ✅ Works |
| Apply success message | ✅ Basic (shows description only) |
| Coupon active pill in Profile > Subscription | ✅ Works (aggregate only) |
| Preview benefit before applying | ❌ Missing |
| List active coupons with individual expiry | ❌ Missing |
| Apply coupon from Profile page | ❌ Missing |

---

## Phase 1 — Admin: Core CRUD Completeness

### 1.1 Inline edit per coupon

Replace the static coupon row with an expandable card. Clicking anywhere on the row (other than the toggle) opens an edit form below it — same pattern as the Users tab expand.

**New state:**
```tsx
const [editingCode, setEditingCode] = useState<string | null>(null)
const [editForm, setEditForm] = useState<Partial<CouponRow>>({})
const [savingEdit, setSavingEdit] = useState(false)
```

**Edit fields to show:** `description`, `credit_cents`, `bonus_messages`, `max_redemptions`, `expires_at`, `duration_days`, `plan_override`, `tag`

**Handler:**
```tsx
const handleSaveCoupon = async (code: string) => {
  setSavingEdit(true)
  try {
    const token = await getToken()
    const res = await fetch(`/api/v1/coupons/admin/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(editForm),
    })
    if (res.ok) {
      const updated = await res.json()
      setCoupons(prev => prev.map(c => c.code === code ? updated : c))
      setEditingCode(null)
    }
  } finally {
    setSavingEdit(false)
  }
}
```

**UI pattern** — below each coupon row when expanded:
```
┌─────────────────────────────────────────────────────────┐
│  LAUNCH50  [+50¢ credit]  [30d validity]              ▲ │
│  "Launch promo — 50 cents AI credit"                    │
│  12/500 uses · expires Jul 1                            │
├─────────────────────────────────────────────────────────┤
│  Description  [__________________________]              │
│  AI Credit ¢  [____]  Bonus Messages  [____]            │
│  Max uses     [____]  Credit days     [____]            │
│  Expires at   [____________________]                    │
│                              [Cancel]  [Save changes]   │
└─────────────────────────────────────────────────────────┘
```

---

### 1.2 Delete coupon (with confirmation)

Add a delete button (trash icon) inside the expanded edit view — not on the main row (prevents accidental clicks).

**State:**
```tsx
const [deletingCode, setDeletingCode] = useState<string | null>(null)
const [confirmDeleteCode, setConfirmDeleteCode] = useState<string | null>(null)
```

**Handler:**
```tsx
const handleDeleteCoupon = async (code: string) => {
  setDeletingCode(code)
  try {
    const token = await getToken()
    const res = await fetch(`/api/v1/coupons/admin/${code}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      setCoupons(prev => prev.filter(c => c.code !== code))
      setConfirmDeleteCode(null)
      setEditingCode(null)
    }
  } finally {
    setDeletingCode(null)
  }
}
```

**UI — inside edit expand, danger zone section:**
```
┌─────────────────────────────────────────────────────────┐
│  Danger zone                                            │
│  Deleting removes this coupon. Existing redemptions     │
│  and credits are NOT revoked.                           │
│                                    [🗑 Delete coupon]   │
└─────────────────────────────────────────────────────────┘
```

On click, show an inline confirmation: `"Type the code to confirm"` input — same pattern as the account delete modal in `Profile.tsx`.

---

### 1.3 Redemptions drawer

Add a `"X uses"` clickable link that opens an inline drawer below the coupon card showing who redeemed it. Calls `GET /api/v1/coupons/admin/{code}/redemptions`.

**State:**
```tsx
interface RedemptionRow {
  id: string; uid: string; display_name: string | null; email: string | null
  credit_applied_cents: number; bonus_messages_applied: number
  redeemed_at: string; credit_expires_at: string | null
}
const [redemptions, setRedemptions] = useState<Record<string, RedemptionRow[]>>({})
const [loadingRedemptions, setLoadingRedemptions] = useState<string | null>(null)
const [expandedRedemptionsCode, setExpandedRedemptionsCode] = useState<string | null>(null)
```

**Handler:**
```tsx
const handleLoadRedemptions = async (code: string) => {
  if (expandedRedemptionsCode === code) { setExpandedRedemptionsCode(null); return }
  setExpandedRedemptionsCode(code)
  if (redemptions[code]) return
  setLoadingRedemptions(code)
  try {
    const token = await getToken()
    const res = await fetch(`/api/v1/coupons/admin/${code}/redemptions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setRedemptions(prev => ({ ...prev, [code]: data.redemptions }))
    }
  } finally { setLoadingRedemptions(null) }
}
```

**UI — redemptions table inside the card:**
```
┌─────────────────────────────────────────────────────┐
│  Redemptions (12)                          [Close]  │
│  ─────────────────────────────────────────────────  │
│  Alice Smith       alice@ex.com  +$0.50  May 18     │
│  Bob Jones         bob@ex.com    +$0.50  May 19     │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

Each row: display_name, email, credit/messages applied, redeemed_at, credit_expires_at (if set).  
Add a "Revoke" button per row (calls `DELETE /admin/{code}/redemptions/{uid}`).

---

### 1.4 Copy code to clipboard

On the `<code>` badge for each coupon, add a `onClick` that copies to clipboard and briefly shows a checkmark.

```tsx
const [copiedCode, setCopiedCode] = useState<string | null>(null)

const copyCode = (code: string) => {
  navigator.clipboard.writeText(code)
  setCopiedCode(code)
  setTimeout(() => setCopiedCode(null), 1500)
}
```

```tsx
<code
  onClick={() => copyCode(c.code)}
  className="cursor-pointer select-none ..."
  title="Click to copy"
>
  {copiedCode === c.code ? '✓ Copied' : c.code}
</code>
```

---

## Phase 2 — Admin: List UX

### 2.1 Search + filter bar

Above the coupon list, add a filter row:

```
[🔍 Search codes...]  [Status ▼]  [Tag ▼]  [Sort ▼]
```

**Status filter options:** All · Active · Inactive · Expired · Depleted  
**Sort options:** Newest · Most used · Expiring soon

This is fully client-side filtering against the already-loaded `coupons` array — no additional API calls needed until pagination is required at scale.

```tsx
const [couponSearch, setCouponSearch] = useState('')
const [couponStatusFilter, setCouponStatusFilter] = useState<'all' | 'active' | 'inactive' | 'expired' | 'depleted'>('all')
const [couponSort, setCouponSort] = useState<'newest' | 'most_used' | 'expiring'>('newest')

const filteredCoupons = useMemo(() => {
  let result = [...coupons]

  if (couponSearch) {
    result = result.filter(c =>
      c.code.includes(couponSearch.toUpperCase()) ||
      c.description.toLowerCase().includes(couponSearch.toLowerCase())
    )
  }

  const now = new Date()
  if (couponStatusFilter === 'active')
    result = result.filter(c => c.is_active && (!c.expires_at || new Date(c.expires_at) > now))
  else if (couponStatusFilter === 'inactive')
    result = result.filter(c => !c.is_active)
  else if (couponStatusFilter === 'expired')
    result = result.filter(c => c.expires_at && new Date(c.expires_at) <= now)
  else if (couponStatusFilter === 'depleted')
    result = result.filter(c => c.max_redemptions != null && c.redemption_count >= c.max_redemptions)

  if (couponSort === 'most_used')
    result.sort((a, b) => b.redemption_count - a.redemption_count)
  else if (couponSort === 'expiring')
    result = result.filter(c => c.expires_at).sort((a, b) =>
      new Date(a.expires_at!).getTime() - new Date(b.expires_at!).getTime()
    )

  return result
}, [coupons, couponSearch, couponStatusFilter, couponSort])
```

---

### 2.2 Duplicate / clone button

Add a copy icon button on each coupon row. Clicking it pre-fills the create form with that coupon's values (minus the code and redemption_count) and scrolls to the top of the Coupons tab.

```tsx
const handleCloneCoupon = (c: CouponRow) => {
  setCouponForm({
    code: '',
    description: c.description,
    credit_cents: String(c.credit_cents),
    bonus_messages: String(c.bonus_messages),
    duration_days: c.duration_days ? String(c.duration_days) : '',
    max_redemptions: c.max_redemptions ? String(c.max_redemptions) : '',
    expires_at: '',
  })
  createFormRef.current?.scrollIntoView({ behavior: 'smooth' })
}
```

---

## Phase 3 — Admin: Stats Dashboard

### 3.1 Stats cards at top of Coupons tab

Fetched once on tab load from `GET /api/v1/coupons/admin/stats`.

```tsx
interface CouponStats {
  active_coupons: number
  total_coupons: number
  total_redemptions: number
  total_credit_applied_cents: number
  unique_redeemers: number
}
const [couponStats, setCouponStats] = useState<CouponStats | null>(null)
```

**UI — 4-card grid above the create form:**
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Active        │ │ Total        │ │ Unique        │ │ Credit        │
│ coupons       │ │ redemptions  │ │ redeemers     │ │ distributed   │
│ 4             │ │ 347          │ │ 289           │ │ $173.50       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

Same `glass-card rounded-xl p-4` treatment as the Overview tab stats.

---

### 3.2 Usage progress bar per coupon

Replace the plain `"12/500 uses"` text with a visual progress bar:

```tsx
{c.max_redemptions && (
  <div className="flex items-center gap-2 mt-1">
    <div className="flex-1 h-1 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
      <div
        className={clsx(
          'h-full rounded-full',
          fillPct >= 90 ? 'bg-rose-500' : fillPct >= 60 ? 'bg-amber-400' : 'bg-emerald-500'
        )}
        style={{ width: `${fillPct}%` }}
      />
    </div>
    <span className="text-[10px] tabular-nums text-slate-400 shrink-0">
      {c.redemption_count}/{c.max_redemptions}
    </span>
  </div>
)}
```

Color coding: green < 60%, amber 60–90%, red ≥ 90%.

---

### 3.3 Bulk-generate form

A collapsible section below the standard create form, behind a "Bulk generate unique codes" toggle:

**Fields:** Prefix, Count (1–1000), Description, Credit ¢, Bonus messages, Duration days, Expires at, Tag

On success show: `"Generated 50 codes: CONF26-A3X9, CONF26-B2K1, ..."`  
Include a "Copy all codes" button that copies the full list to clipboard.

```tsx
const [showBulkForm, setShowBulkForm] = useState(false)
const [bulkForm, setBulkForm] = useState({ prefix: '', count: '10', description: '', credit_cents: '', bonus_messages: '0', duration_days: '', expires_at: '', tag: '' })
const [bulkResult, setBulkResult] = useState<string[] | null>(null)

const handleBulkGenerate = async () => {
  const token = await getToken()
  const res = await fetch('/api/v1/coupons/admin/bulk-generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      prefix: bulkForm.prefix.toUpperCase(),
      count: parseInt(bulkForm.count),
      description: bulkForm.description,
      credit_cents: parseFloat(bulkForm.credit_cents || '0'),
      bonus_messages: parseInt(bulkForm.bonus_messages || '0'),
      duration_days: bulkForm.duration_days ? parseInt(bulkForm.duration_days) : null,
      expires_at: bulkForm.expires_at || null,
      tag: bulkForm.tag || null,
    }),
  })
  if (res.ok) {
    const data = await res.json()
    setBulkResult(data.codes)
    // Add the new coupons to the list by re-fetching
    const cRes = await fetch('/api/v1/coupons/admin', { headers: { Authorization: `Bearer ${token}` } })
    if (cRes.ok) setCoupons(await cRes.json().then((d: any) => d.coupons ?? []))
  }
}
```

---

## Phase 4 — User-facing Improvements

### 4.1 Coupon preview before applying (Pricing.tsx)

Currently the `CouponApply` component applies immediately on click. Add a two-step flow:
1. User types code, clicks "Preview" (or presses Enter)
2. A preview chip appears: `"LAUNCH50 — +$0.50 AI credit, 30-day validity"` with an "Apply" confirm button

This requires a new backend endpoint `GET /api/v1/coupons/preview?code=LAUNCH50` (no auth side effect — just validation + metadata). Alternatively, keep client-side and just change the button label to "Apply" and show the success message in a preview area first.

**Simpler approach — no new endpoint needed:**  
Keep the single-click apply. After success, show an expanded result card instead of just a text message:

```tsx
{status === 'success' && appliedResult && (
  <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-left">
    <Ticket size={14} className="text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
    <div>
      <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">{appliedResult.description}</p>
      <p className="text-[11px] text-emerald-600 dark:text-emerald-500 mt-0.5">
        {[
          appliedResult.credit_cents > 0 && `+$${(appliedResult.credit_cents / 100).toFixed(2)} AI credit`,
          appliedResult.bonus_messages > 0 && `+${appliedResult.bonus_messages} messages`,
          appliedResult.credit_expires_at && `valid until ${new Date(appliedResult.credit_expires_at).toLocaleDateString()}`,
        ].filter(Boolean).join(' · ')}
      </p>
    </div>
  </div>
)}
```

**State change:**
```tsx
const [appliedResult, setAppliedResult] = useState<{
  description: string; credit_cents: number; bonus_messages: number; credit_expires_at: string | null
} | null>(null)

// In apply():
setAppliedResult(data)
```

---

### 4.2 Active coupons list in Profile.tsx

The current profile subscription card shows only a single aggregate pill (`"Coupon active — +$0.50 credit · +20 messages"`). Replace it with a list of individual coupons that the user has redeemed and are still active.

**Requires:** User-facing endpoint `GET /api/v1/coupons/me` (new — returns the user's own active redemptions).

**New backend endpoint:**
```python
@router.get("/me")
def user_coupons(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cr.coupon_code, cr.credit_applied_cents, cr.bonus_messages_applied,
                       cr.redeemed_at, cr.credit_expires_at, c.description, c.is_active
                FROM coupon_redemptions cr
                JOIN coupons c ON c.code = cr.coupon_code
                WHERE cr.uid = %s
                ORDER BY cr.redeemed_at DESC
            """, (uid,))
            rows = [dict(r) for r in cur.fetchall()]
    return {"coupons": rows}
```

**UI in Profile.tsx — within the Subscription card, below the plan line:**
```
┌─────────────────────────────────────────────────────┐
│  Promo codes                                        │
│  ┌──────────────────────────────────────────────┐   │
│  │ 🎟 LAUNCH50  +$0.50 credit                    │   │
│  │    Valid until Jun 18, 2026                   │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 🎟 FRIEND20  +20 messages  [expired]         │   │
│  └──────────────────────────────────────────────┘   │
│  + Apply another code                               │
└─────────────────────────────────────────────────────┘
```

"+ Apply another code" opens an inline `CouponApply`-style input without navigating away.

---

### 4.3 Coupon apply accessible from Profile page

Currently users must go to `/pricing` to apply a coupon. Add a `CouponApply` component inline within the Profile > Subscription section — collapsed by default, expanded when the user clicks "+ Apply a promo code".

```tsx
const [showCouponInput, setShowCouponInput] = useState(false)
```

```tsx
<button
  onClick={() => setShowCouponInput(v => !v)}
  className="flex items-center gap-1.5 text-xs text-violet-600 dark:text-violet-400 hover:underline mt-2"
>
  <Ticket size={11} />
  {showCouponInput ? 'Cancel' : 'Apply a promo code'}
</button>
{showCouponInput && <CouponApply onSuccess={() => setShowCouponInput(false)} />}
```

The existing `CouponApply` component needs an `onSuccess` prop added so the parent can close the input after redemption.

---

## Component Architecture Changes

### New shared component: `<CouponApply>`

The `CouponApply` function currently lives inside `Pricing.tsx`. Move it to `src/components/CouponApply.tsx` so it can be reused in both `Pricing.tsx` and `Profile.tsx`.

```
src/components/
  CouponApply.tsx       ← extracted from Pricing.tsx
```

**Props:**
```tsx
interface CouponApplyProps {
  onSuccess?: (result: CouponApplyResult) => void
  compact?: boolean   // smaller variant for Profile page
}
```

---

## Summary of New State in Admin.tsx — Coupons Tab

```tsx
// Phase 1
const [editingCode, setEditingCode]         = useState<string | null>(null)
const [editForm, setEditForm]               = useState<Partial<CouponRow>>({})
const [savingEdit, setSavingEdit]           = useState(false)
const [confirmDeleteCode, setConfirmDeleteCode] = useState<string | null>(null)
const [deletingCode, setDeletingCode]       = useState<string | null>(null)
const [copiedCode, setCopiedCode]           = useState<string | null>(null)
const [redemptions, setRedemptions]         = useState<Record<string, RedemptionRow[]>>({})
const [loadingRedemptions, setLoadingRedemptions] = useState<string | null>(null)
const [expandedRedemptionsCode, setExpandedRedemptionsCode] = useState<string | null>(null)

// Phase 2
const [couponSearch, setCouponSearch]               = useState('')
const [couponStatusFilter, setCouponStatusFilter]   = useState<'all' | 'active' | 'inactive' | 'expired' | 'depleted'>('all')
const [couponSort, setCouponSort]                   = useState<'newest' | 'most_used' | 'expiring'>('newest')

// Phase 3
const [couponStats, setCouponStats]   = useState<CouponStats | null>(null)
const [showBulkForm, setShowBulkForm] = useState(false)
const [bulkForm, setBulkForm]         = useState({ ... })
const [bulkResult, setBulkResult]     = useState<string[] | null>(null)
```

---

## Implementation Order

1. **Do first (highest impact):** Phase 1.3 Redemptions drawer — endpoint exists, just needs UI
2. **Do second:** Phase 1.4 Copy-to-clipboard — trivial, high daily-use value
3. **Do third:** Phase 1.1 Inline edit + Phase 1.2 Delete (together, same expand component)
4. **Do fourth:** Phase 4.1 Better success card in `CouponApply` — user-facing polish
5. **Do fifth:** Phase 2.1 Search + filter bar
6. **Do sixth:** Phase 3.1 Stats cards (requires backend Phase 2.1 first)
7. **Do after:** Phase 4.2 + 4.3 Profile page improvements (requires new `/me` endpoint)
8. **Do last:** Phase 2.2 Clone, Phase 3.2 Progress bar, Phase 3.3 Bulk generate form
