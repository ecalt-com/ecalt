from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_required_user, get_admin_user
from app.services.coupon_service import (
    apply_coupon,
    create_coupon,
    list_coupons,
    update_coupon,
    delete_coupon,
    grant_coupon_to_user,
    get_coupon_redemptions,
)

router = APIRouter()


# ── User-facing ───────────────────────────────────────────────────────────────

class ApplyRequest(BaseModel):
    code: str


@router.post("/apply")
def apply(body: ApplyRequest, uid: str = Depends(get_required_user)):
    try:
        result = apply_coupon(uid, body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ── Admin ─────────────────────────────────────────────────────────────────────

class CreateCouponRequest(BaseModel):
    code: str
    description: str
    credit_cents: float = 0.0
    bonus_messages: int = 0
    plan_override: Optional[str] = None
    duration_days: Optional[int] = None
    max_redemptions: Optional[int] = None
    expires_at: Optional[datetime] = None


class UpdateCouponRequest(BaseModel):
    description: Optional[str] = None
    credit_cents: Optional[float] = None
    bonus_messages: Optional[int] = None
    max_redemptions: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    plan_override: Optional[str] = None
    duration_days: Optional[int] = None


class GrantCouponRequest(BaseModel):
    uid: str
    description: str
    credit_cents: float = 0.0
    bonus_messages: int = 0
    duration_days: Optional[int] = None


@router.get("/admin")
def admin_list(uid: str = Depends(get_admin_user)):
    return {"coupons": list_coupons()}


@router.post("/admin")
def admin_create(body: CreateCouponRequest, uid: str = Depends(get_admin_user)):
    try:
        coupon = create_coupon(
            code=body.code,
            description=body.description,
            credit_cents=body.credit_cents,
            bonus_messages=body.bonus_messages,
            plan_override=body.plan_override,
            duration_days=body.duration_days,
            max_redemptions=body.max_redemptions,
            expires_at=body.expires_at,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return coupon


@router.patch("/admin/{code}")
def admin_update(code: str, body: UpdateCouponRequest, uid: str = Depends(get_admin_user)):
    try:
        updated = update_coupon(code, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return updated


@router.delete("/admin/{code}", status_code=204)
def admin_delete(code: str, uid: str = Depends(get_admin_user)):
    try:
        delete_coupon(code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/grant")
def admin_grant(body: GrantCouponRequest, uid: str = Depends(get_admin_user)):
    if body.credit_cents == 0 and body.bonus_messages == 0:
        raise HTTPException(status_code=400, detail="Grant must include credit_cents or bonus_messages.")
    try:
        result = grant_coupon_to_user(
            uid=body.uid,
            description=body.description,
            credit_cents=body.credit_cents,
            bonus_messages=body.bonus_messages,
            duration_days=body.duration_days,
            granted_by=uid,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/admin/{code}/redemptions")
def admin_redemptions(code: str, uid: str = Depends(get_admin_user)):
    return {"redemptions": get_coupon_redemptions(code)}
