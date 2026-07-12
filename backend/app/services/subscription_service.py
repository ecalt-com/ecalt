import logging
from datetime import date

from app.core.database import get_db
from app.services.provider_service import cost_for_tokens

logger = logging.getLogger(__name__)


def get_user_plan(uid: str) -> dict:
    """Return plan_configs row for user. Defaults to free_trial.

    A child with no subscription of their own inherits their linked parent's
    Family plan (seat-capped: only the first max_seats-1 children by link age).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pc.* FROM plan_configs pc
                WHERE pc.plan_id = COALESCE(
                    (SELECT plan_id FROM subscriptions
                     WHERE uid = %(uid)s AND status IN ('active', 'trialing')
                     LIMIT 1),
                    (SELECT s.plan_id
                       FROM family_links fl
                       JOIN subscriptions s ON s.uid = fl.parent_uid
                        AND s.status IN ('active', 'trialing') AND s.plan_id = 'family'
                      WHERE fl.child_uid = %(uid)s AND fl.status = 'active'
                        AND (SELECT count(*) FROM family_links fl2
                              WHERE fl2.parent_uid = fl.parent_uid
                                AND fl2.status = 'active'
                                AND fl2.created_at <= fl.created_at)
                            <= (SELECT max_seats - 1 FROM plan_configs WHERE plan_id = 'family')
                      LIMIT 1),
                    'free_trial'
                )
                """,
                {"uid": uid},
            )
            return dict(cur.fetchone())


def get_family_member_uids(uid: str) -> list[str]:
    """All uids sharing this user's family budget: the subscribing parent plus
    active linked children. Returns [uid] for anyone outside a family."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT parent_uid FROM family_links WHERE child_uid = %s AND status = 'active'",
                (uid,),
            )
            row = cur.fetchone()
            root = row["parent_uid"] if row else uid
            cur.execute(
                "SELECT child_uid FROM family_links WHERE parent_uid = %s AND status = 'active' "
                "ORDER BY created_at",
                (root,),
            )
            children = [r["child_uid"] for r in cur.fetchall()]
    return [root] + children


def get_family_spend_cents(member_uids: list[str]) -> float:
    """Combined current-month spend across family members (shared budget)."""
    period_start = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(sum(estimated_cost_cents), 0) AS spent "
                "FROM token_usage WHERE uid = ANY(%s) AND period_start = %s",
                (member_uids, period_start),
            )
            row = cur.fetchone()
    return float(row["spent"] if row else 0.0)


def get_current_usage(uid: str) -> dict:
    """Return token_usage row for the current billing month."""
    period_start = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM token_usage WHERE uid = %s AND period_start = %s",
                (uid, period_start),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
    return {
        "uid": uid,
        "period_start": period_start,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_cents": 0.0,
        "message_count": 0,
    }


def count_lifetime_messages(uid: str) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM conversation_messages
                WHERE conversation_id IN (SELECT id FROM conversations WHERE uid = %s)
                  AND role = 'user'
                """,
                (uid,),
            )
            return cur.fetchone()["n"]


def get_coupon_extras(uid: str) -> dict:
    """Return summed active coupon benefits for a user: extra_credits_cents, bonus_messages."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(credit_applied_cents), 0) AS extra_credits,
                        COALESCE(SUM(bonus_messages_applied), 0) AS bonus_messages
                    FROM coupon_redemptions
                    WHERE uid = %s
                      AND (credit_expires_at IS NULL OR credit_expires_at > now())
                    """,
                    (uid,),
                )
                row = cur.fetchone()
                return {
                    "extra_credits_cents": float(row["extra_credits"]),
                    "bonus_messages": int(row["bonus_messages"]),
                }
    except Exception:
        return {"extra_credits_cents": 0.0, "bonus_messages": 0}


def check_budget(uid: str, context: str = "ai") -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    context='chat'  → free trial uses message count gate; paid uses token budget.
    context='ai'    → all plans use token budget (step content, explore, etc.).
    """
    plan = get_user_plan(uid)
    extras = get_coupon_extras(uid)

    if plan["plan_id"] == "free_trial" and context == "chat":
        base_limit = plan.get("lifetime_message_limit") or 6
        total_limit = base_limit + extras["bonus_messages"]
        used = count_lifetime_messages(uid)
        if used >= total_limit:
            logger.warning(
                "budget.blocked",
                extra={
                    "uid": uid,
                    "reason": "free_trial_exhausted",
                    "messages_used": used,
                    "messages_limit": total_limit,
                },
            )
            return False, "free_trial_exhausted"
        logger.debug(
            "budget.check_ok",
            extra={
                "uid": uid,
                "context": context,
                "plan": plan["plan_id"],
                "messages_used": used,
                "messages_limit": total_limit,
                "messages_remaining": total_limit - used,
            },
        )
        return True, "ok"

    # Token budget gate (free trial non-chat + all paid plans).
    # Family plans share one budget across parent + linked children.
    spent = None
    if plan["plan_id"] == "family":
        members = get_family_member_uids(uid)
        if len(members) > 1:
            spent = get_family_spend_cents(members)
    if spent is None:
        spent = get_current_usage(uid)["estimated_cost_cents"]
    base_budget = float(plan.get("token_budget_cents") or 20.0)
    total_budget = base_budget + extras["extra_credits_cents"]
    remaining = total_budget - spent

    if spent >= total_budget:
        logger.warning(
            "budget.blocked",
            extra={
                "uid": uid,
                "reason": "budget_exhausted",
                "plan": plan["plan_id"],
                "spent_cents": round(spent, 4),
                "budget_cents": round(total_budget, 2),
            },
        )
        return False, "budget_exhausted"

    logger.debug(
        "budget.check_ok",
        extra={
            "uid": uid,
            "context": context,
            "plan": plan["plan_id"],
            "spent_cents": round(spent, 4),
            "budget_cents": round(total_budget, 2),
            "remaining_cents": round(remaining, 4),
            "pct_used": round(spent / total_budget * 100, 1) if total_budget > 0 else 0.0,
        },
    )
    return True, "ok"


def record_usage(
    uid: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    interaction_type: str = "unknown",
    cached_input_tokens: int = 0,
) -> None:
    """Upsert token_usage for the current billing month and log budget status."""
    cost_cents = cost_for_tokens(model, input_tokens, output_tokens)
    period_start = date.today().replace(day=1)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO token_usage (uid, period_start, input_tokens, output_tokens, estimated_cost_cents, message_count, cached_input_tokens)
                    VALUES (%s, %s, %s, %s, %s, 1, %s)
                    ON CONFLICT (uid, period_start) DO UPDATE SET
                        input_tokens          = token_usage.input_tokens + EXCLUDED.input_tokens,
                        output_tokens         = token_usage.output_tokens + EXCLUDED.output_tokens,
                        estimated_cost_cents  = token_usage.estimated_cost_cents + EXCLUDED.estimated_cost_cents,
                        message_count         = token_usage.message_count + 1,
                        cached_input_tokens   = token_usage.cached_input_tokens + EXCLUDED.cached_input_tokens,
                        updated_at            = now()
                    RETURNING estimated_cost_cents, message_count
                    """,
                    (uid, period_start, input_tokens, output_tokens, cost_cents, cached_input_tokens),
                )
                row = cur.fetchone()
                spent_cents = float(row["estimated_cost_cents"]) if row else cost_cents

                cur.execute(
                    """
                    INSERT INTO usage_by_interaction
                        (uid, period_start, interaction_type, input_tokens, output_tokens,
                         cached_input_tokens, estimated_cost_cents, request_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    ON CONFLICT (uid, period_start, interaction_type) DO UPDATE SET
                        input_tokens         = usage_by_interaction.input_tokens + EXCLUDED.input_tokens,
                        output_tokens        = usage_by_interaction.output_tokens + EXCLUDED.output_tokens,
                        cached_input_tokens  = usage_by_interaction.cached_input_tokens + EXCLUDED.cached_input_tokens,
                        estimated_cost_cents = usage_by_interaction.estimated_cost_cents + EXCLUDED.estimated_cost_cents,
                        request_count        = usage_by_interaction.request_count + 1,
                        updated_at           = now()
                    """,
                    (uid, period_start, interaction_type, input_tokens, output_tokens,
                     cached_input_tokens, cost_cents),
                )

        try:
            plan = get_user_plan(uid)
            extras = get_coupon_extras(uid)
            base_budget = float(plan.get("token_budget_cents") or 20.0)
            total_budget = base_budget + extras["extra_credits_cents"]
            remaining = total_budget - spent_cents
            pct_used = round(spent_cents / total_budget * 100, 1) if total_budget > 0 else 0.0
            logger.info(
                "budget.usage_recorded",
                extra={
                    "uid": uid,
                    "interaction": interaction_type,
                    "model": model,
                    "in_tok": input_tokens,
                    "out_tok": output_tokens,
                    "call_cost_cents": round(cost_cents, 6),
                    "spent_cents": round(spent_cents, 4),
                    "budget_cents": round(total_budget, 2),
                    "remaining_cents": round(remaining, 4),
                    "pct_used": pct_used,
                    "plan": plan["plan_id"],
                },
            )
        except Exception:
            pass
    except Exception:
        pass


def get_budget_status(uid: str) -> dict:
    """Return full budget picture for a user."""
    plan = get_user_plan(uid)
    extras = get_coupon_extras(uid)

    spent = None
    if plan["plan_id"] == "family":
        members = get_family_member_uids(uid)
        if len(members) > 1:
            spent = get_family_spend_cents(members)
    if spent is None:
        spent = get_current_usage(uid)["estimated_cost_cents"]
    base_budget = float(plan.get("token_budget_cents") or 20.0)
    total_budget = base_budget + extras["extra_credits_cents"]
    remaining = max(0.0, total_budget - spent)
    pct_used = round(spent / total_budget * 100, 1) if total_budget > 0 else 0.0

    result: dict = {
        "plan_id": plan["plan_id"],
        "plan_name": plan.get("name", plan["plan_id"]),
        "token_budget_cents": round(total_budget, 2),
        "spent_cents": round(spent, 4),
        "remaining_cents": round(remaining, 4),
        "pct_used": pct_used,
        "is_limited": spent >= total_budget,
        "coupon_credits_cents": extras["extra_credits_cents"],
        "coupon_bonus_messages": extras["bonus_messages"],
        "lifetime_messages_used": None,
        "lifetime_messages_limit": None,
        "messages_remaining": None,
    }

    if plan["plan_id"] == "free_trial":
        base_limit = plan.get("lifetime_message_limit") or 6
        total_limit = base_limit + extras["bonus_messages"]
        used_messages = count_lifetime_messages(uid)
        result["lifetime_messages_used"] = used_messages
        result["lifetime_messages_limit"] = total_limit
        result["messages_remaining"] = max(0, total_limit - used_messages)
        result["is_limited"] = (used_messages >= total_limit) or (spent >= total_budget)

    return result


def get_usage_history(uid: str, months: int = 6) -> list[dict]:
    """Return token_usage rows for the past N months, newest first."""
    months = min(months, 24)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT period_start, input_tokens, output_tokens,
                       COALESCE(cached_input_tokens, 0) AS cached_input_tokens,
                       estimated_cost_cents, message_count
                FROM token_usage
                WHERE uid = %s
                  AND period_start >= (date_trunc('month', now()) - (%s * interval '1 month'))::date
                ORDER BY period_start DESC
                """,
                (uid, months),
            )
            return [dict(r) for r in cur.fetchall()]


def get_usage_breakdown(uid: str) -> list[dict]:
    """Return per-interaction-type usage for the current billing month, ordered by cost."""
    period_start = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT interaction_type, input_tokens, output_tokens,
                       COALESCE(cached_input_tokens, 0) AS cached_input_tokens,
                       estimated_cost_cents, request_count
                FROM usage_by_interaction
                WHERE uid = %s AND period_start = %s
                ORDER BY estimated_cost_cents DESC
                """,
                (uid, period_start),
            )
            return [dict(r) for r in cur.fetchall()]


def upsert_subscription_from_stripe(
    uid: str,
    plan_id: str,
    stripe_subscription_id: str = None,
    stripe_customer_id: str = None,
    status: str = "active",
    period_start=None,
    period_end=None,
    payment_gateway: str = "stripe",
    razorpay_subscription_id: str = None,
    razorpay_last_payment_id: str = None,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions
                  (uid, plan_id, stripe_subscription_id, stripe_customer_id, status,
                   current_period_start, current_period_end, payment_gateway,
                   razorpay_subscription_id, razorpay_last_payment_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    plan_id                  = EXCLUDED.plan_id,
                    stripe_subscription_id   = COALESCE(EXCLUDED.stripe_subscription_id, subscriptions.stripe_subscription_id),
                    stripe_customer_id       = COALESCE(EXCLUDED.stripe_customer_id, subscriptions.stripe_customer_id),
                    status                   = EXCLUDED.status,
                    current_period_start     = EXCLUDED.current_period_start,
                    current_period_end       = EXCLUDED.current_period_end,
                    payment_gateway          = EXCLUDED.payment_gateway,
                    razorpay_subscription_id = COALESCE(EXCLUDED.razorpay_subscription_id, subscriptions.razorpay_subscription_id),
                    razorpay_last_payment_id = COALESCE(EXCLUDED.razorpay_last_payment_id, subscriptions.razorpay_last_payment_id)
                """,
                (uid, plan_id, stripe_subscription_id, stripe_customer_id, status,
                 period_start, period_end, payment_gateway, razorpay_subscription_id,
                 razorpay_last_payment_id),
            )


def get_admin_stats() -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*)          FROM users)                                                      AS total_users,
                    (SELECT COUNT(DISTINCT uid) FROM conversations WHERE started_at >= now() - interval '24 hours') AS dau,
                    (SELECT COUNT(*)          FROM conversation_messages WHERE created_at >= now() - interval '24 hours') AS messages_today,
                    COALESCE((SELECT SUM(estimated_cost_cents) FROM token_usage
                               WHERE period_start = date_trunc('month', now())::date), 0)                     AS monthly_cost_cents
                """
            )
            row = cur.fetchone()
    return {
        "total_users": row["total_users"],
        "dau": row["dau"],
        "messages_today": row["messages_today"],
        "monthly_api_cost_cents": float(row["monthly_cost_cents"]),
    }
