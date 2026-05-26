# Token Plan — Centralized Budget System

Every AI call in ECALT routes through a single budget enforcement and logging layer. This document explains how plan limits are set, enforced, and observed.

---

## Plan Budgets

All monetary values are stored as **fractional cents (float)**, not dollars.

| Plan | Monthly Token Budget | Lifetime Chat Messages | Price |
|---|---|---|---|
| `free_trial` | 20¢ | 6 messages | Free |
| `student` | 360¢ ($3.60) | Unlimited | $9/mo |
| `individual` | 760¢ ($7.60) | Unlimited | $19/mo |

Budgets come from the `plan_configs.token_budget_cents` column. Admins can edit them live via `PATCH /api/v1/admin/plans/{plan_id}` — no deploy needed.

Coupon credits (`coupon_redemptions.credit_applied_cents`) stack on top of the plan budget. Expired credits are excluded automatically.

---

## Gating Logic

### `check_budget(uid, context)`

Called before every AI call that is gated. Returns `(allowed: bool, reason: str)`.

| Plan | Context | Gate |
|---|---|---|
| `free_trial` | `"chat"` | Lifetime message count ≤ `lifetime_message_limit + bonus_messages` |
| `free_trial` | `"ai"` | Monthly `estimated_cost_cents` < `token_budget_cents + coupon_credits` |
| Any paid plan | `"chat"` or `"ai"` | Monthly `estimated_cost_cents` < `token_budget_cents + coupon_credits` |

When blocked, the endpoint raises `HTTP 402`:
```json
{"error": "budget_exhausted", "upgrade_url": "/pricing"}
{"error": "free_trial_exhausted", "upgrade_url": "/pricing"}
```

### Per-endpoint gating

| Endpoint | Budget context | Gated for guests? |
|---|---|---|
| `POST /spark` | `"ai"` | No — guests use session window only (5/hour) |
| `POST /explore` | `"ai"` | N/A — requires auth |
| `GET /journeys/.../content` | `"ai"` | N/A — requires auth |
| `POST /chat/stream` | `"chat"` | N/A — requires auth |

Guest spark users are rate-limited by `spark_usage` table (5 sparks per 60-minute window) but are never checked against a plan budget since they have no account.

---

## Usage Recording

### `record_usage(uid, input_tokens, output_tokens, model, interaction_type)`

Called after every successful AI call. Upserts into `token_usage`:

```sql
INSERT INTO token_usage (uid, period_start, input_tokens, output_tokens, estimated_cost_cents, message_count)
VALUES (...)
ON CONFLICT (uid, period_start) DO UPDATE SET
    input_tokens         = token_usage.input_tokens + EXCLUDED.input_tokens,
    output_tokens        = token_usage.output_tokens + EXCLUDED.output_tokens,
    estimated_cost_cents = token_usage.estimated_cost_cents + EXCLUDED.estimated_cost_cents,
    message_count        = token_usage.message_count + 1,
    updated_at           = now()
RETURNING estimated_cost_cents, message_count
```

`period_start` is always the first day of the current calendar month. Usage resets at the start of each billing month.

### Token count accuracy

`complete_text()` (non-streaming) returns actual token counts from the API response (`resp.usage.*`). `stream_completion()` (used by chat) yields actual counts on the final chunk. No character-based estimates are used.

### Cost table (cents per token)

| Model | Input (¢/tok) | Output (¢/tok) |
|---|---|---|
| gpt-4.1-nano | 0.000010 | 0.000040 |
| gpt-4o-mini | 0.000015 | 0.000060 |
| gpt-4.1-mini | 0.000040 | 0.000160 |
| gpt-4o | 0.000250 | 0.001000 |
| gpt-4.1 | 0.000200 | 0.000800 |
| o1-mini | 0.000300 | 0.001200 |
| claude-haiku-4-5 | 0.000080 | 0.000400 |
| claude-sonnet-4-6 | 0.000300 | 0.001500 |
| claude-opus-4-7 | 0.001500 | 0.007500 |

Unknown models fall back to Haiku rates (conservative overestimate).

---

## Budget Status API

### `GET /api/v1/subscriptions/me`

Returns the full budget picture for the authenticated user. Backed by `get_budget_status(uid)` in `subscription_service.py`.

```json
{
  "plan_id": "free_trial",
  "plan_name": "Free Trial",
  "token_budget_cents": 20.0,
  "spent_cents": 1.42,
  "remaining_cents": 18.58,
  "pct_used": 7.1,
  "is_limited": false,
  "coupon_credits_cents": 0.0,
  "coupon_bonus_messages": 0,
  "lifetime_messages_used": 2,
  "lifetime_messages_limit": 6,
  "messages_remaining": 4
}
```

`lifetime_messages_*` fields are `null` for paid plans.

---

## Logs

All budget events emit structured JSON logs (production) or colored plaintext (development). Logger name: `app.services.subscription_service`.

### `budget.usage_recorded` — INFO

Emitted after every successful `record_usage` call.

```json
{
  "message": "budget.usage_recorded",
  "uid": "firebase-uid-abc",
  "interaction": "spark",
  "model": "gpt-4.1-nano",
  "in_tok": 210,
  "out_tok": 390,
  "call_cost_cents": 0.0000177,
  "spent_cents": 1.4200,
  "budget_cents": 20.0,
  "remaining_cents": 18.58,
  "pct_used": 7.1,
  "plan": "free_trial"
}
```

### `budget.check_ok` — DEBUG

Emitted when `check_budget` allows a request.

```json
{
  "message": "budget.check_ok",
  "uid": "firebase-uid-abc",
  "context": "ai",
  "plan": "free_trial",
  "spent_cents": 1.42,
  "budget_cents": 20.0,
  "remaining_cents": 18.58,
  "pct_used": 7.1
}
```

### `budget.blocked` — WARNING

Emitted when `check_budget` blocks a request.

```json
{
  "message": "budget.blocked",
  "uid": "firebase-uid-abc",
  "reason": "budget_exhausted",
  "plan": "free_trial",
  "spent_cents": 20.01,
  "budget_cents": 20.0
}
```

For free trial message exhaustion:
```json
{
  "message": "budget.blocked",
  "uid": "firebase-uid-abc",
  "reason": "free_trial_exhausted",
  "messages_used": 6,
  "messages_limit": 6
}
```

---

## How Admins Can Adjust Limits

1. **Change plan budget** — `PATCH /api/v1/admin/plans/{plan_id}` with `{"token_budget_cents": 500.0}`
2. **Issue coupon credits** — `POST /api/v1/coupons/admin` with `credit_cents` and optional `duration_days`
3. **Switch AI model** — `PATCH /api/v1/admin/ai-config` to a cheaper model; future calls immediately use the new model and lower cost per token
4. **View usage breakdown** — `GET /api/v1/admin/usage` shows token usage and cost by model + daily message volume

---

## Interaction Type Reference

| `interaction_type` | Endpoint / trigger | Default model |
|---|---|---|
| `spark` | `POST /spark` | gpt-4.1-nano |
| `journey` | `POST /explore` | gpt-4o-mini |
| `step_content` | `GET /journeys/.../content` (cache miss) + background warm | gpt-4o-mini |
| `daily_chat` | `POST /chat/stream` | gpt-4.1-nano |
| `daily_spark` | `GET /knowledge/spark` | gpt-4.1-nano |
| `knowledge_extraction` | Background after chat | gpt-4.1-nano |
| `mind_signature` | `POST /mind-signature/generate` | gpt-4o-mini |
