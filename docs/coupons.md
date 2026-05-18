# Coupon & Redemption System

## Overview

The coupon system lets admins create promo codes that give users extra AI token budget, bonus chat messages, or both. Credits stack on top of the user's existing plan budget and are checked in real-time on every AI call.

---

## How It Works

```
User enters code → validate → record redemption → credits added to budget check
                                                         ↓
                               check_budget() = plan_budget + active coupon credits
```

Coupon credits are **additive** — they never replace a plan, they top it up. A free trial user with a coupon still has 6 chat messages *plus* whatever `bonus_messages` the coupon grants. A paid user's token budget grows by the coupon's `credit_cents`.

Credits expire per-redemption (not globally) — if a coupon has `duration_days = 30`, each user's credit expires 30 days after *they* redeem it, not 30 days after the coupon was created.

---

## Database Schema

### `coupons`

| Column | Type | Description |
|---|---|---|
| `code` | `text` PK | Uppercase code users enter (e.g. `LAUNCH50`) |
| `description` | `text` | Human-readable label shown to user on success |
| `credit_cents` | `float` | Extra AI token budget in cents added to user's budget |
| `bonus_messages` | `int` | Extra chat messages added to free trial message limit |
| `plan_override` | `text` FK → `plan_configs` | Reserved for future: grant a temp plan upgrade |
| `duration_days` | `int` | How long the credit lasts after redemption. `null` = permanent |
| `max_redemptions` | `int` | Total uses allowed across all users. `null` = unlimited |
| `redemption_count` | `int` | Auto-incremented on each redemption |
| `expires_at` | `timestamptz` | Hard expiry date for the coupon itself. `null` = no expiry |
| `is_active` | `boolean` | Admin can deactivate without deleting |
| `created_at` | `timestamptz` | Auto-set on creation |

### `coupon_redemptions`

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | Row ID |
| `uid` | `text` FK → `users` | User who redeemed |
| `coupon_code` | `text` FK → `coupons` | Which coupon |
| `credit_applied_cents` | `float` | Snapshot of `credit_cents` at time of redemption |
| `bonus_messages_applied` | `int` | Snapshot of `bonus_messages` at time of redemption |
| `credit_expires_at` | `timestamptz` | When this user's credit expires. `null` = permanent |
| `redeemed_at` | `timestamptz` | When the user redeemed |

**Unique constraint:** `(uid, coupon_code)` — one redemption per user per coupon.

**Why snapshot at redemption?** If an admin later edits the coupon's credit value, existing redemptions are unaffected. Each user keeps exactly what they got when they redeemed.

---

## API Endpoints

### User-facing

#### `POST /api/v1/coupons/apply`

Apply a coupon code. Requires authentication.

**Request body:**
```json
{ "code": "LAUNCH50" }
```

**Success response `200`:**
```json
{
  "code": "LAUNCH50",
  "description": "Launch promo — 50 cents AI credit",
  "credit_cents": 50.0,
  "bonus_messages": 0,
  "plan_override": null,
  "credit_expires_at": "2026-06-18T00:00:00+00:00"
}
```

**Error responses:**

| Status | `detail` | Reason |
|---|---|---|
| `400` | `"Coupon not found."` | Code doesn't exist |
| `400` | `"This coupon is no longer active."` | Admin deactivated it |
| `400` | `"This coupon has expired."` | Past `expires_at` |
| `400` | `"This coupon has reached its maximum number of uses."` | `redemption_count >= max_redemptions` |
| `400` | `"You have already used this coupon."` | User already redeemed this code |
| `401` | — | Not authenticated |

---

### Admin endpoints

All admin endpoints require a signed-in user with `users.is_admin = true`. Returns `403` otherwise.

---

#### `GET /api/v1/coupons/admin`

List all coupons.

**Response:**
```json
{
  "coupons": [
    {
      "code": "LAUNCH50",
      "description": "Launch promo — 50 cents AI credit",
      "credit_cents": 50.0,
      "bonus_messages": 0,
      "plan_override": null,
      "duration_days": 30,
      "max_redemptions": 500,
      "redemption_count": 12,
      "expires_at": "2026-07-01T00:00:00+00:00",
      "is_active": true,
      "created_at": "2026-05-18T10:00:00+00:00"
    }
  ]
}
```

---

#### `POST /api/v1/coupons/admin`

Create a new coupon.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | ✅ | Uppercase code. Auto-uppercased if lowercase. |
| `description` | `string` | ✅ | Shown to user on redemption |
| `credit_cents` | `float` | — | Default `0`. AI budget boost in cents. |
| `bonus_messages` | `int` | — | Default `0`. Extra chat messages for free trial users. |
| `plan_override` | `string` | — | Default `null`. Reserved. |
| `duration_days` | `int` | — | Default `null` (permanent). Days credit lasts after each redemption. |
| `max_redemptions` | `int` | — | Default `null` (unlimited). |
| `expires_at` | `datetime` | — | Default `null`. ISO 8601 string. |

**Example — 50-cent credit, 30-day validity, max 500 uses, expires July 1:**
```json
{
  "code": "LAUNCH50",
  "description": "Launch promo — 50 cents AI credit",
  "credit_cents": 50.0,
  "bonus_messages": 0,
  "duration_days": 30,
  "max_redemptions": 500,
  "expires_at": "2026-07-01T00:00:00Z"
}
```

**Example — 20 bonus chat messages, permanent, unlimited:**
```json
{
  "code": "FRIEND20",
  "description": "Extended free trial — 20 extra messages",
  "credit_cents": 0,
  "bonus_messages": 20
}
```

**Example — both credit and messages, one-time use:**
```json
{
  "code": "VIP",
  "description": "VIP access — 200 cents credit + 50 messages",
  "credit_cents": 200.0,
  "bonus_messages": 50,
  "max_redemptions": 1
}
```

**Response:** Full coupon object (same shape as list).

**Error `400`:** Code already exists or DB constraint violation.

---

#### `PATCH /api/v1/coupons/admin/{code}`

Update a coupon. Only provided fields are updated.

**Updatable fields:** `description`, `credit_cents`, `bonus_messages`, `max_redemptions`, `expires_at`, `is_active`

**Deactivate a coupon:**
```json
{ "is_active": false }
```

**Reactivate:**
```json
{ "is_active": true }
```

**Extend expiry:**
```json
{ "expires_at": "2026-12-31T23:59:59Z" }
```

**Response:** Updated coupon object.

**Note:** Editing `credit_cents` or `bonus_messages` does NOT retroactively change existing redemptions. The snapshots in `coupon_redemptions` remain unchanged.

---

#### `GET /api/v1/coupons/admin/{code}/redemptions`

See every user who redeemed a specific coupon.

**Response:**
```json
{
  "redemptions": [
    {
      "id": "uuid",
      "uid": "firebase-uid",
      "coupon_code": "LAUNCH50",
      "display_name": "Alice Smith",
      "email": "alice@example.com",
      "credit_applied_cents": 50.0,
      "bonus_messages_applied": 0,
      "credit_expires_at": "2026-06-18T10:00:00+00:00",
      "redeemed_at": "2026-05-18T10:00:00+00:00"
    }
  ]
}
```

---

## How Credits Are Applied

### Token budget check

`GET /api/v1/subscriptions/me` returns:

```json
{
  "plan": { "plan_id": "free_trial", "token_budget_cents": 20.0, ... },
  "usage": { "estimated_cost_cents": 8.4, ... },
  "coupon_extras": {
    "extra_credits_cents": 50.0,
    "bonus_messages": 0
  },
  "total_budget_cents": 70.0,
  "lifetime_message_count": 3,
  "lifetime_message_limit": 6
}
```

`total_budget_cents = plan.token_budget_cents + coupon_extras.extra_credits_cents`

When `estimated_cost_cents >= total_budget_cents` → API returns `402 budget_exhausted`.

### Message limit (free trial only)

`lifetime_message_limit = plan.lifetime_message_limit + coupon_extras.bonus_messages`

When `lifetime_message_count >= lifetime_message_limit` → API returns `402 free_trial_exhausted`.

### What consumes budget

| Action | Records usage? | Checks budget? |
|---|---|---|
| Chat message (`/chat/stream`) | ✅ | ✅ (message count for free trial) |
| Explore / generate journey | ✅ | ✅ (token budget) |
| Expand step content (cache miss) | ✅ | ✅ (token budget) |
| Expand step content (cache hit) | ❌ | ❌ (free) |
| Background step warming | ✅ (charged to journey creator) | ❌ |
| Daily spark | ❌ | ❌ |
| Knowledge extraction | ❌ | ❌ |

---

## Admin Panel

Navigate to `/admin` → **Coupons** tab.

**Create form fields:**

| Field | What to enter |
|---|---|
| Code | Short uppercase string, e.g. `SUMMER25` |
| Description | User-visible label shown on redemption success |
| AI Credit (cents) | e.g. `50` = 50 cents = $0.50 extra AI budget |
| Bonus Chat Messages | e.g. `20` = 20 extra messages for free trial users |
| Credit valid for (days) | e.g. `30` = expires 30 days after each user redeems. Leave blank = permanent |
| Max redemptions | Total uses before code stops working. Leave blank = unlimited |
| Expires at | Hard date the code stops accepting new redemptions |

**Coupon list** shows each coupon with:
- Color-coded badges for credit amount, bonus messages, validity period
- Use count (`12/500` or just `12` if unlimited)
- Expiry date
- Toggle switch to activate / deactivate instantly

---

## Promotion Playbook

### Product Hunt launch
```json
{
  "code": "PRODUCTHUNT",
  "description": "Product Hunt special — 3 months of extra AI credit",
  "credit_cents": 200.0,
  "bonus_messages": 50,
  "duration_days": 90,
  "max_redemptions": 1000,
  "expires_at": "2026-06-01T00:00:00Z"
}
```

### Hand-pick influencer / beta tester
```json
{
  "code": "BETAVIP2026",
  "description": "Beta tester access",
  "credit_cents": 500.0,
  "bonus_messages": 100,
  "max_redemptions": 50
}
```

### Conference giveaway (one-time QR code)
```json
{
  "code": "DEVCONF26",
  "description": "DevConf 2026 attendee gift",
  "credit_cents": 100.0,
  "bonus_messages": 0,
  "duration_days": 60,
  "max_redemptions": 300,
  "expires_at": "2026-08-01T00:00:00Z"
}
```

### Referral reward (one use per person)
Create a unique code per user and set `max_redemptions: 1`. Since `(uid, coupon_code)` is unique, the referrer can't use their own code twice even if you set max_redemptions higher.

---

## Cost Reference

Approximate cost per action with current default models:

| Action | Model | Approx cost |
|---|---|---|
| 1 chat message (short) | gpt-4.1-nano | ~0.003 cents |
| 1 chat message (with history) | gpt-4.1-nano | ~0.01–0.05 cents |
| 1 step content generation | gpt-4o-mini | ~0.04 cents |
| 1 journey generation | gpt-4o-mini | ~0.10 cents |

So `credit_cents = 50` ≈ 1,250 step expansions or 500 journey generations or ~5,000 short chat messages.

---

## Caveats

- **Deactivating** a coupon stops new redemptions but does NOT revoke credits already granted to users who already redeemed it.
- **Editing credit value** after creation does not affect past redemptions (snapshot pattern).
- `plan_override` field exists in the schema but is not yet enforced in `check_budget()` — reserved for future "give user a temporary paid plan" feature.
- Budget tracking uses token count estimates (`len(text) // 4`) for non-streaming calls, accurate to ~15%. This is a guardrail, not billing-grade accounting.
