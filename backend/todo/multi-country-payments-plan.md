# Multi-Country Payments Plan
## Stripe (Global) + Razorpay (India)

### Current State

| Layer | What exists |
|---|---|
| Backend | Single Stripe-only flow: `POST /subscriptions/checkout` → Stripe Checkout redirect |
| Webhook | `POST /subscriptions/webhook` handles 3 Stripe events |
| DB | `plan_configs.stripe_price_id` (single price column, USD only) |
| Frontend | Hardcoded USD, always calls checkout endpoint, redirects to Stripe |
| Country awareness | None — no detection, no routing |

### Target State

- **India users** → Razorpay inline checkout (INR pricing, UPI/cards/netbanking)
- **All other countries** → Stripe Checkout redirect (USD/local pricing via Stripe)
- Single `/subscriptions/checkout` endpoint routes based on detected country
- Single `subscriptions` DB table extended with gateway column

---

## Phase 1 — Backend Foundations (DB + Config + Country Detection)

**Goal:** Everything the later phases depend on. No user-visible change yet.

### 1.1 — New config vars

Add to `app/core/config.py`:
```python
RAZORPAY_KEY_ID: str = ""
RAZORPAY_KEY_SECRET: str = ""
RAZORPAY_WEBHOOK_SECRET: str = ""
```

Add to `.env` (test values — never commit to git):
```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...   # set after creating webhook in Razorpay dashboard
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 1.2 — DB migration

Run `migrations/add_multi_gateway.sql` (create this file):

```sql
-- Add gateway tracking to subscriptions
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS payment_gateway TEXT NOT NULL DEFAULT 'stripe'
    CHECK (payment_gateway IN ('stripe', 'razorpay')),
  ADD COLUMN IF NOT EXISTS razorpay_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS razorpay_customer_id TEXT;

-- Add INR pricing + Razorpay plan ID to plan_configs
ALTER TABLE plan_configs
  ADD COLUMN IF NOT EXISTS base_price_inr_paise  INTEGER,   -- price in paise (1 INR = 100 paise)
  ADD COLUMN IF NOT EXISTS razorpay_plan_id      TEXT;      -- Razorpay Plan ID (plan_XXXX)

-- Seed INR prices (adjust amounts as needed)
UPDATE plan_configs SET base_price_inr_paise = 0      WHERE plan_id = 'free_trial';
UPDATE plan_configs SET base_price_inr_paise = 79900  WHERE plan_id = 'individual';  -- ₹799/month
```

### 1.3 — Country detection endpoint

Create `app/api/v1/endpoints/geo.py`:

```python
from fastapi import APIRouter, Request
import httpx

router = APIRouter()

@router.get("/country")
async def get_country(request: Request):
    """Detect user country from IP. Returns ISO 3166-1 alpha-2 code."""
    # Use request.headers for X-Forwarded-For (behind reverse proxy/Supabase)
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    
    # Option A: Free tier of ip-api.com (no key needed, 45 req/min)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?fields=countryCode")
            if r.status_code == 200:
                return {"country": r.json().get("countryCode", "US")}
    except Exception:
        pass
    
    # Fallback: check Accept-Language header
    lang = request.headers.get("accept-language", "en-US")
    # Crude but workable fallback
    return {"country": "US"}
```

Register in `app/api/v1/router.py`:
```python
from app.api.v1.endpoints import geo
api_router.include_router(geo.router, prefix="/geo", tags=["geo"])
```

**Alternative (better for production):** Use Cloudflare's `CF-IPCountry` header if behind Cloudflare — zero latency, no external call.

### 1.4 — Install Razorpay SDK

```bash
pip install razorpay
# Add to requirements.txt / pyproject.toml
```

---

## Phase 2 — Razorpay Backend Integration

**Goal:** Full Razorpay order creation and webhook processing.

### 2.1 — Razorpay service

Create `app/services/razorpay_service.py`:

```python
import hashlib
import hmac
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_razorpay_client():
    import razorpay
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount_paise: int, plan_id: str, uid: str) -> dict:
    """Create a Razorpay order. Returns order dict with id, amount, currency."""
    client = get_razorpay_client()
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"ecalt_{plan_id}_{uid[:8]}",
        "notes": {"uid": uid, "plan_id": plan_id},
    })
    return order

def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature (client-side flow)."""
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 2.2 — Extend subscriptions endpoint

Modify `app/api/v1/endpoints/subscriptions.py`:

**2.2a — Unified checkout endpoint with gateway routing**

Replace the existing `create_checkout()` with a router-aware version:

```python
from app.services.razorpay_service import create_razorpay_order

class CheckoutRequest(BaseModel):
    plan_id: str
    country: str = "US"   # frontend sends detected country

@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, uid: str = Depends(get_required_user)):
    # Validate plan exists
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stripe_price_id, base_price_inr_paise, razorpay_plan_id "
                "FROM plan_configs WHERE plan_id = %s AND is_active = true",
                (body.plan_id,)
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Route by country
    if body.country == "IN":
        return _razorpay_checkout(uid, body.plan_id, row)
    else:
        return _stripe_checkout(uid, body.plan_id, row)

def _stripe_checkout(uid, plan_id, row):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")
    stripe_price_id = row.get("stripe_price_id")
    if not stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe price not configured for this plan")
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/learn?upgraded=true",
        cancel_url=f"{settings.FRONTEND_URL}/pricing",
        client_reference_id=uid,
    )
    return {"gateway": "stripe", "checkout_url": session.url}

def _razorpay_checkout(uid, plan_id, row):
    if not settings.RAZORPAY_KEY_ID:
        raise HTTPException(status_code=503, detail="Razorpay not configured")
    amount_paise = row.get("base_price_inr_paise")
    if not amount_paise:
        raise HTTPException(status_code=503, detail="INR price not configured for this plan")
    order = create_razorpay_order(amount_paise, plan_id, uid)
    return {
        "gateway": "razorpay",
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": settings.RAZORPAY_KEY_ID,
    }
```

**2.2b — Razorpay payment verification endpoint**

After client completes Razorpay checkout, they POST the payment result here:

```python
from app.services.razorpay_service import verify_razorpay_signature

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str

@router.post("/razorpay/verify")
async def verify_razorpay_payment(
    body: RazorpayVerifyRequest,
    uid: str = Depends(get_required_user)
):
    if not verify_razorpay_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    upsert_subscription_from_stripe(     # reuse existing upsert — just pass razorpay IDs
        uid=uid,
        plan_id=body.plan_id,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        status="active",
        razorpay_payment_id=body.razorpay_payment_id,
        payment_gateway="razorpay",
    )
    return {"success": True}
```

**2.2c — Extend `upsert_subscription_from_stripe` signature**

In `subscription_service.py`, update the function to accept optional gateway params:

```python
def upsert_subscription_from_stripe(
    uid, plan_id, stripe_subscription_id=None, stripe_customer_id=None,
    status="active", period_start=None, period_end=None,
    payment_gateway="stripe", razorpay_payment_id=None,
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO subscriptions
                  (uid, plan_id, stripe_subscription_id, stripe_customer_id, status,
                   current_period_start, current_period_end, payment_gateway,
                   razorpay_subscription_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    plan_id                  = EXCLUDED.plan_id,
                    stripe_subscription_id   = COALESCE(EXCLUDED.stripe_subscription_id, subscriptions.stripe_subscription_id),
                    stripe_customer_id       = COALESCE(EXCLUDED.stripe_customer_id, subscriptions.stripe_customer_id),
                    status                   = EXCLUDED.status,
                    current_period_start     = EXCLUDED.current_period_start,
                    current_period_end       = EXCLUDED.current_period_end,
                    payment_gateway          = EXCLUDED.payment_gateway,
                    razorpay_subscription_id = COALESCE(EXCLUDED.razorpay_subscription_id, subscriptions.razorpay_subscription_id)
                """,
                (uid, plan_id, stripe_subscription_id, stripe_customer_id,
                 status, period_start, period_end, payment_gateway, razorpay_payment_id),
            )
```

### 2.3 — Razorpay webhook

```python
@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay webhook not configured")

    payload = await request.body()
    sig = request.headers.get("x-razorpay-signature", "")

    from app.services.razorpay_service import verify_webhook_signature
    if not verify_webhook_signature(payload, sig):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    event = json.loads(payload)
    event_type = event.get("event")

    if event_type == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        notes = payment.get("notes", {})
        uid = notes.get("uid")
        plan_id = notes.get("plan_id")
        if uid and plan_id:
            upsert_subscription_from_stripe(
                uid=uid, plan_id=plan_id, status="active",
                payment_gateway="razorpay",
                razorpay_payment_id=payment["id"],
            )

    elif event_type == "payment.failed":
        # Log for support; no subscription change needed
        pass

    return {"received": True}
```

### 2.4 — Publish Razorpay public key to frontend

Add to the `/subscriptions/plans` response (or a new `/subscriptions/config` endpoint):

```python
@router.get("/config")
async def get_payment_config():
    return {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    }
```

---

## Phase 3 — Frontend Integration

See `todo/multi-country-payments-ui.md` for all UI changes in detail.

Summary of what Phase 3 delivers:
- Country detection on app load → stored in context
- Pricing page shows INR for India, USD otherwise
- "Get started" button routes to Razorpay inline checkout (India) or Stripe redirect (global)
- Razorpay success → POST to `/subscriptions/razorpay/verify` → refresh subscription
- Stripe success → existing `/learn?upgraded=true` redirect flow (unchanged)

---

## Phase 4 — Testing

### Razorpay test scenarios

| Scenario | How to test |
|---|---|
| UPI success | Use UPI ID `success@razorpay` in test checkout |
| Card success | 4111 1111 1111 1111, any future expiry, any CVV |
| Card failure | 4000 0000 0000 0002 |
| Netbanking | Select any bank → "Success" |
| Webhook delivery | Razorpay Dashboard → Webhooks → "Test webhook" |

### Stripe test scenarios (regression — must still work)

| Scenario | Card |
|---|---|
| Success | 4242 4242 4242 4242 |
| Decline | 4000 0000 0000 9995 |

### Country routing test

Force country in frontend by temporarily hardcoding `country = "IN"` in the checkout call,
verify Razorpay flow fires. Switch to `"US"`, verify Stripe fires.

### DB verification after each test

```sql
SELECT uid, plan_id, status, payment_gateway, razorpay_subscription_id, stripe_subscription_id
FROM subscriptions ORDER BY created_at DESC LIMIT 5;
```

---

## Phase 5 — Production Readiness

- [ ] Switch to a proper IP geo service (Cloudflare `CF-IPCountry` header, or MaxMind GeoLite2)
- [ ] Replace Razorpay one-time payment with **Razorpay Subscriptions API** for recurring billing
- [ ] Add `razorpay_subscription_id` to renewals webhook handler
- [ ] Add INR prices for all plans in `plan_configs`
- [ ] Set live Razorpay keys and webhook secret in production `.env`
- [ ] Set Razorpay webhook URL in dashboard: `https://api.ecalt.app/api/v1/subscriptions/razorpay/webhook`
- [ ] Monitor failed payments via Razorpay Dashboard → Payments

---

## Files to Create/Modify Summary

| File | Action |
|---|---|
| `app/core/config.py` | Add 3 Razorpay vars |
| `app/services/razorpay_service.py` | Create (new) |
| `app/api/v1/endpoints/subscriptions.py` | Extend checkout, add verify + webhook endpoints |
| `app/api/v1/endpoints/geo.py` | Create (new) |
| `app/api/v1/router.py` | Register geo router |
| `app/services/subscription_service.py` | Extend upsert signature |
| `migrations/add_multi_gateway.sql` | Create (new) |
| `requirements.txt` | Add `razorpay` |
| `.env` | Add Razorpay test keys (never commit) |
| `frontend/src/...` | See `multi-country-payments-ui.md` |
