import hashlib
import hmac
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def provision_razorpay_plan(plan_id: str, name: str, amount_paise: int) -> str:
    """
    Creates a Razorpay Plan for a subscription tier. Called once per plan from the
    admin panel. Returns the Razorpay plan_id ("plan_XXXX").

    Requires the Razorpay account to have Subscriptions enabled (Dashboard → Settings).
    """
    import razorpay as _rzp
    client = get_razorpay_client()
    try:
        plan = client.plan.create({
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": name,
                "amount": amount_paise,
                "currency": "INR",
            },
            "notes": {"plan_id": plan_id, "app": "ecalt"},
        })
    except (_rzp.errors.BadRequestError, _rzp.errors.ServerError) as e:
        logger.error("razorpay.provision.error plan_id=%s error=%s", plan_id, e)
        err_str = str(e).lower()
        # ServerError (5xx) on plan creation almost always means Subscriptions is not
        # activated; Razorpay returns an empty body so str(e) is "".
        if isinstance(e, _rzp.errors.ServerError) or any(
            kw in err_str for kw in ("subscription", "feature", "not been activated")
        ):
            raise ValueError(
                "Razorpay Subscriptions are not enabled on this account. "
                "Activate it once at: Dashboard → Settings → Subscriptions. "
                "There is no API to enable this — it is a one-time dashboard action."
            ) from e
        raise ValueError(f"Razorpay error: {e}") from e
    logger.info("razorpay.provision: created plan %s for %s", plan["id"], plan_id)
    return plan["id"]


def create_razorpay_subscription(razorpay_plan_id: str, uid: str, plan_id: str) -> dict:
    """
    Creates a Razorpay Subscription for a user linked to the given plan.
    total_count=12 gives a 12-month cycle; set to 0 for indefinite where supported.
    Returns the full subscription dict (id is "sub_XXXX").
    """
    client = get_razorpay_client()
    subscription = client.subscription.create({
        "plan_id": razorpay_plan_id,
        "total_count": 12,
        "notes": {"uid": uid, "plan_id": plan_id},
    })
    logger.info(
        "razorpay.subscription: created %s for uid=%s plan=%s",
        subscription["id"], uid, plan_id,
    )
    return subscription


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
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
