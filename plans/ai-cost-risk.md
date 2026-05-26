# Plan 2 — AI Cost & Margin Risk

## What It Shows

Added to the existing **AI Providers** tab (or a new sub-section):
- Cost per plan — is each plan profitable given AI spend?
- Users near/at budget limit this month — intervention list
- Aggregate cost by interaction type across all users
- Cache hit rate over time

---

## Backend

### New endpoint — `GET /admin/cost-analysis`

**Query 1 — Cost vs revenue per plan (margin analysis)**
```sql
SELECT
    pc.plan_id,
    pc.name                                         AS plan_name,
    pc.base_price_cents                             AS price_cents,
    pc.token_budget_cents                           AS budget_cents,
    COUNT(DISTINCT s.uid)                           AS active_users,
    COALESCE(SUM(tu.estimated_cost_cents), 0)       AS total_spent_cents,
    COALESCE(AVG(tu.estimated_cost_cents), 0)       AS avg_spent_cents,
    COALESCE(MAX(tu.estimated_cost_cents), 0)       AS max_spent_cents,
    -- actual AI cost as % of plan price
    CASE WHEN pc.base_price_cents > 0
         THEN ROUND((COALESCE(SUM(tu.estimated_cost_cents), 0) /
              (pc.base_price_cents * COUNT(DISTINCT s.uid)) * 100)::numeric, 1)
         ELSE 0 END                                 AS cost_revenue_pct
FROM plan_configs pc
LEFT JOIN subscriptions s
    ON s.plan_id = pc.plan_id AND s.status IN ('active', 'trialing')
LEFT JOIN token_usage tu
    ON tu.uid = s.uid
    AND tu.period_start = date_trunc('month', now())::date
GROUP BY pc.plan_id, pc.name, pc.base_price_cents, pc.token_budget_cents
ORDER BY pc.base_price_cents DESC
```

**Query 2 — Users at risk (>75% budget used this month)**
```sql
SELECT
    u.uid, u.email, u.display_name,
    COALESCE(s.plan_id, 'free_trial')               AS plan_id,
    pc.token_budget_cents                            AS budget_cents,
    tu.estimated_cost_cents                          AS spent_cents,
    ROUND((tu.estimated_cost_cents /
           pc.token_budget_cents * 100)::numeric, 1) AS pct_used
FROM token_usage tu
JOIN users u ON u.uid = tu.uid
LEFT JOIN subscriptions s
    ON s.uid = tu.uid AND s.status IN ('active', 'trialing')
JOIN plan_configs pc
    ON pc.plan_id = COALESCE(s.plan_id, 'free_trial')
WHERE tu.period_start = date_trunc('month', now())::date
  AND pc.token_budget_cents > 0
  AND (tu.estimated_cost_cents / pc.token_budget_cents) >= 0.75
ORDER BY pct_used DESC
LIMIT 50
```

**Query 3 — Cost by interaction type (all users, this month)**
```sql
SELECT
    interaction_type,
    COUNT(DISTINCT uid)              AS user_count,
    SUM(request_count)               AS total_requests,
    SUM(input_tokens)                AS total_input_tokens,
    SUM(output_tokens)               AS total_output_tokens,
    SUM(estimated_cost_cents)        AS total_cost_cents,
    AVG(estimated_cost_cents)        AS avg_cost_per_user_cents
FROM usage_by_interaction
WHERE period_start = date_trunc('month', now())::date
GROUP BY interaction_type
ORDER BY total_cost_cents DESC
```

**Query 4 — Cache hit rate last 6 months**
```sql
SELECT
    period_start,
    SUM(input_tokens)                AS total_input,
    SUM(cached_input_tokens)         AS total_cached,
    ROUND(
        CASE WHEN SUM(input_tokens) > 0
             THEN SUM(cached_input_tokens)::numeric / SUM(input_tokens) * 100
             ELSE 0 END, 1
    )                                AS cache_hit_pct,
    SUM(estimated_cost_cents)        AS total_cost_cents
FROM token_usage
WHERE period_start >= date_trunc('month', now() - interval '5 months')::date
GROUP BY period_start
ORDER BY period_start
```

**Response shape**
```json
{
  "plan_margins": [
    { "plan_id": "individual", "plan_name": "Individual",
      "price_cents": 1900, "budget_cents": 760,
      "active_users": 12, "total_spent_cents": 340.5,
      "avg_spent_cents": 28.4, "max_spent_cents": 143.2,
      "cost_revenue_pct": 1.5 }
  ],
  "at_risk_users": [
    { "uid": "...", "email": "...", "display_name": "...",
      "plan_id": "individual", "budget_cents": 760,
      "spent_cents": 692.1, "pct_used": 91.1 }
  ],
  "by_interaction": [
    { "interaction_type": "daily_chat", "user_count": 30,
      "total_requests": 1240, "total_cost_cents": 890.2 }
  ],
  "cache_trend": [
    { "period_start": "2026-01-01", "total_input": 120000,
      "total_cached": 48000, "cache_hit_pct": 40.0,
      "total_cost_cents": 220.4 }
  ]
}
```

---

## Frontend

### Where to add
Add a new **Cost Analysis** section at the top of the existing **AI Providers** tab, above the existing "Usage This Month" model breakdown table.

### UI layout

```
Cost vs Revenue by Plan
  Plan         Users  Avg spend  Max spend  Cost/Rev%  Margin health
  Individual   12     $0.28      $1.43      1.5%       ██ Healthy
  Family       4      $0.14      $0.44      0.4%       █  Healthy
  Free trial   110    $0.00      $0.01      —          —

Users Near Budget Limit  (⚠ 3 users above 75%)
  alice@example.com   Individual   ████████████░  91.1%
  bob@example.com     Student      ████████░░░░░  78.4%

Cost by Feature (all users this month)
  daily_chat   ████████████  $8.90  1,240 req
  journey      ██████        $4.20    320 req
  spark        ██            $1.10    890 req

Cache Hit Rate (6 months)
  Jan ████  40%   Feb ██████  52%   ...
```

**Color coding for margin health:**
- `cost_revenue_pct < 30%` → green "Healthy"
- `30–60%` → amber "Watch"
- `>60%` → red "At risk"

**At-risk users** — clicking a row expands to show the same detail panel already built for the Users tab (reuse `handleExpandUser`).

---

## Notes

- `cost_revenue_pct` = (actual AI spend / plan price × number of users) × 100. If this approaches 40% you lose money because the token_budget is set at 40% of plan price.
- At-risk users list helps you proactively reach out or raise the budget ceiling before they churn.
- Cache hit rate trend shows whether your prompt engineering is improving — a rising trend means lower cost per request.
