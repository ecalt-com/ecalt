from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_required_user, get_admin_user
from app.core.database import get_db
from app.services.subscription_service import get_admin_stats
from app.services.provider_service import (
    AVAILABLE_MODELS, get_all_configs, set_config
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
                SELECT u.uid, u.email, u.display_name, u.is_admin, u.created_at,
                       COALESCE(s.plan_id, 'free_trial') as plan_id,
                       COALESCE(s.status, 'active') as sub_status
                FROM users u
                LEFT JOIN subscriptions s ON u.uid = s.uid
                ORDER BY u.created_at DESC LIMIT 100
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
