"""Student sign-in under /school-login (plans/school-courses SC-205, SC-206).

Public routes — students have no account yet when they call these. Limits key
on the class code or the student, never the IP address (a whole school shares
one). The service returns a Firebase custom token on success.
"""
from typing import Literal, Optional, Union

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.limiter import limiter
from app.services import school_login_service as login

router = APIRouter()


def _code_key(request: Request) -> str:
    return "class-code:" + str(request.path_params.get("code", "")).upper()


class StudentSecret(BaseModel):
    kind: Literal["picture", "pin"]
    value: Union[list[int], str] = Field(...)


class SessionRequest(BaseModel):
    class_code: str = Field(..., min_length=4, max_length=16)
    student_uid: Optional[str] = Field(None, max_length=64)
    external_ref: Optional[str] = Field(None, max_length=40)
    secret: StudentSecret


class BadgeRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=128)


@router.get("/classes/{code}", summary="Class sign-in page: class name + roster (first name + initial)")
@limiter.limit("120/minute", key_func=_code_key)
def lookup_class(request: Request, code: str):
    return login.lookup_class(code)


@router.post("/sessions", summary="Sign in with class code + picture password / PIN → Firebase custom token")
def create_session(body: SessionRequest):
    return login.sign_in(body.class_code, body.student_uid, body.external_ref, body.secret.kind, body.secret.value)


@router.post("/badge", summary="Sign in with a QR badge token → Firebase custom token")
def badge_session(body: BadgeRequest):
    return login.badge_sign_in(body.token)
