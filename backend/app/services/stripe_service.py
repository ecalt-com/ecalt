import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def provision_stripe_plan(plan_id: str, name: str, amount_cents: int) -> dict:
    """
    Idempotent. Searches for an existing Stripe Product by plan_id metadata before
    creating a new one. Always creates a new Price (Stripe prices are immutable once
    attached to a subscription).

    Returns {"stripe_product_id": "prod_...", "stripe_price_id": "price_..."}
    """
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError("STRIPE_SECRET_KEY is not configured")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        search = stripe.Product.search(query=f'metadata["plan_id"]:"{plan_id}"')
        if search.data:
            product = search.data[0]
            logger.info("stripe.provision: reusing existing product %s for plan %s", product.id, plan_id)
        else:
            product = stripe.Product.create(
                name=name,
                metadata={"plan_id": plan_id, "app": "ecalt"},
            )
            logger.info("stripe.provision: created product %s for plan %s", product.id, plan_id)

        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount_cents,
            currency="usd",
            recurring={"interval": "month"},
            metadata={"plan_id": plan_id, "app": "ecalt"},
        )
        logger.info("stripe.provision: created price %s for plan %s", price.id, plan_id)
    except stripe.error.AuthenticationError as e:
        raise ValueError(f"Stripe authentication failed — check STRIPE_SECRET_KEY. Detail: {e}") from e
    except stripe.error.StripeError as e:
        raise ValueError(f"Stripe error: {e}") from e

    return {"stripe_product_id": product.id, "stripe_price_id": price.id}
