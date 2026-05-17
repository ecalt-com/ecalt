import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import get_required_user
from app.core.config import settings
from app.core.database import get_db
from app.services.subscription_service import (
    get_user_plan,
    get_current_usage,
    count_lifetime_messages,
    upsert_subscription_from_stripe,
)

router = APIRouter()


@router.get("/me")
async def get_my_subscription(uid: str = Depends(get_required_user)):
    plan = get_user_plan(uid)
    usage = get_current_usage(uid)

    is_free = plan["plan_id"] == "free_trial"
    lifetime_count = count_lifetime_messages(uid) if is_free else None
    lifetime_limit = plan.get("lifetime_message_limit") if is_free else None

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                is_admin = bool(row["is_admin"]) if row else False
    except Exception:
        is_admin = False

    return {
        "plan": plan,
        "usage": usage,
        "lifetime_message_count": lifetime_count,
        "is_admin": is_admin,
        "is_limited": (
            (is_free and (lifetime_count or 0) >= (lifetime_limit or 6))
            or (not is_free and usage["estimated_cost_cents"] >= (plan.get("token_budget_cents") or 0))
        ),
    }


@router.get("/plans")
async def list_plans():
    """Public endpoint: return all active plan configs."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM plan_configs WHERE is_active = true ORDER BY base_price_cents"
            )
            return {"plans": [dict(r) for r in cur.fetchall()]}


class CheckoutRequest(BaseModel):
    plan_id: str


@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, uid: str = Depends(get_required_user)):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured. Add STRIPE_SECRET_KEY to enable payments.",
        )

    # Validate plan
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stripe_price_id FROM plan_configs WHERE plan_id = %s AND is_active = true",
                (body.plan_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")

    stripe_price_id = row.get("stripe_price_id") if row else None
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
        success_url=f"{settings.FRONTEND_URL}/learn?upgraded=true",
        cancel_url=f"{settings.FRONTEND_URL}/pricing",
        client_reference_id=uid,
    )
    return {"checkout_url": session.url}


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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        uid = session.get("client_reference_id")
        sub_id = session.get("subscription")
        customer_id = session.get("customer")
        if uid and sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            plan_id = _stripe_price_to_plan(sub["items"]["data"][0]["price"]["id"])
            upsert_subscription_from_stripe(
                uid=uid,
                plan_id=plan_id,
                stripe_subscription_id=sub_id,
                stripe_customer_id=customer_id,
                status=sub["status"],
                period_start=datetime.datetime.fromtimestamp(sub["current_period_start"]),
                period_end=datetime.datetime.fromtimestamp(sub["current_period_end"]),
            )

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub = event["data"]["object"]
        sub_id = sub["id"]
        status = sub["status"]
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE subscriptions SET status = %s WHERE stripe_subscription_id = %s",
                    (status, sub_id),
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
