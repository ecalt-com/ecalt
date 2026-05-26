# Plan 1 — Revenue & Subscription Dashboard

## What It Shows

A new **Revenue** tab in the admin panel with:
- MRR card (current month recurring revenue)
- Plan distribution bar (users per plan)
- Gateway split (Stripe USD vs Razorpay INR)
- Active vs churned vs trial counts
- ARPU (average revenue per active paid user)

---

## Backend

### New endpoint — `GET /admin/revenue`

Add to `admin.py`. One DB connection, three queries.

**Query 1 — MRR and plan distribution**
```sql
SELECT
    pc.plan_id,
    pc.name                                     AS plan_name,
    pc.base_price_cents                         AS price_cents,
    pc.base_price_inr_paise,
    COUNT(s.uid)                                AS user_count,
    -- MRR in cents (USD only; INR subscribers counted separately)
    SUM(CASE WHEN s.payment_gateway = 'stripe'
             THEN pc.base_price_cents ELSE 0 END) AS mrr_usd_cents,
    SUM(CASE WHEN s.payment_gateway = 'razorpay'
             THEN pc.base_price_inr_paise ELSE 0 END) AS mrr_inr_paise
FROM subscriptions s
JOIN plan_configs pc ON pc.plan_id = s.plan_id
WHERE s.status IN ('active', 'trialing')
GROUP BY pc.plan_id, pc.name, pc.base_price_cents, pc.base_price_inr_paise
ORDER BY pc.base_price_cents DESC
```

**Query 2 — Status breakdown**
```sql
SELECT
    COALESCE(s.status, 'no_subscription') AS status,
    COUNT(*)                              AS user_count
FROM users u
LEFT JOIN subscriptions s ON s.uid = u.uid
GROUP BY s.status
```

**Query 3 — Gateway split**
```sql
SELECT
    payment_gateway,
    COUNT(*)                        AS subscriptions,
    SUM(pc.base_price_cents)        AS total_usd_cents,
    SUM(pc.base_price_inr_paise)    AS total_inr_paise
FROM subscriptions s
JOIN plan_configs pc ON pc.plan_id = s.plan_id
WHERE s.status IN ('active', 'trialing')
GROUP BY payment_gateway
```

**Response shape**
```json
{
  "plan_distribution": [
    { "plan_id": "individual", "plan_name": "Individual",
      "price_cents": 1900, "user_count": 12,
      "mrr_usd_cents": 22800, "mrr_inr_paise": 0 }
  ],
  "status_breakdown": [
    { "status": "active", "user_count": 34 },
    { "status": "trialing", "user_count": 8 },
    { "status": "no_subscription", "user_count": 110 }
  ],
  "gateway_split": [
    { "payment_gateway": "stripe", "subscriptions": 20,
      "total_usd_cents": 38000, "total_inr_paise": 0 },
    { "payment_gateway": "razorpay", "subscriptions": 14,
      "total_usd_cents": 0, "total_inr_paise": 1118600 }
  ],
  "summary": {
    "total_mrr_usd_cents": 38000,
    "total_mrr_inr_paise": 1118600,
    "total_paid_users": 34,
    "total_trial_users": 8,
    "total_free_users": 110,
    "arpu_usd_cents": 1118          -- mrr_usd / paid_users
  }
}
```

---

## Frontend

### New tab
Add `{ id: 'revenue', label: 'Revenue' }` to the `TABS` array in `Admin.tsx`.

### New state
```ts
interface RevenueData { ... }   // matches response shape above
const [revenue, setRevenue] = useState<RevenueData | null>(null)
```

Fetch `GET /admin/revenue` alongside the other initial loads.

### UI layout

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ MRR (USD)    │ │ MRR (INR)    │ │ Paid users   │ │ ARPU         │
│ $380.00      │ │ ₹11,186      │ │ 34           │ │ $11.18       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

Plan Distribution
  Individual  ████████████  12 users  $228/mo
  Student     ██████        6 users   $54/mo
  Family      ████          4 users   $156/mo
  Free trial  ██████████████████████  110 users

Status Breakdown
  Active ██████████  34    Trial ████  8    Free ████████████████  110

Gateway Split
  Stripe (USD)     ████████████  20 subs   $380/mo
  Razorpay (INR)   ████████      14 subs   ₹11,186/mo
```

Each plan distribution bar is a horizontal bar scaled to max user count.
Use `violet-500` for paid plans, `slate-400` for free.

---

## Notes

- "MRR" here is a snapshot (active subs × plan price), not accounting for mid-cycle upgrades
- INR and USD are shown separately — don't try to convert them
- Trial users are counted separately; they are not yet revenue
- ARPU excludes trial and free users from the denominator
