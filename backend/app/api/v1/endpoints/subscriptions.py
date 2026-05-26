import datetime
import json
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.limiter import limiter

from app.core.auth import get_required_user
from app.core.logging_config import get_logger

logger = get_logger(__name__)
from app.core.config import settings
from app.core.database import get_db
from app.services.subscription_service import upsert_subscription_from_stripe

router = APIRouter()

_ME_QUERY = """
    SELECT
        pc.*,
        COALESCE(tu.input_tokens, 0)           AS _usage_input_tokens,
        COALESCE(tu.output_tokens, 0)          AS _usage_output_tokens,
        COALESCE(tu.estimated_cost_cents, 0.0) AS _usage_cost_cents,
        COALESCE(tu.message_count, 0)          AS _usage_message_count,
        COALESCE(cr.extra_credits, 0)          AS _extra_credits_cents,
        COALESCE(cr.bonus_msgs, 0)             AS _bonus_messages,
        COALESCE(u.is_admin, false)            AS _is_admin,
        COALESCE(mc.n, 0)                      AS _lifetime_messages
    FROM plan_configs pc
    JOIN (
        SELECT COALESCE(
            (SELECT plan_id FROM subscriptions
             WHERE uid = %(uid)s AND status IN ('active', 'trialing')
             LIMIT 1),
            'free_trial'
        ) AS plan_id
    ) rp ON pc.plan_id = rp.plan_id
    LEFT JOIN token_usage tu
        ON tu.uid = %(uid)s AND tu.period_start = %(period_start)s
    LEFT JOIN (
        SELECT COALESCE(SUM(credit_applied_cents), 0)   AS extra_credits,
               COALESCE(SUM(bonus_messages_applied), 0) AS bonus_msgs
        FROM coupon_redemptions
        WHERE uid = %(uid)s
          AND (credit_expires_at IS NULL OR credit_expires_at > now())
    ) cr ON true
    LEFT JOIN users u ON u.uid = %(uid)s
    LEFT JOIN (
        SELECT COUNT(*) AS n
        FROM conversation_messages
        WHERE conversation_id IN (SELECT id FROM conversations WHERE uid = %(uid)s)
          AND role = 'user'
    ) mc ON true
"""


def _build_me_response(uid: str) -> dict:
    period_start = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_ME_QUERY, {"uid": uid, "period_start": period_start})
            row = dict(cur.fetchone())

    plan = {k: v for k, v in row.items() if not k.startswith("_")}
    usage = {
        "uid": uid,
        "period_start": period_start,
        "input_tokens": row["_usage_input_tokens"],
        "output_tokens": row["_usage_output_tokens"],
        "estimated_cost_cents": float(row["_usage_cost_cents"]),
        "message_count": row["_usage_message_count"],
    }
    extras = {
        "extra_credits_cents": float(row["_extra_credits_cents"]),
        "bonus_messages": int(row["_bonus_messages"]),
    }
    is_free = plan["plan_id"] == "free_trial"
    base_limit = plan.get("lifetime_message_limit") or 6
    lifetime_limit = (base_limit + extras["bonus_messages"]) if is_free else None
    lifetime_count = row["_lifetime_messages"] if is_free else None
    base_budget = float(plan.get("token_budget_cents") or 20.0)
    total_budget = base_budget + extras["extra_credits_cents"]
    return {
        "plan": plan,
        "usage": usage,
        "coupon_extras": extras,
        "total_budget_cents": total_budget,
        "lifetime_message_count": lifetime_count,
        "lifetime_message_limit": lifetime_limit,
        "is_admin": bool(row["_is_admin"]),
        "is_limited": (
            (is_free and (lifetime_count or 0) >= (lifetime_limit or 6))
            or usage["estimated_cost_cents"] >= total_budget
        ),
    }


@router.get("/me")
def get_my_subscription(uid: str = Depends(get_required_user)):
    return _build_me_response(uid)


@router.get("/plans")
def list_plans():
    """Public endpoint: return all active plan configs."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM plan_configs WHERE is_active = true ORDER BY base_price_cents"
            )
            return {"plans": [dict(r) for r in cur.fetchall()]}


@router.get("/config")
def get_payment_config():
    """Public endpoint: return publishable payment keys for the frontend."""
    return {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    }


class SyncRequest(BaseModel):
    session_id: str | None = None


@router.post("/sync")
def sync_subscription(
    uid: str = Depends(get_required_user),
    body: SyncRequest = Body(default=SyncRequest()),
):
    """
    Called by the frontend immediately after a Stripe redirect (before the webhook
    fires) to pull the subscription state directly from Stripe.  Returns the same
    shape as GET /me so the caller can refresh in one round-trip.
    """
    session_id = body.session_id
    if session_id and settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(
                session_id,
                expand=["subscription"],
            )
            # Verify the session belongs to this user via client_reference_id
            # (set at checkout creation; works for all sessions regardless of metadata).
            if session.client_reference_id != uid:
                logger.warning(
                    "subscriptions.sync.uid_mismatch",
                    extra={"uid": uid, "session_ref": session.client_reference_id},
                )
                sub = None
            else:
                sub = session.subscription
            if sub:
                price_id = sub.items.data[0].price.id
                plan_id = _stripe_price_to_plan(price_id)
                item = sub.items.data[0]
                try:
                    period_start = datetime.datetime.fromtimestamp(item.current_period_start)
                    period_end = datetime.datetime.fromtimestamp(item.current_period_end)
                except AttributeError:
                    period_start = None
                    period_end = None
                upsert_subscription_from_stripe(
                    uid=uid,
                    plan_id=plan_id,
                    stripe_subscription_id=sub.id,
                    stripe_customer_id=sub.customer,
                    status=sub.status,
                    period_start=period_start,
                    period_end=period_end,
                )
                logger.info(
                    "subscriptions.sync.ok",
                    extra={"uid": uid, "plan_id": plan_id, "sub_id": sub.id, "status": sub.status},
                )
        except Exception:
            logger.warning("subscriptions.sync.failed", extra={"uid": uid, "session_id": session_id}, exc_info=True)

    return _build_me_response(uid)


class CheckoutRequest(BaseModel):
    plan_id: str
    country: str = "US"  # kept for API compatibility; server-side detection takes precedence


def _detect_country(request: Request) -> str:
    """Resolve user country server-side. Cloudflare header is authoritative; falls back to config."""
    cf = request.headers.get("cf-ipcountry", "")
    if cf and cf not in ("XX", "T1"):  # XX = unknown, T1 = Tor
        return cf
    return settings.GEO_DEFAULT_COUNTRY


@router.post("/checkout")
@limiter.limit("5/minute")
def create_checkout(request: Request, body: CheckoutRequest, uid: str = Depends(get_required_user)):
    # Use server-side geo — client-supplied country is ignored to prevent price manipulation.
    country = _detect_country(request)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stripe_price_id, base_price_inr_paise, razorpay_plan_id "
                "FROM plan_configs WHERE plan_id = %s AND is_active = true",
                (body.plan_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")

    if country == "IN":
        return _razorpay_checkout(uid, body.plan_id, row)
    return _stripe_checkout(uid, body.plan_id, row)


def _stripe_checkout(uid: str, plan_id: str, row) -> dict:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured. Add STRIPE_SECRET_KEY to enable payments.",
        )
    stripe_price_id = row.get("stripe_price_id")
    if not stripe_price_id:
        raise HTTPException(
            status_code=503,
            detail="Stripe price not configured for this plan. Set it via the admin panel.",
        )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/pricing",
        client_reference_id=uid,
        # Embed uid in subscription metadata so the customer.subscription.created
        # webhook has everything it needs without an extra Subscription.retrieve() call.
        subscription_data={"metadata": {"uid": uid, "app": "ecalt"}},
    )
    return {"gateway": "stripe", "checkout_url": session.url}


def _razorpay_checkout(uid: str, plan_id: str, row) -> dict:
    if not settings.RAZORPAY_KEY_ID:
        raise HTTPException(status_code=503, detail="Razorpay not configured")

    amount_paise = row.get("base_price_inr_paise")
    if not amount_paise:
        raise HTTPException(status_code=503, detail="INR price not configured for this plan")

    razorpay_plan_id = row.get("razorpay_plan_id")

    if razorpay_plan_id:
        # Recurring subscription — proper billing, Razorpay handles renewals
        from app.services.razorpay_service import create_razorpay_subscription
        sub = create_razorpay_subscription(razorpay_plan_id, uid, plan_id)
        return {
            "gateway": "razorpay",
            "checkout_type": "subscription",
            "subscription_id": sub["id"],
            "amount": amount_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
        }
    else:
        # Fallback: one-time order until plan is provisioned in Razorpay
        from app.services.razorpay_service import create_razorpay_order
        order = create_razorpay_order(amount_paise, plan_id, uid)
        return {
            "gateway": "razorpay",
            "checkout_type": "order",
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.RAZORPAY_KEY_ID,
        }


class RazorpayVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str
    # Subscription flow sends subscription_id; order/fallback flow sends order_id
    razorpay_subscription_id: str | None = None
    razorpay_order_id: str | None = None


@router.post("/razorpay/verify")
def verify_razorpay_payment(
    body: RazorpayVerifyRequest,
    uid: str = Depends(get_required_user),
):
    ref_id = body.razorpay_subscription_id or body.razorpay_order_id
    if not ref_id:
        raise HTTPException(
            status_code=400,
            detail="Provide razorpay_subscription_id (subscription flow) or razorpay_order_id (order flow)",
        )

    from app.services.razorpay_service import verify_razorpay_signature, get_razorpay_client
    if not verify_razorpay_signature(ref_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Replay prevention: reject a payment_id that was already activated
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM subscriptions WHERE razorpay_last_payment_id = %s",
                (body.razorpay_payment_id,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Payment already processed")

    # Order flow: confirm the payment is actually captured with Razorpay before granting access.
    # Signature alone only proves the response came from Razorpay checkout — not that money settled.
    if body.razorpay_order_id and not body.razorpay_subscription_id:
        try:
            client = get_razorpay_client()
            payment = client.payment.fetch(body.razorpay_payment_id)
            if payment.get("status") != "captured":
                raise HTTPException(status_code=402, detail="Payment not yet captured")
            if payment.get("order_id") != body.razorpay_order_id:
                raise HTTPException(status_code=400, detail="Payment and order ID mismatch")
        except HTTPException:
            raise
        except Exception:
            logger.error(
                "razorpay.verify.fetch_failed",
                extra={"uid": uid, "payment_id": body.razorpay_payment_id},
            )
            raise HTTPException(status_code=503, detail="Could not verify payment status with Razorpay")

    upsert_subscription_from_stripe(
        uid=uid,
        plan_id=body.plan_id,
        razorpay_subscription_id=body.razorpay_subscription_id,
        razorpay_last_payment_id=body.razorpay_payment_id,
        payment_gateway="razorpay",
    )
    return {"success": True}


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
        return {"received": True}

    event_type = event.get("event")

    try:
        if event_type == "payment.captured":
            # Order flow (one-time): notes carry uid/plan_id set at order creation
            payment = event["payload"]["payment"]["entity"]
            notes = payment.get("notes") or {}
            if not isinstance(notes, dict):
                notes = {}
            uid = notes.get("uid")
            plan_id = notes.get("plan_id")
            if uid and plan_id:
                upsert_subscription_from_stripe(
                    uid=uid,
                    plan_id=plan_id,
                    payment_gateway="razorpay",
                )

        elif event_type == "subscription.charged":
            # Fires on every successful renewal for Razorpay Subscriptions
            subscription = event["payload"]["subscription"]["entity"]
            notes = subscription.get("notes") or {}
            if not isinstance(notes, dict):
                notes = {}
            uid = notes.get("uid")
            plan_id = notes.get("plan_id")
            if uid and plan_id:
                upsert_subscription_from_stripe(
                    uid=uid,
                    plan_id=plan_id,
                    payment_gateway="razorpay",
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
                        if cur.rowcount == 0:
                            logger.warning("razorpay.webhook.cancel_no_row uid=%s", uid)

    except (KeyError, TypeError, AttributeError) as exc:
        logger.error("razorpay.webhook.parse_error event=%s error=%s", event_type, exc)
        return {"received": True}

    # payment.failed: no subscription change needed, just log for support
    return {"received": True}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event["type"] == "customer.subscription.created":
        # Snapshot — the full subscription object is already in the event.
        # uid is in metadata (set at checkout session creation via subscription_data).
        # No extra Subscription.retrieve() call needed.
        sub = event["data"]["object"]
        try:
            uid = sub.metadata["uid"]
        except (KeyError, TypeError, AttributeError):
            uid = None
        if uid:
            item = sub.items.data[0]
            price_id = item.price.id
            plan_id = _stripe_price_to_plan(price_id)
            upsert_subscription_from_stripe(
                uid=uid,
                plan_id=plan_id,
                stripe_subscription_id=sub.id,
                stripe_customer_id=sub.customer,
                status=sub.status,
                period_start=datetime.datetime.fromtimestamp(item.current_period_start),
                period_end=datetime.datetime.fromtimestamp(item.current_period_end),
            )
            logger.info(
                "stripe.webhook.subscription_created",
                extra={"uid": uid, "plan_id": plan_id, "sub_id": sub.id},
            )
        else:
            logger.warning(
                "stripe.webhook.missing_uid",
                extra={"sub_id": sub.id, "hint": "subscription_data.metadata.uid not set at checkout"},
            )

    elif event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        try:
            uid = sub.metadata["uid"]
        except (KeyError, TypeError, AttributeError):
            uid = None
        item = sub.items.data[0]
        plan_id = _stripe_price_to_plan(item.price.id)
        try:
            period_start = datetime.datetime.fromtimestamp(item.current_period_start)
            period_end = datetime.datetime.fromtimestamp(item.current_period_end)
        except (AttributeError, TypeError, OSError):
            period_start = period_end = None
        if uid:
            # Upsert so a race where updated arrives before created never loses data
            upsert_subscription_from_stripe(
                uid=uid,
                plan_id=plan_id,
                stripe_subscription_id=sub.id,
                stripe_customer_id=sub.customer,
                status=sub.status,
                period_start=period_start,
                period_end=period_end,
            )
        else:
            # uid not in metadata (old sessions before subscription_data.metadata was set)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE subscriptions SET status = %s, current_period_start = %s, current_period_end = %s "
                        "WHERE stripe_subscription_id = %s",
                        (sub.status, period_start, period_end, sub.id),
                    )
        logger.info(
            "stripe.webhook.subscription_updated",
            extra={"sub_id": sub.id, "status": sub.status, "uid": uid},
        )

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE subscriptions SET status = 'cancelled' WHERE stripe_subscription_id = %s",
                    (sub.id,),
                )
        logger.info(
            "stripe.webhook.subscription_deleted",
            extra={"sub_id": sub.id},
        )

    return {"received": True}


def _stripe_price_to_plan(price_id: str) -> str:
    """Map Stripe price ID back to our plan_id via plan_configs."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT plan_id FROM plan_configs WHERE stripe_price_id = %s",
                    (price_id,),
                )
                row = cur.fetchone()
                return row["plan_id"] if row else "individual"
    except Exception:
        return "individual"
