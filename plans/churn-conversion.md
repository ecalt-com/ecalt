# Plan 5 — Churn & Conversion Funnel

## What It Shows

A new **Funnel** tab in the admin panel:
- Free → paid conversion rate (last 30 / 60 / 90 days)
- Cancellation trend (subscriptions cancelled per month)
- Upgrades vs downgrades (plan change events)
- Time-to-convert (median days from signup to first paid subscription)
- Users who exhausted free trial messages but never upgraded

---

## Backend

### New endpoint — `GET /admin/funnel`

**Query 1 — Free → paid conversion**

Count users who signed up in each window and then got an active subscription.
```sql
WITH signups AS (
    SELECT uid, created_at::date AS signup_date
    FROM users
),
conversions AS (
    SELECT s.uid, MIN(s.created_at) AS converted_at
    FROM subscriptions s
    WHERE s.status IN ('active', 'trialing')
      AND s.plan_id != 'free_trial'
    GROUP BY s.uid
)
SELECT
    COUNT(DISTINCT sg.uid)                                          AS total_signups,
    COUNT(DISTINCT CASE
        WHEN co.converted_at::date <= sg.signup_date + 30
        THEN sg.uid END)                                            AS converted_30d,
    COUNT(DISTINCT CASE
        WHEN co.converted_at::date <= sg.signup_date + 60
        THEN sg.uid END)                                            AS converted_60d,
    COUNT(DISTINCT CASE
        WHEN co.converted_at::date <= sg.signup_date + 90
        THEN sg.uid END)                                            AS converted_90d,
    ROUND(AVG(
        CASE WHEN co.converted_at IS NOT NULL
             THEN (co.converted_at::date - sg.signup_date)
        END
    )::numeric, 1)                                                  AS avg_days_to_convert
FROM signups sg
LEFT JOIN conversions co ON co.uid = sg.uid
WHERE sg.signup_date >= CURRENT_DATE - 180
```

**Query 2 — Cancellations per month (last 6 months)**
```sql
SELECT
    date_trunc('month', updated_at)::date   AS month,
    COUNT(*)                                AS cancellations
FROM subscriptions
WHERE status = 'cancelled'
  AND updated_at >= now() - interval '6 months'
GROUP BY month
ORDER BY month
```

**Query 3 — New activations per month (to pair with cancellations)**
```sql
SELECT
    date_trunc('month', created_at)::date   AS month,
    COUNT(*)                                AS new_subscriptions
FROM subscriptions
WHERE status IN ('active', 'trialing')
  AND plan_id != 'free_trial'
  AND created_at >= now() - interval '6 months'
GROUP BY month
ORDER BY month
```

**Query 4 — Trial exhausted, never upgraded**
```sql
SELECT
    u.uid, u.email, u.display_name, u.created_at::date AS signup_date,
    COALESCE(mc.n, 0) AS lifetime_messages
FROM users u
LEFT JOIN subscriptions s
    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
    AND s.plan_id != 'free_trial'
LEFT JOIN (
    SELECT c.uid, COUNT(*) AS n
    FROM conversation_messages cm
    JOIN conversations c ON c.id = cm.conversation_id
    WHERE cm.role = 'user'
    GROUP BY c.uid
) mc ON mc.uid = u.uid
WHERE s.uid IS NULL                      -- never paid
  AND COALESCE(mc.n, 0) >= 6            -- hit or exceeded free message limit
ORDER BY u.created_at DESC
LIMIT 100
```

**Response shape**
```json
{
  "conversion": {
    "total_signups_180d": 210,
    "converted_30d": 18,  "converted_30d_pct": 8.6,
    "converted_60d": 28,  "converted_60d_pct": 13.3,
    "converted_90d": 34,  "converted_90d_pct": 16.2,
    "avg_days_to_convert": 11.4
  },
  "monthly_churn": [
    { "month": "2026-01-01", "cancellations": 2, "new_subscriptions": 14 }
  ],
  "trial_exhausted_never_upgraded": [
    { "uid": "...", "email": "...", "display_name": "...",
      "signup_date": "2026-04-12", "lifetime_messages": 7 }
  ]
}
```

---

## Frontend

### New tab
Add `{ id: 'funnel', label: 'Funnel' }` to `TABS`.

### UI layout

```
Free → Paid Conversion  (last 180 days, 210 signups)

  D30  ██         8.6%   18 users converted within 30 days
  D60  █████      13.3%  28 users converted within 60 days
  D90  ███████    16.2%  34 users converted within 90 days

  Median time to convert: 11.4 days

Activations vs Cancellations (last 6 months)
  Month    New subs  Cancellations  Net
  Jan 26   14        2              +12   ████████████
  Feb 26   8         3              +5    █████
  Mar 26   11        5              +6    ██████

Trial Exhausted — Never Upgraded  (100 shown)
  These users hit the 6-message limit but did not subscribe.
  Prime re-engagement targets.

  [same card style as Users tab — email, signup date, messages used]
```

**Conversion funnel bars** — three stacked/overlapping bars (D30 ⊂ D60 ⊂ D90 conceptually). Show as horizontal bars with a % label.

**Net activations chart** — two columns per month side by side: green for new, red for cancellations. A net line overlay is optional.

**Trial exhausted list** — future work: add a "Send re-engagement email" button per row that calls a new `POST /admin/nudge/{uid}` endpoint (out of scope for this plan).

---

## Notes

- Subscription `created_at` is used as the activation date, not `current_period_start`, because `current_period_start` can be null for Razorpay users.
- `avg_days_to_convert` of < 7 is excellent — it means the product hooks users quickly. > 30 suggests they need more nudges before converting.
- The "trial exhausted never upgraded" list is your highest-intent re-engagement audience — they used all their messages, which proves intent; they just haven't paid yet.
- Churn rate = cancellations / (active subscribers at start of month). You'd need a subscription state snapshot to compute this precisely; the query above is a simpler proxy.
