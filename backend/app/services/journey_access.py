"""Who may read a journey (plans/school-courses README §3.4, invariant I3).

Non-school journeys keep today's open-by-id behaviour for everyone except
school students, who may only reach school courses assigned to one of their
active classes (decision D5). A school course is visible to staff of its school
and to those students; anyone else gets a 404, so its existence never leaks.

Call assert_can_read_journey() before any read, write, or model call that takes
a journey id. It returns the journey's school id (None for non-school journeys)
so callers can apply the school-course rules: no automatic regeneration, no
marketplace operations.
"""
import time
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import (
    OPEN_SCHOOL_STATUSES,
    is_school_student_uid,
    load_membership,
    student_not_allowed,
)

_TTL = 60.0
# journey_id -> (school_id or None, cached_at). A journey's school never changes.
_school_cache: dict[str, tuple[Optional[str], float]] = {}
# (uid, journey_id) -> (allowed, cached_at)
_access_cache: dict[tuple[str, str], tuple[bool, float]] = {}


def journey_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Journey not found")


def remember_journey_school(journey_id: str, school_id: Optional[str]) -> None:
    """Prime the cache when a school course is created."""
    _school_cache[journey_id] = (school_id, time.monotonic())


def invalidate_journey_access(uid: Optional[str] = None, journey_id: Optional[str] = None) -> None:
    """Call after enrollment, assignment or course-status changes. With no
    arguments it clears everything."""
    for key in list(_access_cache):
        if (uid is None or key[0] == uid) and (journey_id is None or key[1] == journey_id):
            _access_cache.pop(key, None)


def journey_school_id(journey_id: str) -> Optional[str]:
    """The school that owns a journey, or None (non-school or unknown id).
    Fails closed: a DB error with nothing cached is a 503, never a guess."""
    now = time.monotonic()
    cached = _school_cache.get(journey_id)
    if cached is not None and now - cached[1] < _TTL:
        return cached[0]
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT school_id FROM journeys WHERE id = %s", (journey_id,))
                row = cur.fetchone()
    except Exception:
        if cached is not None:
            return cached[0]
        raise HTTPException(status_code=503, detail="Could not load this journey. Please try again.")
    school_id = str(row["school_id"]) if row and row["school_id"] else None
    _school_cache[journey_id] = (school_id, now)
    return school_id


def _student_is_assigned(uid: str, journey_id: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM course_assignments a
                  JOIN class_enrollments e ON e.class_id = a.class_id AND e.removed_at IS NULL
                  JOIN classes c           ON c.id = a.class_id AND c.archived_at IS NULL
                  JOIN school_courses sc   ON sc.journey_id = a.journey_id AND sc.status = 'published'
                  JOIN school_students ss  ON ss.uid = e.student_uid AND ss.status = 'active'
                  JOIN schools s           ON s.id = a.school_id AND s.status = ANY(%s)
                 WHERE a.journey_id = %s AND a.status = 'active' AND e.student_uid = %s
                 LIMIT 1
                """,
                (list(OPEN_SCHOOL_STATUSES), journey_id, uid),
            )
            return cur.fetchone() is not None


def _is_school_staff(uid: str, school_id: str) -> bool:
    membership = load_membership(uid, school_id)
    return membership is not None and membership[1] in OPEN_SCHOOL_STATUSES


def assert_can_read_journey(uid: Optional[str], journey_id: str) -> Optional[str]:
    """Raise unless uid may read journey_id; return the journey's school id.

    - school student + non-school journey → 403 school_student_not_allowed (D5)
    - school course the caller isn't entitled to → 404
    """
    school_id = journey_school_id(journey_id)
    if is_school_student_uid(uid):
        if school_id is None:
            raise student_not_allowed()
    elif school_id is None:
        return None
    elif not uid:
        raise journey_not_found()

    key = (uid, journey_id)
    now = time.monotonic()
    cached = _access_cache.get(key)
    if cached is not None and now - cached[1] < _TTL:
        allowed = cached[0]
    else:
        try:
            if is_school_student_uid(uid):
                allowed = _student_is_assigned(uid, journey_id)
            else:
                allowed = _is_school_staff(uid, school_id)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="Could not load this journey. Please try again.")
        _access_cache[key] = (allowed, now)
    if not allowed:
        raise journey_not_found()
    return school_id


def student_assigned_journey_ids(uid: str) -> list[str]:
    """Published school courses assigned to the student's active classes."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT a.journey_id
                  FROM course_assignments a
                  JOIN class_enrollments e ON e.class_id = a.class_id AND e.removed_at IS NULL
                  JOIN classes c           ON c.id = a.class_id AND c.archived_at IS NULL
                  JOIN school_courses sc   ON sc.journey_id = a.journey_id AND sc.status = 'published'
                  JOIN school_students ss  ON ss.uid = e.student_uid AND ss.status = 'active'
                  JOIN schools s           ON s.id = a.school_id AND s.status = ANY(%s)
                 WHERE e.student_uid = %s AND a.status = 'active'
                """,
                (list(OPEN_SCHOOL_STATUSES), uid),
            )
            return [r["journey_id"] for r in cur.fetchall()]
