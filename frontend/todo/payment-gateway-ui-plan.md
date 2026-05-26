# Payment Gateway UI Plan
## Admin Panel + Pricing Page — Stripe & Razorpay

---

## Current State

| Component | Status |
|-----------|--------|
| Pricing page shows plans from DB | ✅ Working |
| Geo-detects India, shows ₹ price | ✅ Working (if `base_price_inr_paise` set in DB) |
| Razorpay modal checkout (order flow) | ✅ Working |
| Stripe redirect checkout | ✅ Working |
| Admin Plans tab — edit `stripe_price_id` | ✅ Working |
| Admin Plans tab — edit `base_price_inr_paise` | ❌ Field missing |
| Admin Plans tab — edit `razorpay_plan_id` | ❌ Field missing |
| Admin Plans tab — provision buttons | ❌ Not built |
| Admin Plans tab — gateway status badges | ❌ Not built |
| Admin Plans tab — create new plan | ❌ Not built |
| Pricing page — Razorpay subscription flow | ❌ Only handles order flow |

---

## Files to Modify

### 1. `frontend/src/pages/Admin.tsx` — Major update to Plans tab

#### A. Update `PlanRow` interface

```typescript
interface PlanRow {
  plan_id: string
  name: string
  base_price_cents: number
  base_price_inr_paise: number | null    // ADD
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
  stripe_price_id: string | null
  razorpay_plan_id: string | null        // ADD
}
```

#### B. Add provisioning state

```typescript
const [provisioning, setProvisioning] = useState<Record<string, string | null>>({})
// key: plan_id, value: "stripe" | "razorpay" | "both" | null
```

#### C. Add `handleProvision` function

```typescript
const handleProvision = async (planId: string, gateway: 'stripe' | 'razorpay' | 'both') => {
  setProvisioning(prev => ({ ...prev, [planId]: gateway }))
  try {
    const token = await getToken()
    const res = await fetch(`/api/v1/admin/plans/${planId}/provision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ gateway }),
    })
    const data = await res.json()
    if (res.ok) {
      // Refresh plan list so new IDs show immediately
      setPlans(prev => prev.map(p => {
        if (p.plan_id !== planId) return p
        const stripe = data.provisioned?.stripe ?? {}
        const razorpay = data.provisioned?.razorpay ?? {}
        return {
          ...p,
          stripe_price_id: stripe.stripe_price_id ?? p.stripe_price_id,
          razorpay_plan_id: razorpay.razorpay_plan_id ?? p.razorpay_plan_id,
        }
      }))
    } else {
      alert(data.detail ?? 'Provisioning failed.')
    }
  } finally {
    setProvisioning(prev => ({ ...prev, [planId]: null }))
  }
}
```

#### D. Add `handleCreatePlan` function

```typescript
interface NewPlanForm {
  plan_id: string
  name: string
  base_price_cents: string      // string for input, parse on submit
  base_price_inr_paise: string
  token_budget_cents: string
  max_seats: string
}

const [newPlanForm, setNewPlanForm] = useState<NewPlanForm>({
  plan_id: '', name: '', base_price_cents: '', base_price_inr_paise: '',
  token_budget_cents: '', max_seats: '1',
})
const [creatingPlan, setCreatingPlan] = useState(false)

const handleCreatePlan = async () => {
  if (!newPlanForm.plan_id || !newPlanForm.name) return
  setCreatingPlan(true)
  try {
    const token = await getToken()
    const res = await fetch('/api/v1/admin/plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        plan_id: newPlanForm.plan_id.toLowerCase().replace(/\s+/g, '_'),
        name: newPlanForm.name,
        base_price_cents: parseInt(newPlanForm.base_price_cents) || 0,
        base_price_inr_paise: parseInt(newPlanForm.base_price_inr_paise) || null,
        token_budget_cents: parseInt(newPlanForm.token_budget_cents) || 0,
        max_seats: parseInt(newPlanForm.max_seats) || 1,
      }),
    })
    const data = await res.json()
    if (res.ok) {
      setPlans(prev => [...prev, data.plan])
      setNewPlanForm({ plan_id: '', name: '', base_price_cents: '', base_price_inr_paise: '', token_budget_cents: '', max_seats: '1' })
    } else {
      alert(data.detail ?? 'Failed to create plan.')
    }
  } finally {
    setCreatingPlan(false)
  }
}
```

---

#### E. Plans Tab UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Pricing Preview  (existing card grid)                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  + Create New Plan                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Plan ID slug  │ Display Name  │ USD $/mo         │   │
│  │ [           ] │ [           ] │ [     ]          │   │
│  │ INR ₹/mo      │ Token budget  │ Max seats        │   │
│  │ [           ] │ [           ] │ [1    ]          │   │
│  │                          [Create Plan]           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Edit Plan Configuration                                │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Individual  (individual)          [Save]        │   │
│  │                                                  │   │
│  │  USD Price (¢) │ INR Price (paise) │ Token budget│   │
│  │  [999        ] │ [79900          ] │ [5000      ]│   │
│  │  Max seats     │ Active            │             │   │
│  │  [1          ] │ [✓]               │             │   │
│  │                                                  │   │
│  │  Gateway Configuration                           │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │ Stripe   [✓ price_1Abc...]  [Re-provision] │  │   │
│  │  │ Razorpay [✓ plan_Xyz...]   [Re-provision] │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  │                  [Provision Both Gateways]       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Gateway status badge logic:**
- `stripe_price_id` set → green badge `✓ Stripe price_1Abc...` + `[Re-provision]` button
- `stripe_price_id` null → amber badge `! Not provisioned` + `[Provision in Stripe]` button
- Same pattern for `razorpay_plan_id`

**"Provision Both Gateways" button:**
- Visible only when plan has `base_price_cents > 0` (paid plan)
- Calls `handleProvision(planId, 'both')`
- Shows spinner while running
- On success: both badges turn green with new IDs

**Token budget helper text:**
Show a human-readable conversion beneath the token_budget_cents field:
```
token_budget_cents = 5000  →  "≈ $0.50 of AI spend / month"
```
Conversion: `$${(value / 10000).toFixed(2)}`

---

### 2. `frontend/src/pages/Pricing.tsx` — Handle subscription vs order response

The backend now returns `checkout_type: "subscription" | "order"` for Razorpay.

Update `handleRazorpayCheckout` signature and `handleSelect`:

```typescript
const handleRazorpayCheckout = async (
  data: {
    checkout_type: 'subscription' | 'order'
    subscription_id?: string
    order_id?: string
    amount: number
    currency: string
  },
  planId: string,
  token: string,
) => {
  const loaded = await loadRazorpayScript()
  if (!loaded) { alert('Could not load Razorpay. Check your connection.'); return }

  return new Promise<void>((resolve) => {
    const options: any = {
      key: razorpayKeyId,
      amount: data.amount,
      currency: data.currency,
      name: 'ecalt',
      description: `${planId} plan`,
      prefill: { email: user?.email ?? '' },
      modal: { ondismiss: () => { setLoadingPlan(null); resolve() } },
    }

    if (data.checkout_type === 'subscription') {
      options.subscription_id = data.subscription_id
      // Subscription handler — no signature to verify client-side
      // Backend webhook handles subscription.charged
      options.handler = async () => { navigate('/learn?upgraded=true'); resolve() }
    } else {
      options.order_id = data.order_id
      // Order handler — verify signature with backend
      options.handler = async (response: RazorpayResponse) => {
        const verifyRes = await fetch('/api/v1/subscriptions/razorpay/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
            plan_id: planId,
          }),
        })
        if (verifyRes.ok) navigate('/learn?upgraded=true')
        else alert('Payment verification failed. Contact support with your payment ID.')
        resolve()
      }
    }

    new (window as any).Razorpay(options).open()
  })
}
```

Update `handleSelect` to pass the full `data` object (not just `{ order_id, amount, currency }`):

```typescript
if (data.gateway === 'razorpay') {
  await handleRazorpayCheckout(data, planId, token!)  // data now includes checkout_type
}
```

---

## Component Checklist

### Admin.tsx

- [ ] Update `PlanRow` interface (add `base_price_inr_paise`, `razorpay_plan_id`)
- [ ] Add provisioning state + `handleProvision` function
- [ ] Add `NewPlanForm` state + `handleCreatePlan` function
- [ ] "Create New Plan" section (collapsible or always open)
- [ ] Edit Plan grid: add INR price field + Razorpay plan ID field
- [ ] Gateway status badges (Stripe / Razorpay configured / not)
- [ ] "Provision in Stripe" button per plan
- [ ] "Provision in Razorpay" button per plan
- [ ] "Provision Both Gateways" shortcut button
- [ ] Token budget helper text showing dollar equivalent

### Pricing.tsx

- [ ] Update `handleRazorpayCheckout` to accept `checkout_type`
- [ ] Handle `subscription_id` checkout path (no client-side verify needed)
- [ ] Handle `order_id` checkout path (existing verify endpoint)
- [ ] Update `handleSelect` call to pass full `data` object

---

## UX Notes

**Provision flow should be clear to admin:**
1. Admin creates or edits a plan (set name, USD price, INR price, token budget)
2. Clicks Save
3. Sees gateway status: "⚠ Not provisioned in Stripe" / "⚠ Not provisioned in Razorpay"
4. Clicks "Provision in Stripe" → spinner → "✓ price_1Abc..."
5. Clicks "Provision in Razorpay" → spinner → "✓ plan_Xyz..."
6. Plan is now live — users can subscribe

**Free plan (`base_price_cents = 0`):**
- Never show Provision buttons (free plan doesn't need gateway IDs)
- Hide INR price field (not relevant)

**Error handling:**
- If STRIPE_SECRET_KEY not configured: show "Stripe not configured — add STRIPE_SECRET_KEY to server env"
- If RAZORPAY_KEY_ID not configured: show "Razorpay not configured — add RAZORPAY_KEY_ID to server env"
- Both messages shown as inline alerts near the provision buttons, not page-level errors

---

## Implementation Order

1. Update `PlanRow` interface (5 min)
2. Add INR + Razorpay fields to the edit grid (10 min)
3. Add gateway status badges (15 min)
4. Add provision buttons + `handleProvision` (20 min)
5. Add "Create New Plan" form + `handleCreatePlan` (20 min)
6. Update `Pricing.tsx` Razorpay checkout handler (15 min)
