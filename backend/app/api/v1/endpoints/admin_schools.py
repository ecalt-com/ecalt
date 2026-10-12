"""ECALT admin: create and manage school tenants (plans/school-courses SC-111).

Sales-led (decision D2): an admin creates the school, sets its seat limit and
monthly AI budget, and invites the first owner. ECALT admins are not school
members — they can't see inside a school through the staff API.
"""
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import get_admin_user
from app.core.school_auth import parse_school_id
from app.services import school_service
from app.services.email_service import send_school_invite_email

router = APIRouter()

SchoolStatus = Literal["onboarding", "active", "suspended", "terminated"]


class CreateSchoolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    country: str = Field("IN", min_length=2, max_length=2)
    seat_limit: int = Field(0, ge=0, le=100_000)
    monthly_ai_budget_cents: float = Field(0, ge=0, le=100_000_000)
    owner_email: Optional[str] = Field(None, max_length=254)


class UpdateSchoolRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    status: Optional[SchoolStatus] = None
    seat_limit: Optional[int] = Field(None, ge=0, le=100_000)
    monthly_ai_budget_cents: Optional[float] = Field(None, ge=0, le=100_000_000)


class OwnerInviteRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


def _invite_owner(school_id: str, admin_uid: str, email: str, background_tasks: BackgroundTasks) -> dict:
    invite, token, school_name = school_service.create_invite(school_id, admin_uid, None, email, "owner")
    background_tasks.add_task(
        send_school_invite_email, invite["email"], school_name, "owner", token, invite["id"],
    )
    return invite


@router.post("", status_code=201, summary="Create a school (optionally inviting its first owner)")
def create_school(body: CreateSchoolRequest, background_tasks: BackgroundTasks,
                  uid: str = Depends(get_admin_user)):
    school = school_service.create_school(
        uid, body.name, body.country, body.seat_limit, body.monthly_ai_budget_cents,
    )
    if body.owner_email:
        school["owner_invite"] = _invite_owner(school["id"], uid, body.owner_email, background_tasks)
    return school


@router.get("", summary="List schools")
def list_schools(
    q: Optional[str] = Query(None, max_length=100),
    status: Optional[SchoolStatus] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _uid: str = Depends(get_admin_user),
):
    return school_service.list_schools(q, status, limit, offset)


@router.get("/{school_id}", summary="One school (with staff and student counts)")
def get_school(school_id: str, _uid: str = Depends(get_admin_user)):
    return school_service.get_school(school_id)


@router.patch("/{school_id}", summary="Change a school's name, status, seats or AI budget")
def update_school(school_id: str, body: UpdateSchoolRequest, uid: str = Depends(get_admin_user)):
    return school_service.admin_update_school(uid, school_id, body.model_dump(exclude_unset=True))


@router.post("/{school_id}/owner-invite", status_code=201, summary="Invite an owner by email")
def invite_owner(school_id: str, body: OwnerInviteRequest, background_tasks: BackgroundTasks,
                 uid: str = Depends(get_admin_user)):
    return _invite_owner(parse_school_id(school_id), uid, body.email, background_tasks)
