# Plan 3 — Engagement & Retention

## What It Shows

A new **Retention** tab in the admin panel:
- DAU / WAU / MAU and the stickiness ratio (DAU/MAU)
- D1, D7, D30 retention — % of users who made an AI request N days after signup
- Weekly new user signups (last 12 weeks)
- Inactive users — signed up but zero AI calls in last 14 days

---

## Backend

### New endpoint — `GET /admin/retention`

**Query 1 — DAU / WAU / MAU**
```sql
SELECT
    COUNT(DISTINCT CASE WHEN last_active_date = CURRENT_DATE
                        THEN uid END)                        AS dau,
    COUNT(DISTINCT CASE WHEN last_active_date >= CURRENT_DATE - 6
                        THEN uid END)                        AS wau,
    COUNT(DISTINCT CASE WHEN last_active_date >= CURRENT_DATE - 29
                        THEN uid END)                        AS mau
FROM users
```

**Query 2 — D1 / D7 / D30 retention**

A user "retained at D7" means they made at least one AI request between day 7 and day 14 after signup.

```sql
WITH cohort AS (
    SELECT
        u.uid,
        u.created_at::date AS signup_date,
        MIN(tu_all.period_start) AS first_active_month
    FROM users u
    LEFT JOIN token_usage tu_all ON tu_all.uid = u.uid
    WHERE u.created_at >= now() - interval '60 days'
    GROUP BY u.uid, u.created_at
),
activity AS (
    SELECT DISTINCT
        cm.conversation_id,
        c.uid,
        cm.created_at::date AS active_date
    FROM conversation_messages cm
    JOIN conversations c ON c.id = cm.conversation_id
    WHERE cm.role = 'user'
)
SELECT
    COUNT(DISTINCT c.uid)                                  AS cohort_size,
    COUNT(DISTINCT CASE
        WHEN a.active_date BETWEEN c.signup_date + 1
                               AND c.signup_date + 2
        THEN c.uid END)                                    AS retained_d1,
    COUNT(DISTINCT CASE
        WHEN a.active_date BETWEEN c.signup_date + 7
                               AND c.signup_date + 14
        THEN c.uid END)                                    AS retained_d7,
    COUNT(DISTINCT CASE
        WHEN a.active_date BETWEEN c.signup_date + 30
                               AND c.signup_date + 60
        THEN c.uid END)                                    AS retained_d30
FROM cohort c
LEFT JOIN activity a ON a.uid = c.uid
```

**Query 3 — Weekly new signups (last 12 weeks)**
```sql
SELECT
    date_trunc('week', created_at)::date AS week_start,
    COUNT(*)                             AS new_users
FROM users
WHERE created_at >= now() - interval '12 weeks'
GROUP BY week_start
ORDER BY week_start
```

**Query 4 — Inactive users (signed up, never returned)**
```sql
SELECT
    u.uid, u.email, u.display_name,
    u.created_at::date                         AS signup_date,
    COALESCE(s.plan_id, 'free_trial')          AS plan_id,
    COALESCE(tu.message_count, 0)              AS ai_requests_ever,
    u.last_active_date
FROM users u
LEFT JOIN subscriptions s
    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
LEFT JOIN token_usage tu
    ON tu.uid = u.uid
    AND tu.period_start = date_trunc('month', now())::date
WHERE u.created_at <= now() - interval '3 days'   -- gave them time to activate
  AND (u.last_active_date IS NULL
       OR u.last_active_date < CURRENT_DATE - 14)
ORDER BY u.created_at DESC
LIMIT 100
```

**Response shape**
```json
{
  "active_users": {
    "dau": 12, "wau": 38, "mau": 87,
    "stickiness": 13.8
  },
  "retention": {
    "cohort_size": 52,
    "cohort_window": "last 60 days",
    "d1_count": 28, "d1_pct": 53.8,
    "d7_count": 18, "d7_pct": 34.6,
    "d30_count": 9,  "d30_pct": 17.3
  },
  "weekly_signups": [
    { "week_start": "2026-03-31", "new_users": 8 },
    { "week_start": "2026-04-07", "new_users": 14 }
  ],
  "inactive_users": [
    { "uid": "...", "email": "...", "display_name": "...",
      "signup_date": "2026-05-10", "plan_id": "free_trial",
      "ai_requests_ever": 0, "last_active_date": null }
  ]
}
```

---

## Frontend

### New tab
Add `{ id: 'retention', label: 'Retention' }` to `TABS`.

### UI layout

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ DAU          │ │ WAU          │ │ MAU          │ │ Stickiness   │
│ 12           │ │ 38           │ │ 87           │ │ 13.8%        │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

Retention (52 users who signed up in last 60 days)
  D1  ████████████████████████████  53.8%  (28 users came back next day)
  D7  ████████████████              34.6%  (18 users active in week 2)
  D30 ████████                      17.3%  (9 users active in month 2)

Weekly New Signups (last 12 weeks)
  [bar chart — one bar per week]

Inactive Users (14+ days no activity)  100 shown
  [same card style as Users tab — email, plan, signup date, days inactive]
```

**Stickiness** = DAU/MAU × 100. Industry benchmark: >20% is strong for a learning app.

**Retention bars** — use a single colour (violet) with the % label on the right.

**Inactive users** — each row shows days since signup and days since last active. No expand needed; just a list for bulk action (future: trigger a re-engagement email).

---

## Notes

- D1/D7/D30 cohort window is last 60 days — long enough to have D30 data from the older cohort members.
- `stickiness` below 10% means most users open the app less than once every 10 days — action needed.
- Inactive users list is the re-engagement target list — future work to wire up a "send nudge" button.
- `last_active_date` on the `users` table must be kept up to date; it's currently set by the streak update logic.
