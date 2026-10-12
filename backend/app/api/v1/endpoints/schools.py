"""School staff API (plans/school-courses README §3.15, M1).

Every /schools/{school_id}/… route resolves the caller's membership through
core.school_auth.school_member(...): a school you don't belong to is a 404, a
role that's too low is a 403 school_role_required. The whole router 404s while
SCHOOLS_ENABLED is off (registered in router.py).
"""
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_active_account_holder, token_claims
from app.core.limiter import limiter
from app.core.school_auth import ADMIN_ROLES, SchoolCtx, school_member, uuid_or_404
from app.services import school_service
from app.services.email_service import send_school_invite_email

router = APIRouter()
invites_router = APIRouter()

StaffRole = Literal["owner", "admin", "teacher"]


class UpdateSchoolRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    settings: Optional[dict] = None


class DpaAcceptRequest(BaseModel):
    dpa_version: str = Field(..., min_length=1, max_length=32)


class InviteRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    role: StaffRole = "teacher"


class RoleChangeRequest(BaseModel):
    role: StaffRole


class InviteTokenRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)


# ── My schools ────────────────────────────────────────────────────────────────

@router.get("/mine", summary="Schools the signed-in account is staff at")
def my_schools(uid: str = Depends(get_active_account_holder)):
    return {"schools": school_service.my_schools(uid)}


# ── School ────────────────────────────────────────────────────────────────────

@router.get("/{school_id}", summary="School details, settings and the caller's role")
def get_school(ctx: SchoolCtx = Depends(school_member())):
    return school_service.school_detail(ctx)


@router.patch("/{school_id}", summary="Rename the school or change its settings (admins)")
def update_school(body: UpdateSchoolRequest, ctx: SchoolCtx = Depends(school_member(*ADMIN_ROLES))):
    return school_service.update_school(ctx, body.name, body.settings)


@router.post("/{school_id}/dpa/accept", summary="Accept the data processing agreement (owner)")
def accept_dpa(body: DpaAcceptRequest, ctx: SchoolCtx = Depends(school_member("owner"))):
    return school_service.accept_dpa(ctx, body.dpa_version)


# ── Staff ─────────────────────────────────────────────────────────────────────

@router.get("/{school_id}/staff", summary="Staff list (+ open invites for admins)")
def list_staff(ctx: SchoolCtx = Depends(school_member())):
    return school_service.list_staff(ctx)


@router.post("/{school_id}/staff/invites", status_code=201, summary="Invite a staff member by email (admins)")
def invite_staff(
    body: InviteRequest,
    background_tasks: BackgroundTasks,
    ctx: SchoolCtx = Depends(school_member(*ADMIN_ROLES)),
):
    invite, token, school_name = school_service.create_invite(
        ctx.school_id, ctx.uid, ctx.role, body.email, body.role,
    )
    background_tasks.add_task(
        send_school_invite_email, invite["email"], school_name, invite["role"], token, invite["id"],
    )
    return invite


@router.delete("/{school_id}/staff/invites/{invite_id}", status_code=204, summary="Revoke an open invite (admins)")
def revoke_invite(invite_id: str, ctx: SchoolCtx = Depends(school_member(*ADMIN_ROLES))):
    school_service.revoke_invite(ctx, uuid_or_404(invite_id, "invite_not_found"))


@router.patch("/{school_id}/staff/{member_uid}", summary="Change a staff member's role (admins)")
def change_role(member_uid: str, body: RoleChangeRequest, ctx: SchoolCtx = Depends(school_member(*ADMIN_ROLES))):
    return school_service.change_member_role(ctx, member_uid, body.role)


@router.delete("/{school_id}/staff/{member_uid}", status_code=204,
               summary="Remove a staff member (admins), or leave the school (yourself)")
def remove_staff(member_uid: str, ctx: SchoolCtx = Depends(school_member())):
    school_service.remove_member(ctx, member_uid)


# ── Invite links (/school-invites) ────────────────────────────────────────────

@invites_router.post("/preview", summary="What an invite link is for (no sign-in needed)")
@limiter.limit("30/minute")
def preview_invite(request: Request, body: InviteTokenRequest):
    return school_service.preview_invite(body.token)


@invites_router.post("/accept", summary="Join a school with an invite (verified email must match)")
@limiter.limit("30/minute")
def accept_invite(request: Request, body: InviteTokenRequest, uid: str = Depends(get_active_account_holder)):
    claims = token_claims(request.headers.get("authorization")) or {}
    return school_service.accept_invite(
        body.token, uid, claims.get("email"), bool(claims.get("email_verified")),
    )
