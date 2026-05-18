from datetime import date

from app.core.database import get_db
from app.services.provider_service import cost_for_tokens


def get_user_plan(uid: str) -> dict:
    """Return plan_configs row for user. Defaults to free_trial."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pc.* FROM subscriptions s
                JOIN plan_configs pc ON s.plan_id = pc.plan_id
                WHERE s.uid = %s AND s.status IN ('active', 'trialing')
                LIMIT 1
                """,
                (uid,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            cur.execute("SELECT * FROM plan_configs WHERE plan_id = 'free_trial'")
            return dict(cur.fetchone())


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
            return False, "free_trial_exhausted"
        return True, "ok"

    # Token budget gate (free trial non-chat + all paid plans)
    usage = get_current_usage(uid)
    base_budget = float(plan.get("token_budget_cents") or 20.0)
    total_budget = base_budget + extras["extra_credits_cents"]
    if usage["estimated_cost_cents"] >= total_budget:
        return False, "budget_exhausted"
    return True, "ok"


def record_usage(uid: str, input_tokens: int, output_tokens: int, model: str) -> None:
    """Upsert token_usage for the current billing month."""
    cost_cents = cost_for_tokens(model, input_tokens, output_tokens)
    period_start = date.today().replace(day=1)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO token_usage (uid, period_start, input_tokens, output_tokens, estimated_cost_cents, message_count)
                    VALUES (%s, %s, %s, %s, %s, 1)
                    ON CONFLICT (uid, period_start) DO UPDATE SET
                        input_tokens          = token_usage.input_tokens + EXCLUDED.input_tokens,
                        output_tokens         = token_usage.output_tokens + EXCLUDED.output_tokens,
                        estimated_cost_cents  = token_usage.estimated_cost_cents + EXCLUDED.estimated_cost_cents,
                        message_count         = token_usage.message_count + 1,
                        updated_at            = now()
                    """,
                    (uid, period_start, input_tokens, output_tokens, cost_cents),
                )
    except Exception:
        pass


def upsert_subscription_from_stripe(
    uid: str,
    plan_id: str,
    stripe_subscription_id: str,
    stripe_customer_id: str,
    status: str,
    period_start=None,
    period_end=None,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions
                  (uid, plan_id, stripe_subscription_id, stripe_customer_id, status, current_period_start, current_period_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    plan_id                = EXCLUDED.plan_id,
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    stripe_customer_id     = EXCLUDED.stripe_customer_id,
                    status                 = EXCLUDED.status,
                    current_period_start   = EXCLUDED.current_period_start,
                    current_period_end     = EXCLUDED.current_period_end
                """,
                (uid, plan_id, stripe_subscription_id, stripe_customer_id, status, period_start, period_end),
            )


def get_admin_stats() -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM users")
            total_users = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(DISTINCT uid) AS n FROM conversations WHERE started_at >= now() - interval '24 hours'")
            dau = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM conversation_messages WHERE created_at >= now() - interval '24 hours'")
            messages_today = cur.fetchone()["n"]

            cur.execute(
                "SELECT COALESCE(SUM(estimated_cost_cents), 0) AS n FROM token_usage WHERE period_start = date_trunc('month', now())::date"
            )
            monthly_cost_cents = float(cur.fetchone()["n"])

    return {
        "total_users": total_users,
        "dau": dau,
        "messages_today": messages_today,
        "monthly_api_cost_cents": monthly_cost_cents,
    }
