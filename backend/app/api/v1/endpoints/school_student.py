"""Student-facing school routes (plans/school-courses M5 §9, SC-502).

Mounted under /school-student. School students reach these with their
custom-token sign-in; the route allowlist in core/school_auth.py lets them
through, and every journey they open is still checked by journey_access. The
home screen lists their classes and assigned courses with completion.
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_active_user
from app.services import school_assignment_service as assignments

router = APIRouter()


@router.get("/home", summary="A student's classes and the courses assigned to them")
def student_home(uid: str = Depends(get_active_user)):
    return assignments.student_home(uid)
