# Payment Gateway Backend Plan
## Stripe (US/Global) + Razorpay (India) — Admin-Driven Provisioning

---

## Current State

| Item | Status |
|------|--------|
| Stripe checkout (hosted redirect) | ✅ Working |
| Razorpay order flow (one-time) | ✅ Working |
| Geo-routing IN → Razorpay, else → Stripe | ✅ Working |
| Stripe webhook handler | ✅ Working |
| Razorpay webhook handler (`payment.captured`) | ✅ Working |
| Admin can set `stripe_price_id` manually | ✅ Working |
| Admin can set `base_price_inr_paise` | ❌ Missing from `PlanUpdate` model |
| Admin can set `razorpay_plan_id` | ❌ Missing from `PlanUpdate` model |
| Auto-provision Stripe Product+Price via API | ❌ Not built |
| Auto-provision Razorpay Plan via API | ❌ Not built |
| Admin can create new plan tiers | ❌ No `POST /admin/plans` endpoint |
| Razorpay recurring subscriptions | ❌ Currently one-time orders only |
| Webhook: `subscription.charged` (Razorpay) | ❌ Not handled |

---

## Database Changes

### Migration: `migrations/add_gateway_provisioning.sql` (new file)

```sql
-- Track Stripe Product ID so we can create new Prices without duplicating Products
ALTER TABLE plan_configs
  ADD COLUMN IF NOT EXISTS stripe_product_id TEXT;
```

Run **after** `add_multi_gateway.sql` (which already added `base_price_inr_paise` and `razorpay_plan_id`).

### Final `plan_configs` column set

| Column | Type | Notes |
|--------|------|-------|
| `plan_id` | TEXT PK | slug, e.g. `individual` |
| `name` | TEXT | display name |
| `base_price_cents` | INTEGER | USD price in cents |
| `base_price_inr_paise` | INTEGER | INR price in paise (100 paise = ₹1) |
| `token_budget_cents` | INTEGER | AI cost budget in micro-cents |
| `lifetime_message_limit` | INTEGER | free trial only |
| `max_seats` | INTEGER | default 1 |
| `is_active` | BOOLEAN | show/hide on pricing page |
| `stripe_price_id` | TEXT | e.g. `price_1Abc...` — set by provisioning |
| `stripe_product_id` | TEXT | e.g. `prod_1Abc...` — set by provisioning |
| `razorpay_plan_id` | TEXT | e.g. `plan_Xxx...` — set by provisioning |
| `updated_at` | TIMESTAMP | auto-updated |

---

## Files to Create / Modify

### 1. `app/services/stripe_service.py` — NEW FILE

Handles all Stripe Product + Price creation. The admin panel calls this; checkout continues to use the stored `stripe_price_id`.

```python
def provision_stripe_plan(plan_id: str, name: str, amount_cents: int) -> dict:
    """
    Idempotent. Searches for existing Stripe Product by plan_id metadata.
    Creates Product if not found. Always creates a new Price (prices are immutable).
    Returns {"stripe_product_id": "...", "stripe_price_id": "..."}
    """
```

Key behaviour:
- Search `stripe.Product.search(query=f'metadata["plan_id"]:"{plan_id}"')` before creating
- Create `stripe.Price` with `recurring={"interval": "month"}`
- Raises `HTTPException(503)` if `STRIPE_SECRET_KEY` not set
- Raises `HTTPException(400)` if `base_price_cents == 0` (free plans don't need Stripe)

---

### 2. `app/services/razorpay_service.py` — ADD TWO FUNCTIONS

**Function A: `provision_razorpay_plan`**
```python
def provision_razorpay_plan(plan_id: str, name: str, amount_paise: int) -> str:
    """
    Creates a Razorpay Plan. Returns razorpay plan_id ("plan_XXXX").
    Called once per plan tier from the admin panel.
    """
    # client.plan.create({period, interval, item: {name, amount, currency: "INR"}, notes: {plan_id}})
```

**Function B: `create_razorpay_subscription`**
```python
def create_razorpay_subscription(razorpay_plan_id: str, uid: str, plan_id: str) -> dict:
    """
    Creates a Razorpay Subscription for a user linked to the plan.
    total_count=12 (12 months). Returns subscription dict with id ("sub_XXXX").
    Called at checkout time (replaces create_razorpay_order for recurring plans).
    """
    # client.subscription.create({plan_id, total_count: 12, notes: {uid, plan_id}})
```

> **Note on `total_count`**: Set to `12` (12-month cycle). Razorpay's "indefinite" support
> via `total_count=0` is unreliable across plan types. After 12 months the user will
> need to re-subscribe — acceptable for v1, can be changed later.

---

### 3. `app/api/v1/endpoints/admin.py` — THREE CHANGES

**Change A: Fix `PlanUpdate` model** (line ~69)

Add the two missing fields so INR price and Razorpay plan ID become settable:

```python
class PlanUpdate(BaseModel):
    name: Optional[str] = None
    base_price_cents: Optional[int] = None
    base_price_inr_paise: Optional[int] = None    # WAS MISSING
    token_budget_cents: Optional[int] = None
    lifetime_message_limit: Optional[int] = None
    max_seats: Optional[int] = None
    is_active: Optional[bool] = None
    stripe_price_id: Optional[str] = None
    razorpay_plan_id: Optional[str] = None         # WAS MISSING
```

**Change B: Add `POST /plans`** — create new plan tier

```python
class PlanCreate(BaseModel):
    plan_id: str                          # slug, e.g. "individual_pro"
    name: str
    base_price_cents: int
    base_price_inr_paise: Optional[int] = None
    token_budget_cents: int
    lifetime_message_limit: Optional[int] = None
    max_seats: int = 1

@router.post("/plans")
async def create_plan(body: PlanCreate, _uid: str = Depends(get_admin_user)):
    # INSERT INTO plan_configs ... ON CONFLICT DO NOTHING ... RETURNING *
```

**Change C: Add `POST /plans/{plan_id}/provision`** — auto-provision in gateway

```python
class ProvisionRequest(BaseModel):
    gateway: str  # "stripe" | "razorpay" | "both"

@router.post("/plans/{plan_id}/provision")
async def provision_plan(plan_id: str, body: ProvisionRequest, _uid: str = Depends(get_admin_user)):
    """
    Calls Stripe/Razorpay APIs to create Price or Plan objects, 
    then stores the resulting IDs back in plan_configs.
    Returns {"provisioned": {"stripe": {...}, "razorpay": {...}}}
    """
```

Logic:
1. Fetch plan from DB — 404 if not found
2. If `gateway in ("stripe", "both")`: call `provision_stripe_plan()`, UPDATE `stripe_price_id` + `stripe_product_id`
3. If `gateway in ("razorpay", "both")`: validate `base_price_inr_paise` is set, call `provision_razorpay_plan()`, UPDATE `razorpay_plan_id`
4. Return all newly created IDs

---

### 4. `app/api/v1/endpoints/subscriptions.py` — TWO CHANGES

**Change A: Switch `_razorpay_checkout()` to use Subscriptions when provisioned**

```python
def _razorpay_checkout(uid: str, plan_id: str, row) -> dict:
    razorpay_plan_id = row.get("razorpay_plan_id")
    amount_paise = row.get("base_price_inr_paise")

    if not amount_paise:
        raise HTTPException(503, "INR price not configured for this plan")

    if razorpay_plan_id:
        # Recurring subscription (proper billing)
        sub = create_razorpay_subscription(razorpay_plan_id, uid, plan_id)
        return {
            "gateway": "razorpay",
            "checkout_type": "subscription",   # frontend keys on this
            "subscription_id": sub["id"],
            "amount": amount_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
        }
    else:
        # Fallback: one-time order (until Razorpay plan is provisioned)
        order = create_razorpay_order(amount_paise, plan_id, uid)
        return {
            "gateway": "razorpay",
            "checkout_type": "order",          # frontend falls back to order flow
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.RAZORPAY_KEY_ID,
        }
```

**Change B: Handle `subscription.charged` in `razorpay_webhook()`**

```python
elif event_type == "subscription.charged":
    subscription = event["payload"]["subscription"]["entity"]
    notes = subscription.get("notes", {})
    uid = notes.get("uid")
    plan_id = notes.get("plan_id")
    payment = event["payload"].get("payment", {}).get("entity", {})
    if uid and plan_id:
        upsert_subscription_from_stripe(
            uid=uid,
            plan_id=plan_id,
            payment_gateway="razorpay",
            razorpay_payment_id=payment.get("id"),
        )
```

> `payment.captured` still fires for orders. Both branches stay in the handler.

---

## API Summary After Changes

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/admin/plans` | admin | list all plans |
| POST | `/admin/plans` | admin | create new plan |
| PATCH | `/admin/plans/{plan_id}` | admin | edit plan fields |
| POST | `/admin/plans/{plan_id}/provision` | admin | auto-create in Stripe/Razorpay |
| GET | `/subscriptions/plans` | public | list active plans for pricing page |
| POST | `/subscriptions/checkout` | user | initiate checkout |
| POST | `/subscriptions/razorpay/verify` | user | verify order payment (legacy) |
| POST | `/subscriptions/razorpay/webhook` | public | Razorpay webhook receiver |
| POST | `/subscriptions/webhook` | public | Stripe webhook receiver |

---

## Environment Variables Required

```env
# Stripe
STRIPE_SECRET_KEY=sk_live_...       # required for provisioning + checkout
STRIPE_PUBLISHABLE_KEY=pk_live_...  # sent to frontend
STRIPE_WEBHOOK_SECRET=whsec_...     # required for webhook verification

# Razorpay
RAZORPAY_KEY_ID=rzp_live_...        # required for provisioning + checkout
RAZORPAY_KEY_SECRET=...             # required for provisioning + signature verification
RAZORPAY_WEBHOOK_SECRET=...         # required for webhook verification
```

---

## Implementation Order

1. Run `migrations/add_gateway_provisioning.sql`
2. Fix `PlanUpdate` in `admin.py` (unblocks INR price — quick win)
3. Create `app/services/stripe_service.py`
4. Add functions to `app/services/razorpay_service.py`
5. Add `POST /plans` and `POST /plans/{id}/provision` to `admin.py`
6. Update `_razorpay_checkout()` and webhook in `subscriptions.py`
7. Frontend changes (see UI plan)
