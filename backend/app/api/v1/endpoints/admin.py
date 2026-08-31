from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.core.auth import get_required_user, get_admin_user
from app.core.database import get_db
from app.services.subscription_service import (
    get_admin_stats, get_usage_history,
    get_usage_breakdown as svc_usage_breakdown,
)
from app.services.provider_service import (
    AVAILABLE_MODELS, DEFAULT_CONFIG,
    get_all_configs, set_config,
    set_style_prompt, get_prompt_history,
    get_all_notification_templates, set_notification_template,
)

router = APIRouter()


class BootstrapRequest(BaseModel):
    email: Optional[str] = None
    uid: Optional[str] = None


@router.post("/bootstrap")
def bootstrap_first_admin(body: BootstrapRequest):
    """Set the first admin user. Only works when zero admins exist."""
    if not body.email and not body.uid:
        raise HTTPException(status_code=400, detail="Provide email or uid")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as n FROM users WHERE is_admin = true")
            if cur.fetchone()["n"] > 0:
                raise HTTPException(
                    status_code=403,
                    detail="Admins already exist. Use the admin panel or CLI to promote users.",
                )

            if body.uid:
                cur.execute(
                    "UPDATE users SET is_admin = true WHERE uid = %s RETURNING uid, email, display_name",
                    (body.uid,),
                )
            else:
                cur.execute(
                    "UPDATE users SET is_admin = true WHERE email = %s RETURNING uid, email, display_name",
                    (body.email,),
                )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found. They must sign in at least once.")
    return {"promoted": dict(row)}



@router.get("/plans")
def list_plans(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM plan_configs ORDER BY base_price_cents")
            return {"plans": [dict(r) for r in cur.fetchall()]}


class PlanCreate(BaseModel):
    plan_id: str
    name: str
    base_price_cents: int
    base_price_inr_paise: Optional[int] = None
    token_budget_cents: int
    lifetime_message_limit: Optional[int] = None
    max_seats: int = 1


@router.post("/plans")
def create_plan(body: PlanCreate, _uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plan_configs
                  (plan_id, name, base_price_cents, base_price_inr_paise,
                   token_budget_cents, lifetime_message_limit, max_seats, is_active)
                VALUES (%(plan_id)s, %(name)s, %(base_price_cents)s, %(base_price_inr_paise)s,
                        %(token_budget_cents)s, %(lifetime_message_limit)s, %(max_seats)s, true)
                RETURNING *
                """,
                body.model_dump(),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Plan ID already exists")
    return {"plan": dict(row)}


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    base_price_cents: Optional[int] = None
    base_price_inr_paise: Optional[int] = None
    token_budget_cents: Optional[int] = None
    lifetime_message_limit: Optional[int] = None
    max_seats: Optional[int] = None
    is_active: Optional[bool] = None
    stripe_price_id: Optional[str] = None
    razorpay_plan_id: Optional[str] = None


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: str, body: PlanUpdate, _uid: str = Depends(get_admin_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["plan_id"] = plan_id
    updates["updated_at"] = "now()"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE plan_configs SET {set_clause}, updated_at = now() WHERE plan_id = %(plan_id)s RETURNING *",
                updates,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": dict(row)}


class ProvisionRequest(BaseModel):
    gateway: str                              # "stripe" | "razorpay" | "both"
    base_price_inr_paise: Optional[int] = None  # set INR price inline if not already on plan
    base_price_cents: Optional[int] = None    # override USD price inline if needed


@router.post("/plans/{plan_id}/provision")
def provision_plan(plan_id: str, body: ProvisionRequest, _uid: str = Depends(get_admin_user)):
    """
    Auto-provision the plan in Stripe and/or Razorpay. Creates the Product+Price or
    Plan objects via their APIs and stores the resulting IDs back in plan_configs.

    Pass base_price_inr_paise in the request body to set the INR price and provision
    Razorpay in one step, without needing a separate PATCH call first.
    """
    if body.gateway not in ("stripe", "razorpay", "both"):
        raise HTTPException(status_code=400, detail="gateway must be 'stripe', 'razorpay', or 'both'")

    # Apply any inline price overrides before reading the plan row
    inline_updates: dict = {}
    if body.base_price_inr_paise is not None:
        inline_updates["base_price_inr_paise"] = body.base_price_inr_paise
    if body.base_price_cents is not None:
        inline_updates["base_price_cents"] = body.base_price_cents

    if inline_updates:
        set_clause = ", ".join(f"{k} = %({k})s" for k in inline_updates)
        inline_updates["plan_id"] = plan_id
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE plan_configs SET {set_clause} WHERE plan_id = %(plan_id)s",
                    inline_updates,
                )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM plan_configs WHERE plan_id = %s", (plan_id,))
            plan = cur.fetchone()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    result: dict = {}

    if body.gateway in ("stripe", "both"):
        from app.core.config import settings as _settings
        if not _settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is not configured on the server")
        if not plan["base_price_cents"]:
            raise HTTPException(status_code=400, detail="Free plans do not need a Stripe price")
        from app.services.stripe_service import provision_stripe_plan
        try:
            ids = provision_stripe_plan(plan_id, plan["name"], plan["base_price_cents"])
        except ValueError as e:
            raise HTTPException(status_code=502, detail=str(e))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE plan_configs SET stripe_price_id = %s, stripe_product_id = %s WHERE plan_id = %s",
                    (ids["stripe_price_id"], ids["stripe_product_id"], plan_id),
                )
        result["stripe"] = ids

    if body.gateway in ("razorpay", "both"):
        from app.core.config import settings as _settings
        if not _settings.RAZORPAY_KEY_ID:
            raise HTTPException(status_code=503, detail="RAZORPAY_KEY_ID is not configured on the server")
        inr_paise = plan["base_price_inr_paise"]
        if not inr_paise:
            raise HTTPException(
                status_code=400,
                detail="INR price is required for Razorpay. Pass base_price_inr_paise in this request.",
            )
        from app.services.razorpay_service import provision_razorpay_plan
        try:
            rp_plan_id = provision_razorpay_plan(plan_id, plan["name"], inr_paise)
        except ValueError as e:
            raise HTTPException(status_code=502, detail=str(e))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE plan_configs SET razorpay_plan_id = %s WHERE plan_id = %s",
                    (rp_plan_id, plan_id),
                )
        result["razorpay"] = {"razorpay_plan_id": rp_plan_id}

    return {"provisioned": result}


@router.get("/stats")
def get_stats(_uid: str = Depends(get_admin_user)):
    return get_admin_stats()


@router.get("/users")
def list_users(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.uid, u.email, u.display_name, u.is_admin, u.created_at,
                    COALESCE(s.plan_id, 'free_trial')  AS plan_id,
                    COALESCE(s.status, 'active')        AS sub_status,
                    pc.token_budget_cents               AS budget_cents,
                    COALESCE(tu.estimated_cost_cents, 0) AS spent_cents,
                    COALESCE(tu.input_tokens, 0)         AS input_tokens,
                    COALESCE(tu.output_tokens, 0)        AS output_tokens,
                    COALESCE(tu.cached_input_tokens, 0)  AS cached_input_tokens,
                    COALESCE(tu.message_count, 0)        AS message_count,
                    CASE
                        WHEN COALESCE(pc.token_budget_cents, 0) > 0
                        THEN ROUND(
                            (COALESCE(tu.estimated_cost_cents, 0) /
                            pc.token_budget_cents * 100)::numeric, 1
                        )
                        ELSE 0
                    END AS pct_used
                FROM users u
                LEFT JOIN subscriptions s
                    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
                LEFT JOIN plan_configs pc
                    ON pc.plan_id = COALESCE(s.plan_id, 'free_trial')
                LEFT JOIN token_usage tu
                    ON tu.uid = u.uid
                    AND tu.period_start = date_trunc('month', now())::date
                ORDER BY spent_cents DESC, u.created_at DESC
                LIMIT 100
                """
            )
            return {"users": [dict(r) for r in cur.fetchall()]}


@router.get("/ai-config")
def get_ai_config(_uid: str = Depends(get_admin_user)):
    """Return current provider/model config for each interaction type."""
    return {
        "configs": get_all_configs(),
        "available_models": AVAILABLE_MODELS,
    }


class AIConfigUpdate(BaseModel):
    interaction_type: str
    provider: str
    model: str


@router.patch("/ai-config")
def update_ai_config(body: AIConfigUpdate, _uid: str = Depends(get_admin_user)):
    valid_providers = list(AVAILABLE_MODELS.keys())
    if body.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {valid_providers}")
    valid_models = [m["id"] for m in AVAILABLE_MODELS.get(body.provider, [])]
    if body.model not in valid_models:
        raise HTTPException(status_code=400, detail=f"Model not available for provider {body.provider}")
    set_config(body.interaction_type, body.provider, body.model)
    return {"ok": True}


@router.get("/usage")
def get_usage_breakdown(_uid: str = Depends(get_admin_user)):
    """Token usage and cost breakdown by model for current billing month."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cm.model_used,
                    COUNT(*) AS message_count,
                    COALESCE(SUM(tu.input_tokens), 0) AS total_input,
                    COALESCE(SUM(tu.output_tokens), 0) AS total_output,
                    COALESCE(SUM(tu.estimated_cost_cents), 0) AS total_cost_cents
                FROM conversation_messages cm
                LEFT JOIN token_usage tu ON tu.uid = (
                    SELECT uid FROM conversations WHERE id = cm.conversation_id LIMIT 1
                )
                WHERE cm.created_at >= date_trunc('month', now())
                  AND cm.role = 'assistant'
                  AND cm.model_used IS NOT NULL
                GROUP BY cm.model_used
                ORDER BY total_cost_cents DESC
                """
            )
            by_model = [dict(r) for r in cur.fetchall()]

            # Daily message volume for last 14 days
            cur.execute(
                """
                SELECT
                    DATE(created_at) AS day,
                    COUNT(*) AS messages
                FROM conversation_messages
                WHERE created_at >= now() - interval '14 days'
                  AND role = 'user'
                GROUP BY day
                ORDER BY day
                """
            )
            daily = [{"day": str(r["day"]), "messages": r["messages"]} for r in cur.fetchall()]

            # Cache hit summary for current billing month
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(input_tokens), 0)        AS total_input,
                    COALESCE(SUM(cached_input_tokens), 0) AS total_cached_input,
                    COALESCE(SUM(estimated_cost_cents), 0) AS total_cost_cents
                FROM token_usage
                WHERE period_start = date_trunc('month', now())::date
                """
            )
            cache_row = cur.fetchone()
            total_input = int(cache_row["total_input"])
            total_cached = int(cache_row["total_cached_input"])
            cache_hit_pct = round(total_cached / total_input * 100, 1) if total_input > 0 else 0.0

    return {
        "by_model": by_model,
        "daily": daily,
        "cache": {
            "total_input_tokens": total_input,
            "total_cached_input_tokens": total_cached,
            "cache_hit_pct": cache_hit_pct,
        },
    }


@router.get("/revenue")
def get_revenue(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    pc.plan_id,
                    pc.name                                              AS plan_name,
                    pc.base_price_cents                                  AS price_cents,
                    pc.base_price_inr_paise,
                    COUNT(s.uid)                                         AS user_count,
                    SUM(CASE WHEN s.payment_gateway = 'stripe'
                             THEN pc.base_price_cents ELSE 0 END)        AS mrr_usd_cents,
                    SUM(CASE WHEN s.payment_gateway = 'razorpay'
                             THEN COALESCE(pc.base_price_inr_paise, 0)
                             ELSE 0 END)                                 AS mrr_inr_paise
                FROM subscriptions s
                JOIN plan_configs pc ON pc.plan_id = s.plan_id
                WHERE s.status IN ('active', 'trialing')
                GROUP BY pc.plan_id, pc.name, pc.base_price_cents, pc.base_price_inr_paise
                ORDER BY pc.base_price_cents DESC
                """
            )
            plan_distribution = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    COALESCE(s.status, 'no_subscription') AS status,
                    COUNT(*)                               AS user_count
                FROM users u
                LEFT JOIN subscriptions s ON s.uid = u.uid
                GROUP BY COALESCE(s.status, 'no_subscription')
                """
            )
            status_breakdown = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    payment_gateway,
                    COUNT(*)                                     AS subscriptions,
                    SUM(pc.base_price_cents)                     AS total_usd_cents,
                    SUM(COALESCE(pc.base_price_inr_paise, 0))    AS total_inr_paise
                FROM subscriptions s
                JOIN plan_configs pc ON pc.plan_id = s.plan_id
                WHERE s.status IN ('active', 'trialing')
                GROUP BY payment_gateway
                """
            )
            gateway_split = [dict(r) for r in cur.fetchall()]

    total_mrr_usd = sum((p.get("mrr_usd_cents") or 0) for p in plan_distribution)
    total_mrr_inr = sum((p.get("mrr_inr_paise") or 0) for p in plan_distribution)
    total_paid = next((s["user_count"] for s in status_breakdown if s["status"] == "active"), 0)
    total_trial = next((s["user_count"] for s in status_breakdown if s["status"] == "trialing"), 0)
    total_free = next((s["user_count"] for s in status_breakdown if s["status"] == "no_subscription"), 0)
    arpu_usd = round(total_mrr_usd / total_paid, 1) if total_paid > 0 else 0

    return {
        "plan_distribution": plan_distribution,
        "status_breakdown": status_breakdown,
        "gateway_split": gateway_split,
        "summary": {
            "total_mrr_usd_cents": total_mrr_usd,
            "total_mrr_inr_paise": total_mrr_inr,
            "total_paid_users": total_paid,
            "total_trial_users": total_trial,
            "total_free_users": total_free,
            "arpu_usd_cents": arpu_usd,
        },
    }


@router.get("/users/{target_uid}")
def get_user_detail(target_uid: str, _uid: str = Depends(get_admin_user)):
    """Full usage and account detail for a single user. Admin only."""
    with get_db() as conn:
        with conn.cursor() as cur:

            # ── Profile + subscription + current-month usage ──────────────────
            cur.execute(
                """
                SELECT
                    u.uid, u.email, u.display_name, u.photo_url,
                    u.is_admin, u.streak_days, u.last_active_date,
                    u.age_group_flag, u.account_status, u.created_at,

                    COALESCE(s.plan_id, 'free_trial')       AS plan_id,
                    pc.name                                  AS plan_name,
                    COALESCE(s.status, 'none')               AS sub_status,
                    s.payment_gateway,
                    s.current_period_start,
                    s.current_period_end,
                    pc.token_budget_cents                    AS budget_cents,
                    pc.lifetime_message_limit,

                    COALESCE(tu.estimated_cost_cents, 0)     AS spent_cents,
                    COALESCE(tu.input_tokens, 0)             AS input_tokens,
                    COALESCE(tu.output_tokens, 0)            AS output_tokens,
                    COALESCE(tu.cached_input_tokens, 0)      AS cached_input_tokens,
                    COALESCE(tu.message_count, 0)            AS message_count,
                    CASE
                        WHEN COALESCE(pc.token_budget_cents, 0) > 0
                        THEN ROUND(
                            (COALESCE(tu.estimated_cost_cents, 0) /
                             pc.token_budget_cents * 100)::numeric, 1
                        )
                        ELSE 0
                    END AS pct_used

                FROM users u
                LEFT JOIN subscriptions s
                    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
                LEFT JOIN plan_configs pc
                    ON pc.plan_id = COALESCE(s.plan_id, 'free_trial')
                LEFT JOIN token_usage tu
                    ON tu.uid = u.uid
                    AND tu.period_start = date_trunc('month', now())::date
                WHERE u.uid = %s
                """,
                (target_uid,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            profile = dict(row)

            # ── Lifetime stats ────────────────────────────────────────────────
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(estimated_cost_cents), 0) AS lifetime_cost_cents,
                    COALESCE(SUM(input_tokens), 0)         AS lifetime_input_tokens,
                    COALESCE(SUM(output_tokens), 0)        AS lifetime_output_tokens,
                    COALESCE(SUM(message_count), 0)        AS lifetime_message_count,
                    MIN(period_start)                      AS first_active_month
                FROM token_usage
                WHERE uid = %s
                """,
                (target_uid,),
            )
            lifetime = dict(cur.fetchone())

            # Total conversations
            cur.execute(
                "SELECT COUNT(*) AS total_conversations FROM conversations WHERE uid = %s",
                (target_uid,),
            )
            lifetime["total_conversations"] = cur.fetchone()["total_conversations"]

            # Lifetime chat messages (for free-trial gate visibility)
            cur.execute(
                """
                SELECT COUNT(*) AS lifetime_chat_messages
                FROM conversation_messages
                WHERE conversation_id IN (SELECT id FROM conversations WHERE uid = %s)
                  AND role = 'user'
                """,
                (target_uid,),
            )
            lifetime["lifetime_chat_messages"] = cur.fetchone()["lifetime_chat_messages"]

            # ── Active coupon credits ─────────────────────────────────────────
            cur.execute(
                """
                SELECT
                    c.code, c.description,
                    cr.credit_applied_cents,
                    cr.bonus_messages_applied,
                    cr.redeemed_at,
                    cr.credit_expires_at,
                    CASE
                        WHEN cr.credit_expires_at IS NULL THEN true
                        WHEN cr.credit_expires_at > now() THEN true
                        ELSE false
                    END AS is_active
                FROM coupon_redemptions cr
                JOIN coupons c ON c.code = cr.coupon_code
                WHERE cr.uid = %s
                ORDER BY cr.redeemed_at DESC
                """,
                (target_uid,),
            )
            coupons = [dict(r) for r in cur.fetchall()]

    # ── Per-interaction breakdown (current month) ─────────────────────────────
    breakdown = svc_usage_breakdown(target_uid)

    # ── Monthly history (last 12 months) ─────────────────────────────────────
    history = get_usage_history(target_uid, months=12)

    # Split the flat SQL row into logical sections
    usage_keys = {"spent_cents", "budget_cents", "input_tokens", "output_tokens",
                  "cached_input_tokens", "message_count", "pct_used"}
    current_month = {k: profile.pop(k) for k in list(profile) if k in usage_keys}

    return {
        "profile": profile,
        "current_month": current_month,
        "lifetime": lifetime,
        "breakdown": breakdown,
        "history": history,
        "coupons": coupons,
    }


@router.get("/cost-analysis")
def get_cost_analysis(_uid: str = Depends(get_admin_user)):
    """AI cost & margin risk analysis across plans, users, interaction types, and cache trend."""
    with get_db() as conn:
        with conn.cursor() as cur:

            # Query 1 — cost vs revenue per plan
            cur.execute(
                """
                SELECT
                    pc.plan_id,
                    pc.name                                         AS plan_name,
                    pc.base_price_cents                             AS price_cents,
                    pc.token_budget_cents                           AS budget_cents,
                    COUNT(DISTINCT s.uid)                           AS active_users,
                    COALESCE(SUM(tu.estimated_cost_cents), 0)       AS total_spent_cents,
                    COALESCE(AVG(tu.estimated_cost_cents), 0)       AS avg_spent_cents,
                    COALESCE(MAX(tu.estimated_cost_cents), 0)       AS max_spent_cents,
                    CASE WHEN pc.base_price_cents > 0
                         THEN ROUND((COALESCE(SUM(tu.estimated_cost_cents), 0) /
                              (pc.base_price_cents * NULLIF(COUNT(DISTINCT s.uid), 0)) * 100)::numeric, 1)
                         ELSE 0 END                                 AS cost_revenue_pct
                FROM plan_configs pc
                LEFT JOIN subscriptions s
                    ON s.plan_id = pc.plan_id AND s.status IN ('active', 'trialing')
                LEFT JOIN token_usage tu
                    ON tu.uid = s.uid
                    AND tu.period_start = date_trunc('month', now())::date
                GROUP BY pc.plan_id, pc.name, pc.base_price_cents, pc.token_budget_cents
                ORDER BY pc.base_price_cents DESC
                """
            )
            plan_margins = [dict(r) for r in cur.fetchall()]

            # Query 2 — users at risk (>75% of budget used this month)
            cur.execute(
                """
                SELECT
                    u.uid, u.email, u.display_name,
                    COALESCE(s.plan_id, 'free_trial')               AS plan_id,
                    pc.token_budget_cents                            AS budget_cents,
                    tu.estimated_cost_cents                          AS spent_cents,
                    ROUND((tu.estimated_cost_cents /
                           pc.token_budget_cents * 100)::numeric, 1) AS pct_used
                FROM token_usage tu
                JOIN users u ON u.uid = tu.uid
                LEFT JOIN subscriptions s
                    ON s.uid = tu.uid AND s.status IN ('active', 'trialing')
                JOIN plan_configs pc
                    ON pc.plan_id = COALESCE(s.plan_id, 'free_trial')
                WHERE tu.period_start = date_trunc('month', now())::date
                  AND pc.token_budget_cents > 0
                  AND (tu.estimated_cost_cents / pc.token_budget_cents) >= 0.75
                ORDER BY pct_used DESC
                LIMIT 50
                """
            )
            at_risk_users = [dict(r) for r in cur.fetchall()]

            # Query 3 — cost by interaction type (all users, this month)
            cur.execute(
                """
                SELECT
                    interaction_type,
                    COUNT(DISTINCT uid)              AS user_count,
                    SUM(request_count)               AS total_requests,
                    SUM(input_tokens)                AS total_input_tokens,
                    SUM(output_tokens)               AS total_output_tokens,
                    SUM(estimated_cost_cents)        AS total_cost_cents,
                    AVG(estimated_cost_cents)        AS avg_cost_per_user_cents
                FROM usage_by_interaction
                WHERE period_start = date_trunc('month', now())::date
                GROUP BY interaction_type
                ORDER BY total_cost_cents DESC
                """
            )
            by_interaction = [dict(r) for r in cur.fetchall()]

            # Query 4 — cache hit rate last 6 months
            cur.execute(
                """
                SELECT
                    period_start,
                    SUM(input_tokens)                AS total_input,
                    SUM(cached_input_tokens)         AS total_cached,
                    ROUND(
                        CASE WHEN SUM(input_tokens) > 0
                             THEN SUM(cached_input_tokens)::numeric / SUM(input_tokens) * 100
                             ELSE 0 END, 1
                    )                                AS cache_hit_pct,
                    SUM(estimated_cost_cents)        AS total_cost_cents
                FROM token_usage
                WHERE period_start >= date_trunc('month', now() - interval '5 months')::date
                GROUP BY period_start
                ORDER BY period_start
                """
            )
            cache_trend = [
                {**dict(r), "period_start": str(r["period_start"])}
                for r in cur.fetchall()
            ]

    return {
        "plan_margins": plan_margins,
        "at_risk_users": at_risk_users,
        "by_interaction": by_interaction,
        "cache_trend": cache_trend,
    }


@router.post("/journeys/{journey_id}/hero-image/regenerate")
async def regenerate_hero_image(journey_id: str, _uid: str = Depends(get_admin_user)):
    """Force-regenerate a journey's hero image (moderation / quality hatch).

    Runs synchronously so the admin sees the result; charged to no user budget.
    """
    from app.api.v1.endpoints.journeys import _db_journey, _journey_map
    from app.services.image_service import generate_and_attach_hero, images_enabled

    if not images_enabled():
        raise HTTPException(status_code=503, detail="Image storage not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")
    journey = _db_journey(journey_id) or _journey_map.get(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    url = await generate_and_attach_hero(journey, None)
    if not url:
        raise HTTPException(status_code=502, detail="Hero image generation failed — see server logs")
    return {"journey_id": journey_id, "hero_image_url": url}


class TestImageGenerationRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)


@router.post("/visual/test-image-generation")
async def test_visual_image_generation(body: TestImageGenerationRequest, _uid: str = Depends(get_admin_user)):
    """Diagnostic tool: directly exercises the image generation pipeline
    (OpenAI call -> upload -> Supabase Storage -> public URL), bypassing the
    Visual Planner entirely. Use this to tell apart "the pipeline is broken"
    from "the planner correctly never needed generation for this content" --
    see backend/plans/visual-intelligence/README.md. Charged to no user
    budget (uid=None), same pattern as hero-image/regenerate above.
    """
    from app.services.visual_image_service import generate_step_visual, images_enabled

    if not images_enabled():
        raise HTTPException(status_code=503, detail="Image storage not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")
    result = await generate_step_visual(body.description, uid=None)
    if not result:
        raise HTTPException(status_code=502, detail="Image generation failed — see server logs for the underlying exception")
    return result


@router.get("/marketplace-queue")
def list_marketplace_queue(
    status: str = "pending_review",
    search: Optional[str] = None,
    _uid: str = Depends(get_admin_user),
):
    """Journeys awaiting publish/reject (default: what the popularity job has
    flagged). Pass status=all + search to browse/feature any journey directly,
    bypassing the popularity job entirely — useful while real traffic is low."""
    filters = ["is_curated = FALSE"]
    params: list = []
    if status != "all":
        filters.append("marketplace_status = %s")
        params.append(status)
    if search:
        filters.append("title ILIKE %s")
        params.append(f"%{search}%")
    where_clause = " AND ".join(filters)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, uid, title, description, icon, age_group, difficulty,
                       marketplace_status, popularity_score, like_count, created_at
                FROM journeys
                WHERE {where_clause}
                ORDER BY popularity_score DESC, created_at DESC
                LIMIT 100
                """,
                params,
            )
            return {"queue": [dict(r) for r in cur.fetchall()]}


def _set_marketplace_status(journey_id: str, status: str, reviewer_uid: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE journeys
                SET marketplace_status = %s,
                    marketplace_reviewed_at = now(),
                    marketplace_reviewed_by = %s
                WHERE id = %s
                RETURNING id, marketplace_status
                """,
                (status, reviewer_uid, journey_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Journey not found")
    return dict(row)


@router.post("/marketplace-queue/{journey_id}/approve")
def approve_marketplace_journey(journey_id: str, uid: str = Depends(get_admin_user)):
    """Publish a pending journey to the marketplace."""
    return _set_marketplace_status(journey_id, "published", uid)


@router.post("/marketplace-queue/{journey_id}/reject")
def reject_marketplace_journey(journey_id: str, uid: str = Depends(get_admin_user)):
    """Reject a pending journey. The popularity job never re-flags a rejected journey."""
    return _set_marketplace_status(journey_id, "rejected", uid)


@router.post("/marketplace-queue/{journey_id}/reset")
def reset_marketplace_journey(journey_id: str, uid: str = Depends(get_admin_user)):
    """Send a journey back to private — unpublishes a live one, or gives a
    rejected one another chance to be reconsidered by the popularity job."""
    return _set_marketplace_status(journey_id, "private", uid)


@router.get("/content-stats")
def get_content_stats(journey_id: Optional[str] = None, _uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            if journey_id:
                cur.execute(
                    """
                    SELECT
                        up.step_id,
                        COUNT(DISTINCT up.uid) AS completions
                    FROM user_progress up
                    WHERE up.journey_id = %s
                    GROUP BY up.step_id
                    ORDER BY completions DESC
                    """,
                    (journey_id,),
                )
                return {"step_dropoff": [dict(r) for r in cur.fetchall()]}

            cur.execute(
                """
                SELECT
                    j.id, j.title, j.icon, j.difficulty,
                    j.estimated_hours, j.age_group,
                    COUNT(DISTINCT up.uid)                        AS unique_learners,
                    COUNT(*)                                      AS total_step_completions,
                    jsonb_array_length(j.steps)                  AS total_steps,
                    COUNT(DISTINCT CASE
                        WHEN step_counts.completed = jsonb_array_length(j.steps)
                        THEN step_counts.uid END)                AS fully_completed_users,
                    ROUND(
                        COUNT(DISTINCT CASE
                            WHEN step_counts.completed = jsonb_array_length(j.steps)
                            THEN step_counts.uid END
                        )::numeric /
                        NULLIF(COUNT(DISTINCT up.uid), 0) * 100
                    , 1)                                         AS completion_pct
                FROM journeys j
                LEFT JOIN user_progress up ON up.journey_id = j.id
                LEFT JOIN (
                    SELECT journey_id, uid, COUNT(*) AS completed
                    FROM user_progress
                    GROUP BY journey_id, uid
                ) step_counts ON step_counts.journey_id = j.id
                             AND step_counts.uid = up.uid
                GROUP BY j.id, j.title, j.icon, j.difficulty, j.estimated_hours, j.age_group
                HAVING COUNT(DISTINCT up.uid) > 0
                ORDER BY unique_learners DESC
                LIMIT 20
                """
            )
            top_journeys = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT journey_id) AS journeys_started,
                    COUNT(DISTINCT uid)        AS users_with_progress,
                    ROUND(AVG(pct)::numeric, 1) AS avg_completion_pct
                FROM (
                    SELECT
                        up.uid, up.journey_id,
                        COUNT(up.step_id)::float /
                        NULLIF(jsonb_array_length(j.steps), 0) * 100 AS pct
                    FROM user_progress up
                    JOIN journeys j ON j.id = up.journey_id
                    GROUP BY up.uid, up.journey_id, j.steps
                ) sub
                """
            )
            summary = dict(cur.fetchone())

            cur.execute(
                """
                SELECT
                    c.id, c.title, c.uid,
                    u.email, u.display_name,
                    COUNT(*)              AS message_count,
                    MAX(cm.created_at)   AS last_message_at
                FROM conversations c
                JOIN conversation_messages cm ON cm.conversation_id = c.id
                JOIN users u ON u.uid = c.uid
                WHERE c.started_at >= now() - interval '30 days'
                GROUP BY c.id, c.title, c.uid, u.email, u.display_name
                ORDER BY message_count DESC
                LIMIT 20
                """
            )
            top_conversations = []
            for r in cur.fetchall():
                row = dict(r)
                if row.get("last_message_at"):
                    row["last_message_at"] = row["last_message_at"].isoformat()
                top_conversations.append(row)

            cur.execute(
                """
                SELECT
                    discovered_at::date       AS day,
                    COUNT(*)                  AS new_concepts,
                    COUNT(DISTINCT uid)       AS unique_users
                FROM knowledge_nodes
                WHERE discovered_at >= now() - interval '14 days'
                GROUP BY day
                ORDER BY day
                """
            )
            knowledge_growth = [
                {**dict(r), "day": str(r["day"])}
                for r in cur.fetchall()
            ]

    return {
        "top_journeys": top_journeys,
        "completion_summary": {
            "journeys_started": int(summary["journeys_started"] or 0),
            "users_with_progress": int(summary["users_with_progress"] or 0),
            "avg_completion_pct": float(summary["avg_completion_pct"] or 0),
        },
        "top_conversations": top_conversations,
        "knowledge_growth": knowledge_growth,
    }


@router.get("/funnel")
def get_funnel(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH signups AS (
                    SELECT uid, created_at::date AS signup_date
                    FROM users
                ),
                conversions AS (
                    SELECT s.uid, MIN(s.created_at) AS converted_at
                    FROM subscriptions s
                    WHERE s.status IN ('active', 'trialing')
                      AND s.plan_id != 'free_trial'
                    GROUP BY s.uid
                )
                SELECT
                    COUNT(DISTINCT sg.uid)                              AS total_signups,
                    COUNT(DISTINCT CASE
                        WHEN co.converted_at::date <= sg.signup_date + 30
                        THEN sg.uid END)                                AS converted_30d,
                    COUNT(DISTINCT CASE
                        WHEN co.converted_at::date <= sg.signup_date + 60
                        THEN sg.uid END)                                AS converted_60d,
                    COUNT(DISTINCT CASE
                        WHEN co.converted_at::date <= sg.signup_date + 90
                        THEN sg.uid END)                                AS converted_90d,
                    ROUND(AVG(
                        CASE WHEN co.converted_at IS NOT NULL
                             THEN (co.converted_at::date - sg.signup_date)
                        END
                    )::numeric, 1)                                      AS avg_days_to_convert
                FROM signups sg
                LEFT JOIN conversions co ON co.uid = sg.uid
                WHERE sg.signup_date >= CURRENT_DATE - 180
                """
            )
            conv_row = dict(cur.fetchone())
            total = int(conv_row["total_signups"])

            def _pct(n):
                return round(int(n) / total * 100, 1) if total > 0 else 0.0

            cur.execute(
                """
                SELECT
                    date_trunc('month', current_period_end)::date AS month,
                    COUNT(*)                                      AS cancellations
                FROM subscriptions
                WHERE status = 'cancelled'
                  AND current_period_end >= now() - interval '6 months'
                GROUP BY month
                ORDER BY month
                """
            )
            cancels = {str(r["month"]): int(r["cancellations"]) for r in cur.fetchall()}

            cur.execute(
                """
                SELECT
                    date_trunc('month', created_at)::date AS month,
                    COUNT(*)                              AS new_subscriptions
                FROM subscriptions
                WHERE status IN ('active', 'trialing')
                  AND plan_id != 'free_trial'
                  AND created_at >= now() - interval '6 months'
                GROUP BY month
                ORDER BY month
                """
            )
            activations = {str(r["month"]): int(r["new_subscriptions"]) for r in cur.fetchall()}

            all_months = sorted(set(cancels) | set(activations))
            monthly_churn = [
                {
                    "month": m,
                    "cancellations": cancels.get(m, 0),
                    "new_subscriptions": activations.get(m, 0),
                }
                for m in all_months
            ]

            cur.execute(
                """
                SELECT
                    u.uid, u.email, u.display_name,
                    u.created_at::date AS signup_date,
                    COALESCE(mc.n, 0)  AS lifetime_messages
                FROM users u
                LEFT JOIN subscriptions s
                    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
                    AND s.plan_id != 'free_trial'
                LEFT JOIN (
                    SELECT c.uid, COUNT(*) AS n
                    FROM conversation_messages cm
                    JOIN conversations c ON c.id = cm.conversation_id
                    WHERE cm.role = 'user'
                    GROUP BY c.uid
                ) mc ON mc.uid = u.uid
                WHERE s.uid IS NULL
                  AND COALESCE(mc.n, 0) >= 6
                ORDER BY u.created_at DESC
                LIMIT 100
                """
            )
            exhausted = []
            for r in cur.fetchall():
                row = dict(r)
                row["signup_date"] = str(row["signup_date"]) if row["signup_date"] else None
                exhausted.append(row)

    return {
        "conversion": {
            "total_signups_180d": total,
            "converted_30d": int(conv_row["converted_30d"]),
            "converted_30d_pct": _pct(conv_row["converted_30d"]),
            "converted_60d": int(conv_row["converted_60d"]),
            "converted_60d_pct": _pct(conv_row["converted_60d"]),
            "converted_90d": int(conv_row["converted_90d"]),
            "converted_90d_pct": _pct(conv_row["converted_90d"]),
            "avg_days_to_convert": float(conv_row["avg_days_to_convert"]) if conv_row["avg_days_to_convert"] else None,
        },
        "monthly_churn": monthly_churn,
        "trial_exhausted_never_upgraded": exhausted,
    }


@router.get("/feature-usage")
def get_feature_usage(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    interaction_type,
                    COUNT(DISTINCT uid)         AS unique_users,
                    SUM(request_count)          AS total_requests,
                    SUM(input_tokens)           AS total_input_tokens,
                    SUM(output_tokens)          AS total_output_tokens,
                    SUM(cached_input_tokens)    AS total_cached_tokens,
                    SUM(estimated_cost_cents)   AS total_cost_cents,
                    ROUND(AVG(estimated_cost_cents / NULLIF(request_count, 0))::numeric, 6)
                                                AS avg_cost_per_request_cents
                FROM usage_by_interaction
                WHERE period_start = date_trunc('month', now())::date
                GROUP BY interaction_type
                ORDER BY total_requests DESC
                """
            )
            this_month = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    period_start,
                    interaction_type,
                    SUM(request_count)        AS total_requests,
                    SUM(estimated_cost_cents) AS total_cost_cents
                FROM usage_by_interaction
                WHERE period_start >= date_trunc('month', now() - interval '5 months')::date
                GROUP BY period_start, interaction_type
                ORDER BY period_start, total_requests DESC
                """
            )
            trend = [
                {**dict(r), "period_start": str(r["period_start"])}
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT
                    cm.model_used,
                    COUNT(*)                          AS message_count,
                    COALESCE(SUM(tu.estimated_cost_cents), 0) AS total_cost_cents
                FROM conversation_messages cm
                JOIN conversations c ON c.id = cm.conversation_id
                LEFT JOIN token_usage tu
                    ON tu.uid = c.uid
                    AND tu.period_start = date_trunc('month', now())::date
                WHERE cm.created_at >= date_trunc('month', now())
                  AND cm.role = 'assistant'
                  AND cm.model_used IS NOT NULL
                GROUP BY cm.model_used
                ORDER BY message_count DESC
                """
            )
            models = [dict(r) for r in cur.fetchall()]

    return {"this_month": this_month, "trend": trend, "models": models}


@router.get("/retention")
def get_retention(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT CASE WHEN last_active_date = CURRENT_DATE
                                        THEN uid END) AS dau,
                    COUNT(DISTINCT CASE WHEN last_active_date >= CURRENT_DATE - 6
                                        THEN uid END) AS wau,
                    COUNT(DISTINCT CASE WHEN last_active_date >= CURRENT_DATE - 29
                                        THEN uid END) AS mau
                FROM users
                """
            )
            active = dict(cur.fetchone())
            dau = int(active["dau"])
            wau = int(active["wau"])
            mau = int(active["mau"])
            stickiness = round(dau / mau * 100, 1) if mau > 0 else 0.0

            cur.execute(
                """
                WITH cohort AS (
                    SELECT
                        u.uid,
                        u.created_at::date AS signup_date,
                        MIN(tu_all.period_start) AS first_active_month
                    FROM users u
                    LEFT JOIN token_usage tu_all ON tu_all.uid = u.uid
                    WHERE u.created_at >= now() - interval '60 days'
                    GROUP BY u.uid, u.created_at
                ),
                activity AS (
                    SELECT DISTINCT
                        c.uid,
                        cm.created_at::date AS active_date
                    FROM conversation_messages cm
                    JOIN conversations c ON c.id = cm.conversation_id
                    WHERE cm.role = 'user'
                )
                SELECT
                    COUNT(DISTINCT c.uid) AS cohort_size,
                    COUNT(DISTINCT CASE
                        WHEN a.active_date BETWEEN c.signup_date + 1
                                               AND c.signup_date + 2
                        THEN c.uid END) AS retained_d1,
                    COUNT(DISTINCT CASE
                        WHEN a.active_date BETWEEN c.signup_date + 7
                                               AND c.signup_date + 14
                        THEN c.uid END) AS retained_d7,
                    COUNT(DISTINCT CASE
                        WHEN a.active_date BETWEEN c.signup_date + 30
                                               AND c.signup_date + 60
                        THEN c.uid END) AS retained_d30
                FROM cohort c
                LEFT JOIN activity a ON a.uid = c.uid
                """
            )
            ret_row = dict(cur.fetchone())
            cohort_size = int(ret_row["cohort_size"])
            d1_count = int(ret_row["retained_d1"])
            d7_count = int(ret_row["retained_d7"])
            d30_count = int(ret_row["retained_d30"])

            def _pct(count: int, total: int) -> float:
                return round(count / total * 100, 1) if total > 0 else 0.0

            cur.execute(
                """
                SELECT
                    date_trunc('week', created_at)::date AS week_start,
                    COUNT(*) AS new_users
                FROM users
                WHERE created_at >= now() - interval '12 weeks'
                GROUP BY week_start
                ORDER BY week_start
                """
            )
            weekly_signups = [
                {"week_start": str(r["week_start"]), "new_users": r["new_users"]}
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT
                    u.uid, u.email, u.display_name,
                    u.created_at::date                        AS signup_date,
                    COALESCE(s.plan_id, 'free_trial')         AS plan_id,
                    COALESCE(tu.message_count, 0)             AS ai_requests_ever,
                    u.last_active_date
                FROM users u
                LEFT JOIN subscriptions s
                    ON s.uid = u.uid AND s.status IN ('active', 'trialing')
                LEFT JOIN token_usage tu
                    ON tu.uid = u.uid
                    AND tu.period_start = date_trunc('month', now())::date
                WHERE u.created_at <= now() - interval '3 days'
                  AND (u.last_active_date IS NULL
                       OR u.last_active_date < CURRENT_DATE - 14)
                ORDER BY u.created_at DESC
                LIMIT 100
                """
            )
            inactive_users = []
            for r in cur.fetchall():
                row = dict(r)
                row["signup_date"] = str(row["signup_date"]) if row["signup_date"] else None
                row["last_active_date"] = str(row["last_active_date"]) if row["last_active_date"] else None
                inactive_users.append(row)

    return {
        "active_users": {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "stickiness": stickiness,
        },
        "retention": {
            "cohort_size": cohort_size,
            "cohort_window": "last 60 days",
            "d1_count": d1_count,
            "d1_pct": _pct(d1_count, cohort_size),
            "d7_count": d7_count,
            "d7_pct": _pct(d7_count, cohort_size),
            "d30_count": d30_count,
            "d30_pct": _pct(d30_count, cohort_size),
        },
        "weekly_signups": weekly_signups,
        "inactive_users": inactive_users,
    }


@router.patch("/users/{target_uid}/toggle-admin")
def toggle_admin(target_uid: str, acting_uid: str = Depends(get_admin_user)):
    """Promote or demote a user's admin status."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_admin = NOT is_admin WHERE uid = %s RETURNING uid, email, display_name, is_admin",
                (target_uid,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
    return {"user": dict(row)}


# ── Impersonation ─────────────────────────────────────────────────────────────

_MAX_ACTIVE_SESSIONS = 5


class ImpersonateRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/impersonate/{target_uid}")
def start_impersonation(
    target_uid: str,
    body: ImpersonateRequest,
    admin_uid: str = Depends(get_admin_user),
):
    """Issue a 30-minute impersonation session for target_uid. Admin only."""
    if target_uid == admin_uid:
        raise HTTPException(status_code=400, detail="Cannot impersonate yourself")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_admin FROM users WHERE uid = %s", (target_uid,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Target user not found")
            if row["is_admin"]:
                raise HTTPException(status_code=403, detail="Cannot impersonate another admin account")

            # Rate-limit: max active sessions per admin
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM admin_impersonation_sessions
                WHERE admin_uid = %s AND ended_at IS NULL AND expires_at > now()
                """,
                (admin_uid,),
            )
            if cur.fetchone()["n"] >= _MAX_ACTIVE_SESSIONS:
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many active impersonation sessions (max {_MAX_ACTIVE_SESSIONS}). End one first.",
                )

            cur.execute(
                """
                INSERT INTO admin_impersonation_sessions (admin_uid, target_uid, reason)
                VALUES (%s, %s, %s)
                RETURNING id, expires_at
                """,
                (admin_uid, target_uid, body.reason),
            )
            session = cur.fetchone()

    return {
        "session_id": str(session["id"]),
        "expires_at": session["expires_at"].isoformat(),
        "target_uid": target_uid,
    }


@router.delete("/impersonate/{session_id}", status_code=204)
def end_impersonation(session_id: str, admin_uid: str = Depends(get_admin_user)):
    """End an active impersonation session."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE admin_impersonation_sessions
                SET ended_at = now(), ended_by = 'admin'
                WHERE id = %s AND admin_uid = %s AND ended_at IS NULL
                """,
                (session_id, admin_uid),
            )


@router.delete("/impersonate/sessions/{session_id}/revoke", status_code=204)
def revoke_impersonation(session_id: str, _uid: str = Depends(get_admin_user)):
    """Force-end any admin's impersonation session (super-admin revocation)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE admin_impersonation_sessions
                SET ended_at = now(), ended_by = 'revoke'
                WHERE id = %s AND ended_at IS NULL
                """,
                (session_id,),
            )


@router.get("/impersonation-log")
def get_impersonation_log(
    limit: int = Query(50, ge=1, le=200),
    _uid: str = Depends(get_admin_user),
):
    """Recent impersonation sessions with audit request counts."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id, s.admin_uid, s.target_uid, s.reason,
                    s.created_at, s.expires_at, s.ended_at, s.ended_by,
                    u_admin.email        AS admin_email,
                    u_admin.display_name AS admin_name,
                    u_target.email       AS target_email,
                    u_target.display_name AS target_name,
                    COUNT(a.id)          AS request_count
                FROM admin_impersonation_sessions s
                JOIN users u_admin  ON u_admin.uid  = s.admin_uid
                JOIN users u_target ON u_target.uid = s.target_uid
                LEFT JOIN admin_impersonation_audit a ON a.session_id = s.id
                GROUP BY s.id, u_admin.email, u_admin.display_name,
                         u_target.email, u_target.display_name
                ORDER BY s.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = []
            for r in cur.fetchall():
                row = dict(r)
                row["id"] = str(row["id"])
                if row.get("created_at"):
                    row["created_at"] = row["created_at"].isoformat()
                if row.get("expires_at"):
                    row["expires_at"] = row["expires_at"].isoformat()
                if row.get("ended_at"):
                    row["ended_at"] = row["ended_at"].isoformat()
                rows.append(row)
    return {"sessions": rows}


# ── Prompt management ─────────────────────────────────────────────────────────

class PromptRead(BaseModel):
    interaction_type:        str
    style_prompt:            Optional[str]   # None = using hardcoded default
    style_prompt_is_default: bool
    default_style_prompt:    str
    output_contract_hint:    str
    style_prompt_updated_at: Optional[str]
    style_prompt_updated_by: Optional[str]
    provider:                str
    model:                   str


class PromptUpdate(BaseModel):
    style_prompt: str = Field(..., min_length=10, max_length=8000)


class PromptHistoryEntry(BaseModel):
    id:               int
    interaction_type: str
    old_style_prompt: Optional[str]
    new_style_prompt: str
    changed_by:       str
    changed_at:       str
    reset_to_default: bool


_CONTRACT_HINTS: dict[str, str] = {
    "journey":              "JSON: title, description, age_group, difficulty, steps[]",
    "step_content":         "JSON: content (structured markdown)",
    "spark":                "JSON: answer, mission{title, steps[]}",
    "knowledge_extraction": "JSON array: [{concept, domain}]",
    "daily_chat":           "Free-form conversational response",
    "mind_signature":       "3 plain-text paragraphs",
    "nudge":                "JSON: subject, body_html, short_message",
    "daily_spark":          "Free-form single question string",
    "onboarding":           "Not yet implemented",
    "fingerprint":          "Not yet implemented",
}


def _to_prompt_read(c: dict) -> PromptRead:
    return PromptRead(
        interaction_type=c["interaction_type"],
        style_prompt=c["style_prompt"],
        style_prompt_is_default=c["style_prompt_is_default"],
        default_style_prompt=c["default_style_prompt"],
        output_contract_hint=_CONTRACT_HINTS.get(c["interaction_type"], ""),
        style_prompt_updated_at=(
            c["style_prompt_updated_at"].isoformat()
            if c["style_prompt_updated_at"] else None
        ),
        style_prompt_updated_by=c["style_prompt_updated_by"],
        provider=c["provider"],
        model=c["model"],
    )


@router.get("/prompts", response_model=list[PromptRead])
def list_prompts(_uid: str = Depends(get_admin_user)):
    return [_to_prompt_read(c) for c in get_all_configs()]


@router.get("/prompts/{interaction_type}", response_model=PromptRead)
def get_prompt(interaction_type: str, _uid: str = Depends(get_admin_user)):
    cfg = next((c for c in get_all_configs() if c["interaction_type"] == interaction_type), None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    return _to_prompt_read(cfg)


@router.put("/prompts/{interaction_type}", status_code=204)
def update_prompt(
    interaction_type: str,
    body: PromptUpdate,
    uid: str = Depends(get_admin_user),
):
    if interaction_type not in DEFAULT_CONFIG:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    set_style_prompt(
        interaction_type=interaction_type,
        style_prompt=body.style_prompt,
        changed_by=uid,
        reset_to_default=False,
    )


@router.post("/prompts/{interaction_type}/reset", status_code=204)
def reset_prompt(interaction_type: str, uid: str = Depends(get_admin_user)):
    if interaction_type not in DEFAULT_CONFIG:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    set_style_prompt(
        interaction_type=interaction_type,
        style_prompt="",
        changed_by=uid,
        reset_to_default=True,
    )


@router.get("/prompts/{interaction_type}/history", response_model=list[PromptHistoryEntry])
def prompt_history(
    interaction_type: str,
    limit: int = Query(20, ge=1, le=100),
    _uid: str = Depends(get_admin_user),
):
    rows = get_prompt_history(interaction_type, limit=limit)
    return [
        PromptHistoryEntry(
            id=r["id"],
            interaction_type=r["interaction_type"],
            old_style_prompt=r["old_style_prompt"],
            new_style_prompt=r["new_style_prompt"],
            changed_by=r["changed_by"],
            changed_at=r["changed_at"].isoformat(),
            reset_to_default=r["reset_to_default"],
        )
        for r in rows
    ]


# ── Notification template management ─────────────────────────────────────────

class NotificationTemplateRead(BaseModel):
    notification_type: str
    template:          str
    updated_at:        Optional[str]
    updated_by:        Optional[str]


class NotificationTemplateUpdate(BaseModel):
    template: str = Field(..., min_length=10, max_length=4000)


_VALID_NOTIFICATION_TYPES: frozenset[str] = frozenset({
    "daily_spark", "re_engagement", "cliffhanger_return", "connection_alert",
    "milestone_approach", "mind_signature_ready", "mind_signature_nudge",
    "world_event_hook", "streak_at_risk", "streak_lost", "streak_milestone",
    "journey_almost_done", "weekly_digest", "family_highlight",
})

TEMPLATE_VARIABLES: dict[str, list[str]] = {
    "daily_spark":          ["name", "topics", "angle"],
    "re_engagement":        ["name", "days_inactive", "domain"],
    "cliffhanger_return":   ["name", "topic"],
    "connection_alert":     ["name", "topic_a", "topic_b", "connection"],
    "milestone_approach":   ["name", "steps_remaining", "journey_title"],
    "mind_signature_ready": ["name", "domain"],
    "mind_signature_nudge": ["name", "mastery_pct", "domain"],
    "world_event_hook":     ["name", "event", "topic"],
    "streak_at_risk":       ["name", "streak_days"],
    "streak_lost":          ["name", "streak_days"],
    "streak_milestone":     ["name", "streak_days"],
    "journey_almost_done":  ["name", "steps_remaining", "journey_title"],
    "weekly_digest":        ["name", "new_concepts", "active_domains", "domains", "journeys_touched"],
    "family_highlight":     ["name", "summary"],
}


@router.get("/notification-templates/variables")
def template_variables(_uid: str = Depends(get_admin_user)):
    return TEMPLATE_VARIABLES


@router.get("/notification-templates", response_model=list[NotificationTemplateRead])
def list_notification_templates(_uid: str = Depends(get_admin_user)):
    rows = get_all_notification_templates()
    return [
        NotificationTemplateRead(
            notification_type=r["notification_type"],
            template=r["template"],
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
            updated_by=r["updated_by"],
        )
        for r in rows
    ]


@router.put("/notification-templates/{notification_type}", status_code=204)
def update_notification_template(
    notification_type: str,
    body: NotificationTemplateUpdate,
    uid: str = Depends(get_admin_user),
):
    if notification_type not in _VALID_NOTIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="Unknown notification type")
    set_notification_template(
        notification_type=notification_type,
        template=body.template,
        updated_by=uid,
    )
