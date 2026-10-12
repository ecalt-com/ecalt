"""School tenancy and school-student restrictions (plans/school-courses README §3.4).

Two layers:

- **Student route allowlist.** School students ('stu_' uids, signed in with a
  backend-minted Firebase custom token) may only call the routes listed in
  STUDENT_ALLOWED_ROUTES. core.auth.get_signed_in_uid — the root of every
  authenticated dependency — enforces it, so a route added later is denied to
  students until it is added here on purpose (tests/api/schools enumerates
  app.routes to keep this list honest).
- **Staff membership.** Every /schools/{school_id}/… route depends on
  school_member(...), which resolves the caller's role in that school. Child
  resources are always loaded with the school id in the WHERE clause. A school
  the caller doesn't belong to is a 404, never a 403, so existence never leaks.
"""
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request

from app.core.auth import get_parent_session

logger = logging.getLogger(__name__)

STUDENT_UID_PREFIX = "stu_"

# (method, route template). Learner routes here still check, per journey, that
# the course is assigned to one of the student's active classes
# (services/journey_access.py).
STUDENT_ALLOWED_ROUTES: frozenset[tuple[str, str]] = frozenset({
    # bootstrap
    ("POST", "/api/v1/users"),
    ("GET", "/api/v1/users/me"),
    # assigned school courses
    ("GET", "/api/v1/journeys"),
    ("GET", "/api/v1/journeys/{journey_id}"),
    ("GET", "/api/v1/journeys/{journey_id}/steps/{step_id}/content"),
    ("GET", "/api/v1/journeys/{journey_id}/steps/{step_id}/visual"),
    ("POST", "/api/v1/journeys/{journey_id}/steps/{step_id}/visual/events"),
    ("POST", "/api/v1/journeys/{journey_id}/steps/{step_id}/feedback"),
    ("GET", "/api/v1/progress/{journey_id}"),
    ("POST", "/api/v1/progress/{journey_id}/{step_id}"),
    ("DELETE", "/api/v1/progress/{journey_id}/{step_id}"),
    ("POST", "/api/v1/quiz"),
    ("GET", "/api/v1/quiz/step-status/{journey_id}/{step_id}"),
    ("POST", "/api/v1/quiz/{quiz_id}/hint"),
    ("POST", "/api/v1/quiz/{quiz_id}/submit"),
    # in-course tutor only (chat.py rejects every other interaction type)
    ("POST", "/api/v1/chat/stream"),
})


def require_schools_enabled() -> None:
    """Router-level dependency: the schools API doesn't exist while the
    SCHOOLS_ENABLED flag is off."""
    from app.core.config import settings
    if not settings.SCHOOLS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


def is_school_student_uid(uid: Optional[str]) -> bool:
    return bool(uid) and uid.startswith(STUDENT_UID_PREFIX)


def student_not_allowed() -> HTTPException:
    return HTTPException(status_code=403, detail={
        "error": "school_student_not_allowed",
        "message": "This isn't available with a school sign-in.",
    })


def enforce_student_route(request: Request) -> None:
    """Raise 403 unless the matched route is on the student allowlist.
    Fails closed when the route can't be determined."""
    route = request.scope.get("route")
    path = getattr(route, "path_format", None)
    method = "GET" if request.method == "HEAD" else request.method
    if path is None or (method, path) not in STUDENT_ALLOWED_ROUTES:
        raise student_not_allowed()


# ── Staff membership ──────────────────────────────────────────────────────────

ALL_ROLES = ("owner", "admin", "teacher")
ADMIN_ROLES = ("owner", "admin")
# Schools in these states are usable; 'suspended' blocks everyone with a
# 403, 'terminated' hides the school (404).
OPEN_SCHOOL_STATUSES = ("onboarding", "active")


@dataclass(frozen=True)
class SchoolCtx:
    uid: str
    school_id: str
    role: str
    school_status: str

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES


_member_cache: dict[tuple[str, str], tuple[Optional[tuple[str, str]], float]] = {}
_MEMBER_CACHE_TTL = 60.0


def invalidate_school_member_cache(school_id: Optional[str] = None, uid: Optional[str] = None) -> None:
    """Call after any membership, role or school-status change. With no
    arguments it clears everything."""
    for key in list(_member_cache):
        if (school_id is None or key[1] == school_id) and (uid is None or key[0] == uid):
            _member_cache.pop(key, None)


def school_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "school_not_found", "message": "School not found."})


def uuid_or_404(value: str, error: str = "not_found") -> str:
    """Canonical UUID string, or a 404 for anything malformed (never a 500
    from the database's uuid cast)."""
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail={"error": error, "message": "Not found."})


def parse_school_id(school_id: str) -> str:
    try:
        return str(uuid.UUID(school_id))
    except (ValueError, TypeError, AttributeError):
        raise school_not_found()


def load_membership(uid: str, school_id: str) -> Optional[tuple[str, str]]:
    """(role, school status) for an active member, else None. Cached 60 s.

    Fails closed: on a DB error with nothing cached the request is rejected
    rather than guessing a role.
    """
    from app.core.database import get_db
    key = (uid, school_id)
    now = time.monotonic()
    cached = _member_cache.get(key)
    if cached is not None and now - cached[1] < _MEMBER_CACHE_TTL:
        return cached[0]
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.role, s.status
                      FROM school_members m
                      JOIN schools s ON s.id = m.school_id
                     WHERE m.school_id = %s AND m.uid = %s AND m.status = 'active'
                    """,
                    (school_id, uid),
                )
                row = cur.fetchone()
    except Exception:
        if cached is not None:
            return cached[0]
        raise HTTPException(status_code=503, detail="Could not verify your school access. Please try again.")
    membership = (row["role"], row["status"]) if row else None
    _member_cache[key] = (membership, now)
    return membership


def resolve_school_ctx(uid: str, school_id: str, roles: tuple[str, ...] = ALL_ROLES) -> SchoolCtx:
    sid = parse_school_id(school_id)
    membership = load_membership(uid, sid)
    if membership is None or membership[1] == "terminated":
        raise school_not_found()
    role, status = membership
    if status == "suspended":
        raise HTTPException(status_code=403, detail={
            "error": "school_access_suspended",
            "message": "This school's ECALT access is suspended. Contact ECALT support.",
        })
    if role not in roles:
        raise HTTPException(status_code=403, detail={
            "error": "school_role_required",
            "message": "You don't have permission to do this in this school.",
            "required_roles": list(roles),
        })
    return SchoolCtx(uid=uid, school_id=sid, role=role, school_status=status)


def school_member(*roles: str) -> Callable[..., SchoolCtx]:
    """Dependency for /schools/{school_id}/… routes. Staff act as their own
    account (never a family profile or an impersonated user), with the parent
    PIN unlock when their account has family profiles."""
    allowed = roles or ALL_ROLES

    def _dependency(school_id: str, uid: str = Depends(get_parent_session)) -> SchoolCtx:
        return resolve_school_ctx(uid, school_id, allowed)

    return _dependency
