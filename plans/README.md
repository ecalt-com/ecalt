# Admin Analytics — Implementation Queue

Each file in this folder is a self-contained implementation plan for one analytics feature.
Pick one, implement it end-to-end, then move to the next.

## Priority Order

| # | File | Feature | Effort | Decision value |
|---|------|---------|--------|----------------|
| 1 | [revenue-subscription.md](./revenue-subscription.md) | MRR, plan distribution, gateway split | Low | Highest — core business health |
| 2 | [ai-cost-risk.md](./ai-cost-risk.md) | Cost per plan, users near budget limit | Low | High — protects margin |
| 3 | [engagement-retention.md](./engagement-retention.md) | DAU/WAU/MAU, D7/D30 retention cohorts | Medium | High — tells you if product works |
| 4 | [feature-usage.md](./feature-usage.md) | Feature breakdown, cost by interaction type | Low | Medium — product decisions |
| 5 | [churn-conversion.md](./churn-conversion.md) | Free→paid funnel, cancellation trend | Medium | High — growth lever |
| 6 | [content-learning.md](./content-learning.md) | Top topics, journey completion, drop-off | Medium | Medium — content strategy |

## Shared Conventions

- All new admin endpoints live in `backend/app/api/v1/endpoints/admin.py`
- All queries use the existing `get_db()` pattern — raw psycopg2, no ORM
- Frontend changes go inside the existing tab system in `frontend/src/pages/Admin.tsx`
- New tabs can be added to the `TABS` array; new sections can be added inside existing tabs
- All endpoints are guarded with `get_admin_user` dependency
- Costs are stored in **cents** throughout — divide by 100 for dollar display
- Dates use PostgreSQL `date_trunc` for bucketing

## Existing Infrastructure You Can Reuse

| Asset | Location |
|---|---|
| `token_usage` table | Per-user monthly aggregates |
| `usage_by_interaction` table | Per-user per-feature monthly aggregates |
| `subscriptions` table | Plan, status, gateway, period dates |
| `plan_configs` table | Pricing, token budgets |
| `conversations` + `conversation_messages` | Chat engagement |
| `user_progress` | Journey step completions |
| `journeys` | Journey metadata |
| `users` table | signup date, streak, last_active_date |
| `fmtCents`, `fmtTokens`, `fmtMonth` helpers | Already in Admin.tsx |
