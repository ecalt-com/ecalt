# Payment Security Audit — ECALT
**Scope:** Stripe + Razorpay payment stack  
**Files reviewed:**
- `backend/app/api/v1/endpoints/subscriptions.py`
- `backend/app/services/razorpay_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/core/config.py`
- `frontend/src/lib/razorpay.ts`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/lib/PaymentConfig.tsx`
- `frontend/src/pages/Welcome.tsx`

---

## Finding Summary

| ID  | Severity | Location | Title |
|-----|----------|----------|-------|
| C1  | **CRITICAL** | `Pricing.tsx:97` | Subscription flow never calls `/razorpay/verify` — DB never updated |
| C2  | **CRITICAL** | `subscriptions.py:291` | Verify endpoint does not confirm payment is captured |
| H1  | **HIGH** | `subscriptions.py:182` | Client-controlled `country` field enables price manipulation |
| H2  | **HIGH** | `subscriptions.py:308` | Unguarded JSON parse in webhook causes 500 retry loop |
| H3  | **HIGH** | `subscriptions.py:406` | `customer.subscription.updated` silently no-ops if row doesn't exist |
| M1  | **MEDIUM** | `subscriptions.py:185` | No rate limiting on `POST /checkout` |
| M2  | **MEDIUM** | `subscriptions.py:278` | Old valid signatures can be replayed to re-activate subscription |
| M3  | **MEDIUM** | `razorpay_service.py:72` | No idempotency keys on order/subscription creation |
| M4  | **MEDIUM** | `razorpay.ts:16` | TypeScript interfaces model only order flow — subscription types missing |
| M5  | **MEDIUM** | `subscriptions.py:431` | Stripe deleted-event stores raw `sub.status` string |
| M6  | **MEDIUM** | `config.py:43` | `NOTIFICATION_SIGNING_SECRET` has hardcoded default |
| L1  | LOW | `razorpay.ts:1` | `loadRazorpayScript` race condition on concurrent calls |
| L2  | LOW | `Pricing.tsx:144` | Stripe `checkout_url` not validated before redirect |
| L3  | LOW | `subscriptions.py:123` | `session_id` in query string ends up in server access logs |
| L4  | LOW | `subscriptions.py:347` | Razorpay `subscription.cancelled` UPDATE silently no-ops |
| L5  | INFO | `subscriptions.py:350` | Redundant local `get_db` import inside webhook handler |

---

## Detailed Findings

---

### C1 — CRITICAL: Subscription flow never calls `/razorpay/verify` — DB never updated

**File:** `frontend/src/pages/Pricing.tsx:95–98`

**Description:**

When the backend returns `checkout_type: "subscription"` (i.e., a plan has a `razorpay_plan_id`), the Razorpay handler is:

```typescript
// CURRENT — BUG
options.handler = async () => { navigate('/welcome'); resolve() }
```

On successful payment, Razorpay calls this handler with
`{ razorpay_payment_id, razorpay_subscription_id, razorpay_signature }`.
The handler **ignores all three fields** and just navigates. No call to `/razorpay/verify` is made. The subscription row is never written to the database in the happy path.

The `order` flow (fallback) is correctly wired:
```typescript
options.handler = async (response: RazorpayResponse) => {
  await fetch('/api/v1/subscriptions/razorpay/verify', { ... })
}
```
but the subscription flow is not.

**Impact:**
- User pays but remains on `free_trial` until a `subscription.charged` webhook fires
- If webhooks are not configured, the user **never** gets access — money taken, service not delivered
- This is the root cause of the originally reported bug

**Fix:**

```typescript
// frontend/src/pages/Pricing.tsx

if (data.checkout_type === 'subscription') {
  options.subscription_id = data.subscription_id
  options.handler = async (response: {
    razorpay_payment_id: string
    razorpay_subscription_id: string
    razorpay_signature: string
  }) => {
    try {
      const verifyRes = await fetch('/api/v1/subscriptions/razorpay/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          razorpay_subscription_id: response.razorpay_subscription_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
          plan_id: planId,
        }),
      })
      if (verifyRes.ok) navigate('/welcome')
      else alert('Payment verification failed. Contact support with your payment ID.')
    } finally {
      resolve()
    }
  }
}
```

---

### C2 — CRITICAL: Verify endpoint does not confirm payment is actually captured

**File:** `backend/app/api/v1/endpoints/subscriptions.py:291`  
**File:** `backend/app/services/razorpay_service.py:84`

**Description:**

For the order flow, after passing `verify_razorpay_signature`, the subscription is immediately activated:

```python
# CURRENT — BUG
if not verify_razorpay_signature(ref_id, body.razorpay_payment_id, body.razorpay_signature):
    raise HTTPException(status_code=400, detail="Invalid payment signature")

upsert_subscription_from_stripe(uid=uid, plan_id=body.plan_id, ...)  # activates immediately
```

Razorpay signature verification only proves the response originated from Razorpay's checkout — it does **not** confirm the payment is in `captured` (settled) state. A payment in `authorized` state also produces a valid signature.

**Attack path:**
1. User initiates payment, receives `authorized` response with valid signature
2. Calls `POST /razorpay/verify` → signature passes → subscription activated
3. User initiates a bank chargeback / Razorpay auto-refund on the uncaptured payment
4. User has subscription access without paying

**Fix:**

```python
# backend/app/api/v1/endpoints/subscriptions.py

@router.post("/razorpay/verify")
def verify_razorpay_payment(body: RazorpayVerifyRequest, uid: str = Depends(get_required_user)):
    ref_id = body.razorpay_subscription_id or body.razorpay_order_id
    if not ref_id:
        raise HTTPException(status_code=400, detail="Provide razorpay_subscription_id or razorpay_order_id")

    from app.services.razorpay_service import verify_razorpay_signature, get_razorpay_client
    if not verify_razorpay_signature(ref_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # For order flow: confirm payment is actually captured before granting access
    if body.razorpay_order_id and not body.razorpay_subscription_id:
        try:
            client = get_razorpay_client()
            payment = client.payment.fetch(body.razorpay_payment_id)
            if payment.get("status") != "captured":
                raise HTTPException(status_code=402, detail="Payment not yet captured")
            fetched_order_id = payment.get("order_id")
            if fetched_order_id != body.razorpay_order_id:
                raise HTTPException(status_code=400, detail="Payment/order mismatch")
        except HTTPException:
            raise
        except Exception:
            logger.error("razorpay.verify.fetch_failed", extra={"payment_id": body.razorpay_payment_id})
            raise HTTPException(status_code=503, detail="Could not verify payment status with Razorpay")

    upsert_subscription_from_stripe(
        uid=uid,
        plan_id=body.plan_id,
        razorpay_subscription_id=body.razorpay_subscription_id,
        payment_gateway="razorpay",
    )
    return {"success": True}
```

---

### H1 — HIGH: Client-controlled `country` field enables price manipulation

**File:** `backend/app/api/v1/endpoints/subscriptions.py:182`

**Description:**

```python
class CheckoutRequest(BaseModel):
    plan_id: str
    country: str = "US"   # comes from client body
```

The `country` field from the **request body** determines whether the user pays in USD (Stripe) or INR via Razorpay. A US user can set `"country": "IN"` in their POST body and pay the cheaper INR price — `₹199` instead of `$9.99` for example. An Indian user could also claim `"country": "US"` to avoid Razorpay and use Stripe with a foreign card.

The frontend uses `useGeo()` to determine the real country, but the backend does not enforce this.

**Fix:**

Derive country server-side. The project already has a geo endpoint. Add a utility to resolve country from the request:

```python
# backend/app/api/v1/endpoints/subscriptions.py

from app.api.v1.endpoints.geo import detect_country  # or inline the IP lookup

@router.post("/checkout")
def create_checkout(body: CheckoutRequest, request: Request, uid: str = Depends(get_required_user)):
    # Override client-supplied country with server-side detection
    country = detect_country(request) or body.country

    with get_db() as conn:
        ...

    if country == "IN":
        return _razorpay_checkout(uid, body.plan_id, row)
    return _stripe_checkout(uid, body.plan_id, row)
```

If IP-based geo is not available, at minimum validate `country` against an allowlist and cross-check the payment method used against the country at webhook processing time.

---

### H2 — HIGH: Unguarded JSON parse in Razorpay webhook causes 500 retry loop

**File:** `backend/app/api/v1/endpoints/subscriptions.py:308–337`

**Description:**

```python
event = json.loads(payload)           # JSONDecodeError → 500
event_type = event.get("event")

if event_type == "payment.captured":
    payment = event["payload"]["payment"]["entity"]   # KeyError → 500
    notes = payment.get("notes", {})
    uid = notes.get("uid")
```

None of this is wrapped in try/except. If Razorpay delivers a malformed body or a new event shape, the endpoint returns HTTP 500. Razorpay treats 5xx as failed delivery and retries with exponential backoff — potentially for hours. Meanwhile each retry re-enters the same code and fails again, generating noise in logs and potentially causing brief DB connection exhaustion.

Additionally, if `notes` is not a `dict` (Razorpay's API can return it as an empty list `[]` for some edge cases), calling `.get()` on a list raises `AttributeError` → another unhandled 500.

**Fix:**

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

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("razorpay.webhook.bad_json")
        return {"received": True}   # ACK to stop retries

    event_type = event.get("event")

    try:
        if event_type == "payment.captured":
            payment = event["payload"]["payment"]["entity"]
            notes = payment.get("notes") or {}
            if not isinstance(notes, dict):
                notes = {}
            uid = notes.get("uid")
            plan_id = notes.get("plan_id")
            if uid and plan_id:
                upsert_subscription_from_stripe(uid=uid, plan_id=plan_id, payment_gateway="razorpay")

        elif event_type == "subscription.charged":
            subscription = event["payload"]["subscription"]["entity"]
            notes = subscription.get("notes") or {}
            if not isinstance(notes, dict):
                notes = {}
            uid = notes.get("uid")
            plan_id = notes.get("plan_id")
            if uid and plan_id:
                upsert_subscription_from_stripe(
                    uid=uid, plan_id=plan_id, payment_gateway="razorpay",
                    razorpay_subscription_id=subscription["id"],
                )

        elif event_type == "subscription.cancelled":
            subscription = event["payload"]["subscription"]["entity"]
            notes = subscription.get("notes") or {}
            if not isinstance(notes, dict):
                notes = {}
            uid = notes.get("uid")
            if uid:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE subscriptions SET status = 'cancelled' WHERE uid = %s AND payment_gateway = 'razorpay'",
                            (uid,),
                        )

    except (KeyError, TypeError) as e:
        logger.error("razorpay.webhook.parse_error event=%s error=%s", event_type, e)
        # Return 200 so Razorpay doesn't retry — log the error for manual review
        return {"received": True}

    return {"received": True}
```

---

### H3 — HIGH: `customer.subscription.updated` silently no-ops if DB row missing

**File:** `backend/app/api/v1/endpoints/subscriptions.py:404–423`

**Description:**

```python
elif event["type"] == "customer.subscription.updated":
    sub = event["data"]["object"]
    u_item = sub.items.data[0]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE subscriptions SET status = %s, current_period_start = %s, current_period_end = %s "
                "WHERE stripe_subscription_id = %s",
                (sub.status, ..., sub.id),
            )
```

This is a raw `UPDATE`. If no row exists yet (e.g., `customer.subscription.created` webhook is delayed or failed), this silently updates 0 rows. The subscription is never persisted.

Race condition scenario:
1. User completes Stripe checkout
2. Stripe fires `customer.subscription.created` and `customer.subscription.updated` nearly simultaneously
3. `updated` arrives first → UPDATE → 0 rows affected
4. `created` arrives → INSERT → row created (but with stale period data)

The `updated` event data is now lost and never re-applied.

**Fix:**

```python
elif event["type"] == "customer.subscription.updated":
    sub = event["data"]["object"]
    uid = (sub.metadata or {}).get("uid")   # set at checkout in subscription_data.metadata
    if not uid:
        logger.warning("stripe.webhook.updated.missing_uid", extra={"sub_id": sub.id})
    else:
        item = sub.items.data[0]
        price_id = item.price.id
        plan_id = _stripe_price_to_plan(price_id)
        try:
            period_start = datetime.datetime.fromtimestamp(item.current_period_start)
            period_end = datetime.datetime.fromtimestamp(item.current_period_end)
        except (AttributeError, TypeError, OSError):
            period_start = period_end = None
        upsert_subscription_from_stripe(
            uid=uid,
            plan_id=plan_id,
            stripe_subscription_id=sub.id,
            stripe_customer_id=sub.customer,
            status=sub.status,
            period_start=period_start,
            period_end=period_end,
        )
```

---

### M1 — MEDIUM: No rate limiting on `POST /checkout`

**File:** `backend/app/api/v1/endpoints/subscriptions.py:185`

**Description:**

`POST /checkout` creates a live object on Razorpay or Stripe with every call. An authenticated user (or a compromised token) can call it in a tight loop, creating hundreds of abandoned subscriptions/sessions. This:
- Exhausts Razorpay/Stripe API rate limits that affect all users
- Clutters provider dashboards with orphaned objects
- May trigger fraud-detection flags on the merchant account

**Fix:**

Add per-user rate limiting. With `slowapi` (already compatible with FastAPI):

```python
# backend/app/api/v1/endpoints/subscriptions.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/checkout")
@limiter.limit("5/minute")
def create_checkout(request: Request, body: CheckoutRequest, uid: str = Depends(get_required_user)):
    ...
```

Or a simpler Redis-backed counter keyed on `uid` if `slowapi` isn't already in the stack.

---

### M2 — MEDIUM: Valid Razorpay signatures can be replayed

**File:** `backend/app/api/v1/endpoints/subscriptions.py:278`

**Description:**

The `/razorpay/verify` endpoint doesn't check whether a `payment_id` has already been used. A valid `(order_id, payment_id, signature)` triple from a previous successful payment can be submitted again to reset/re-activate a subscription. Razorpay doesn't invalidate used signatures server-side from the merchant's perspective.

Concrete scenario: User subscribes, cancels via support, then replays an old verification request to re-activate without paying again.

**Fix:**

Track used payment IDs in the database:

```python
# In upsert_subscription_from_stripe or in the endpoint:
with get_db() as conn:
    with conn.cursor() as cur:
        # Prevent replay of already-used payment IDs
        if body.razorpay_payment_id:
            cur.execute(
                "SELECT 1 FROM subscriptions WHERE razorpay_last_payment_id = %s",
                (body.razorpay_payment_id,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Payment already processed")
```

Add a `razorpay_last_payment_id` column to `subscriptions` and populate it on every verify.

---

### M3 — MEDIUM: No idempotency keys on Razorpay order/subscription creation

**File:** `backend/app/services/razorpay_service.py:55, 75`

**Description:**

Neither `create_razorpay_subscription` nor `create_razorpay_order` sets an idempotency key. If a network timeout occurs between the Razorpay API call and the server's response to the frontend, the client retries `POST /checkout` → a second order/subscription is created. The user is now presented with two different subscription objects. Both appear as `created` in Razorpay. Only one ever gets paid, but the other sits as a ghost in Razorpay's system.

**Fix:**

```python
# backend/app/services/razorpay_service.py

def create_razorpay_order(amount_paise: int, plan_id: str, uid: str) -> dict:
    client = get_razorpay_client()
    # Idempotency key: same uid+plan_id within a 10-minute window produces the same order
    import time
    window = int(time.time()) // 600   # 10-minute bucket
    idempotency_key = f"{uid}_{plan_id}_{window}"
    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"ecalt_{plan_id}_{uid[:8]}",
            "notes": {"uid": uid, "plan_id": plan_id},
        },
        headers={"X-Razorpay-Idempotency-Key": idempotency_key},
    )
    return order
```

Same pattern for `create_razorpay_subscription`.

---

### M4 — MEDIUM: TypeScript interfaces model only order flow — subscription types missing

**File:** `frontend/src/lib/razorpay.ts`

**Description:**

```typescript
export interface RazorpayOptions {
  order_id: string        // required — wrong for subscription flow
  ...
}

export interface RazorpayResponse {
  razorpay_order_id: string    // subscription flow sends razorpay_subscription_id instead
  razorpay_payment_id: string
  razorpay_signature: string
  // razorpay_subscription_id missing
}
```

`Pricing.tsx` works around this with `options: any`, silencing all TypeScript safety checks across the entire payment handler. This means the compiler cannot catch any future mistakes in the subscription handler.

**Fix:**

```typescript
// frontend/src/lib/razorpay.ts

interface RazorpayOrderOptions {
  key: string
  amount: number
  currency: string
  order_id: string
  name: string
  description: string
  prefill?: { email?: string; contact?: string }
  handler: (response: RazorpayOrderResponse) => void
  modal?: { ondismiss?: () => void }
}

interface RazorpaySubscriptionOptions {
  key: string
  amount: number
  currency: string
  subscription_id: string
  name: string
  description: string
  prefill?: { email?: string; contact?: string }
  handler: (response: RazorpaySubscriptionResponse) => void
  modal?: { ondismiss?: () => void }
}

export type RazorpayOptions = RazorpayOrderOptions | RazorpaySubscriptionOptions

export interface RazorpayOrderResponse {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export interface RazorpaySubscriptionResponse {
  razorpay_subscription_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export type RazorpayResponse = RazorpayOrderResponse | RazorpaySubscriptionResponse
```

---

### M5 — MEDIUM: `customer.subscription.deleted` stores raw Stripe status string

**File:** `backend/app/api/v1/endpoints/subscriptions.py:431`

**Description:**

```python
cur.execute(
    "UPDATE subscriptions SET status = %s WHERE stripe_subscription_id = %s",
    (sub.status, sub.id),
)
```

For `customer.subscription.deleted`, `sub.status` is typically `"canceled"` (Stripe uses American spelling). However the same event can also carry `"incomplete_expired"` or other transitional states in edge cases. Storing arbitrary string values from the Stripe API into the `status` column bypasses any application-level enum validation. If Stripe ever introduces a new terminal state, the DB gets an unexpected value.

The `_ME_QUERY` only grants access for `status IN ('active', 'trialing')`, so this doesn't break the access gate — but it's fragile.

**Fix:**

```python
cur.execute(
    "UPDATE subscriptions SET status = 'cancelled' WHERE stripe_subscription_id = %s",
    (sub.id,),
)
```

---

### M6 — MEDIUM: `NOTIFICATION_SIGNING_SECRET` has hardcoded default

**File:** `backend/app/core/config.py:43`

**Description:**

```python
NOTIFICATION_SIGNING_SECRET: str = "ecalt-unsub-secret-change-in-prod"
```

If this key is not overridden in the production `.env`, unsubscribe links (and any other HMAC-signed notification tokens using this secret) can be forged by anyone who reads this source code. The comment "change-in-prod" is not enforced.

**Fix:**

```python
NOTIFICATION_SIGNING_SECRET: str = ""

# In app startup (e.g., main.py lifespan):
if settings.ENVIRONMENT != "development" and not settings.NOTIFICATION_SIGNING_SECRET:
    raise RuntimeError("NOTIFICATION_SIGNING_SECRET must be set in production")
```

---

### L1 — LOW: `loadRazorpayScript` race condition on concurrent calls

**File:** `frontend/src/lib/razorpay.ts:1`

**Description:**

If two calls to `loadRazorpayScript()` happen before the script finishes loading (e.g., two components mount simultaneously), both pass the `window.Razorpay` check, both inject a `<script>` tag, and both race. The second script load is redundant but triggers an extra network round-trip.

**Fix:**

```typescript
let _loadingPromise: Promise<boolean> | null = null

export function loadRazorpayScript(): Promise<boolean> {
  if ((window as any).Razorpay) return Promise.resolve(true)
  if (_loadingPromise) return _loadingPromise
  _loadingPromise = new Promise(resolve => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => { _loadingPromise = null; resolve(false) }
    document.body.appendChild(script)
  })
  return _loadingPromise
}
```

---

### L2 — LOW: Stripe `checkout_url` not validated before redirect

**File:** `frontend/src/pages/Pricing.tsx:144`

**Description:**

```typescript
if (data.checkout_url) { window.location.href = data.checkout_url }
```

The `checkout_url` is generated by Stripe's SDK server-side and will always be a `https://checkout.stripe.com/...` URL in normal operation. However, if the backend were ever compromised or if a MITM attack occurred against HTTP traffic, an arbitrary URL could be injected. Defence-in-depth recommends validating this.

**Fix:**

```typescript
const ALLOWED_CHECKOUT_ORIGINS = ['https://checkout.stripe.com']

if (data.checkout_url) {
  try {
    const url = new URL(data.checkout_url)
    if (!ALLOWED_CHECKOUT_ORIGINS.some(o => data.checkout_url.startsWith(o))) {
      console.error('Unexpected checkout URL origin:', url.origin)
      alert('Unexpected payment redirect. Contact support.')
      return
    }
    window.location.href = data.checkout_url
  } catch {
    alert('Invalid checkout URL received.')
  }
}
```

---

### L3 — LOW: `session_id` passed as query param lands in server access logs

**File:** `backend/app/api/v1/endpoints/subscriptions.py:123`

**Description:**

```python
@router.post("/sync")
def sync_subscription(session_id: str | None = None, ...):
```

And from Welcome.tsx:
```typescript
const url = sessionId
  ? `/api/v1/subscriptions/sync?session_id=${encodeURIComponent(sessionId)}`
  : '/api/v1/subscriptions/sync'
```

Stripe checkout session IDs (`cs_live_...`) appear in the server's access log. They expire quickly after checkout, making them low-sensitivity. However, under PCI-DSS compliance requirements, query parameters containing payment-related identifiers should not persist in logs.

**Fix:**

Accept `session_id` in the POST body:

```python
class SyncRequest(BaseModel):
    session_id: str | None = None

@router.post("/sync")
def sync_subscription(body: SyncRequest = Body(default=SyncRequest()), uid: str = Depends(get_required_user)):
    session_id = body.session_id
    ...
```

Frontend:
```typescript
const res = await fetch('/api/v1/subscriptions/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify({ session_id: sessionId || null }),
})
```

---

### L4 — LOW: Razorpay `subscription.cancelled` webhook UPDATE silently no-ops

**File:** `backend/app/api/v1/endpoints/subscriptions.py:347`

**Description:**

```python
cur.execute(
    "UPDATE subscriptions SET status = 'cancelled' WHERE uid = %s AND payment_gateway = 'razorpay'",
    (uid,),
)
```

If no active Razorpay subscription row exists for this `uid` (possible if `subscription.charged` was never processed, or the row was manually cleaned), the UPDATE silently does nothing. No log is emitted. This leaves no audit trail and makes it impossible to detect missing subscription rows.

**Fix:**

```python
cur.execute(
    "UPDATE subscriptions SET status = 'cancelled' WHERE uid = %s AND payment_gateway = 'razorpay'",
    (uid,),
)
if cur.rowcount == 0:
    logger.warning("razorpay.webhook.cancel_no_row", extra={"uid": uid})
```

---

### L5 — INFO: Redundant local `get_db` import inside webhook handler

**File:** `backend/app/api/v1/endpoints/subscriptions.py:350`

**Description:**

```python
from app.core.database import get_db   # line 13 — already imported at module level
...
elif event_type == "subscription.cancelled":
    ...
    from app.core.database import get_db   # line 350 — redundant
```

Not a bug. Appears to be a copy-paste artifact. The local import shadows the module-level one harmlessly, but creates confusion about whether `get_db` is available throughout the module.

**Fix:** Remove the local import at line 350.

---

## Priority Fix Order

1. **C1** — Frontend subscription handler calls verify (blocks subscriptions from being recorded)
2. **C2** — Confirm payment captured before activating (prevents getting subscription for uncaptured payments)
3. **H2** — Guard webhook JSON parse (prevents retry storm)
4. **H1** — Server-side country detection (prevents price manipulation)
5. **H3** — Upsert on `subscription.updated` (prevents race condition data loss)
6. **M1** — Rate limit `/checkout` (prevents provider abuse)
7. **M2** — Track used payment IDs (prevents replay)
8. All remaining Medium/Low findings
