# Plan 4 — Feature Usage Breakdown

## What It Shows

Added to the existing **Overview** tab as a new section below the stats cards:
- Which features drive engagement (requests per feature, all users)
- Which features drive cost (cost per feature, all users)
- Per-feature trend over the last 6 months
- Model usage distribution (which models are being called most)

---

## Backend

### New endpoint — `GET /admin/feature-usage`

**Query 1 — Feature summary this month**
```sql
SELECT
    interaction_type,
    COUNT(DISTINCT uid)         AS unique_users,
    SUM(request_count)          AS total_requests,
    SUM(input_tokens)           AS total_input_tokens,
    SUM(output_tokens)          AS total_output_tokens,
    SUM(cached_input_tokens)    AS total_cached_tokens,
    SUM(estimated_cost_cents)   AS total_cost_cents,
    ROUND(AVG(estimated_cost_cents / NULLIF(request_count, 0))::numeric, 6)
                                AS avg_cost_per_request_cents
FROM usage_by_interaction
WHERE period_start = date_trunc('month', now())::date
GROUP BY interaction_type
ORDER BY total_requests DESC
```

**Query 2 — Feature trend (last 6 months)**
```sql
SELECT
    period_start,
    interaction_type,
    SUM(request_count)        AS total_requests,
    SUM(estimated_cost_cents) AS total_cost_cents
FROM usage_by_interaction
WHERE period_start >= date_trunc('month', now() - interval '5 months')::date
GROUP BY period_start, interaction_type
ORDER BY period_start, total_requests DESC
```

**Query 3 — Model usage this month**

(already in `/admin/usage` but duplicated here for a self-contained response)
```sql
SELECT
    cm.model_used,
    COUNT(*)                    AS message_count,
    COALESCE(
        SUM(tu.estimated_cost_cents), 0
    )                           AS total_cost_cents
FROM conversation_messages cm
JOIN conversations c ON c.id = cm.conversation_id
LEFT JOIN token_usage tu
    ON tu.uid = c.uid
    AND tu.period_start = date_trunc('month', now())::date
WHERE cm.created_at >= date_trunc('month', now())
  AND cm.role = 'assistant'
  AND cm.model_used IS NOT NULL
GROUP BY cm.model_used
ORDER BY message_count DESC
```

**Response shape**
```json
{
  "this_month": [
    { "interaction_type": "daily_chat",
      "unique_users": 45, "total_requests": 1240,
      "total_input_tokens": 980000, "total_output_tokens": 740000,
      "total_cost_cents": 890.2,
      "avg_cost_per_request_cents": 0.718 }
  ],
  "trend": [
    { "period_start": "2026-01-01",
      "interaction_type": "daily_chat",
      "total_requests": 840, "total_cost_cents": 620.1 }
  ],
  "models": [
    { "model_used": "gpt-4.1-nano", "message_count": 1240,
      "total_cost_cents": 890.2 }
  ]
}
```

---

## Frontend

### Where to add
New section at the bottom of the existing **Overview** tab (after the Active Plans grid), replacing / augmenting the existing global stats.

### UI layout

```
Feature Usage — May 2026

  Feature       Users  Requests  Cost     Cost/req   Share of cost
  Chat          45     1,240     $8.90    $0.0007    ████████████  62%
  Journey       30       320     $4.20    $0.013     ████████      29%
  Step Content  22       180     $0.80    $0.004     ██             6%
  Spark         15       890     $0.44    $0.0005    █              3%

6-Month Cost Trend per Feature (stacked or grouped bar)
  [Jan][Feb][Mar][Apr][May][Jun]
  Each bar grouped by feature — shows whether cost is growing per feature

Model Distribution
  gpt-4.1-nano  ████████████████████  1,240 calls  $8.90
  gpt-4o-mini   ████                    320 calls  $4.20
```

**Table columns**: Feature (friendly label), Unique users, Total requests, Total cost, Avg cost/request, horizontal bar showing share of total cost.

**Trend chart**: Group bars by month. Each feature gets its own colour. Keep it simple — 3 to 4 bars per month maximum, collapse small features into "Other".

**Implementation tip**: The trend data is already structured for a grouped bar chart. Use CSS flex bars (same technique as the existing daily usage chart) rather than a chart library.

---

## Notes

- `usage_by_interaction` only has data from the date the migration was run. First month will be partial.
- `avg_cost_per_request` is the most actionable number — if `journey` costs 20× more per call than `chat`, that informs model routing decisions.
- `unique_users` per feature shows adoption — a feature can have high cost but low unique users, meaning a small power-user base is driving it.
- The model distribution section here overlaps with the existing AI tab; consider removing the duplicate from the AI tab once this is live.
