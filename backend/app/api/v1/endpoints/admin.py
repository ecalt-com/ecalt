from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_required_user
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
async def bootstrap_first_admin(body: BootstrapRequest):
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


def get_admin_user(uid: str = Depends(get_required_user)) -> str:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_admin FROM users WHERE uid = %s", (uid,))
            row = cur.fetchone()
            if not row or not row["is_admin"]:
                raise HTTPException(status_code=403, detail="Admin access required")
    return uid


@router.get("/plans")
async def list_plans(_uid: str = Depends(get_admin_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM plan_configs ORDER BY base_price_cents")
            return {"plans": [dict(r) for r in cur.fetchall()]}


class PlanUpdate(BaseModel):
    base_price_cents: Optional[int] = None
    token_budget_cents: Optional[int] = None
    lifetime_message_limit: Optional[int] = None
    max_seats: Optional[int] = None
    is_active: Optional[bool] = None
    stripe_price_id: Optional[str] = None


@router.patch("/plans/{plan_id}")
async def update_plan(plan_id: str, body: PlanUpdate, _uid: str = Depends(get_admin_user)):
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


@router.get("/stats")
async def get_stats(_uid: str = Depends(get_admin_user)):
    return get_admin_stats()


@router.get("/users")
async def list_users(_uid: str = Depends(get_admin_user)):
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
async def get_ai_config(_uid: str = Depends(get_admin_user)):
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
async def update_ai_config(body: AIConfigUpdate, _uid: str = Depends(get_admin_user)):
    valid_providers = list(AVAILABLE_MODELS.keys())
    if body.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {valid_providers}")
    valid_models = [m["id"] for m in AVAILABLE_MODELS.get(body.provider, [])]
    if body.model not in valid_models:
        raise HTTPException(status_code=400, detail=f"Model not available for provider {body.provider}")
    set_config(body.interaction_type, body.provider, body.model)
    return {"ok": True}


@router.get("/usage")
async def get_usage_breakdown(_uid: str = Depends(get_admin_user)):
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

    return {"by_model": by_model, "daily": daily}


@router.patch("/users/{target_uid}/toggle-admin")
async def toggle_admin(target_uid: str, acting_uid: str = Depends(get_admin_user)):
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
