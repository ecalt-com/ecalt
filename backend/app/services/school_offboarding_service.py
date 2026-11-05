"""School offboarding (SC-803, DPA §9.2).

A terminated school keeps its data for a grace period (SCHOOL_OFFBOARDING_GRACE_DAYS,
30 by default) so it can export it. After that the nightly job deletes:

- every student: their account and learner data (account_service cascade), their
  consent record pseudonymised, their Firebase login purged;
- the school's courses (journeys with this school_id) and everything keyed to them;
- uploaded documents in the `school-materials` bucket and course hero images;
- the school row itself, which cascades staff memberships, invites, classes,
  documents/chunks, jobs, usage and the rest.

Kept: `school_audit_log` (it has no FK to schools) with a final
`school.data_deleted` row, and the pseudonymised consent events. Staff keep
their own ECALT accounts — only their membership of this school goes.

Order matters for retries: stored files go first and must all delete, or the
run stops before touching the database so the paths are still there to retry.
Every step is idempotent; the next night picks up whatever is left.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

# Tables keyed by journey_id that don't cascade from journeys (or only partly).
# Student rows are gone already; these catch staff previews and anything else.
_JOURNEY_TABLES = (
    "concept_interactions", "visual_events", "step_feedback", "quiz_quality_log",
    "quiz_results", "quiz_sessions", "user_progress", "step_content", "journey_likes",
)

# Every table that holds a school_id, for the "nothing remains" check.
_SCHOOL_TABLES = (
    "schools", "school_members", "school_invites", "school_students", "classes",
    "class_teachers", "class_enrollments", "school_courses", "course_sources",
    "course_assignments", "source_documents", "school_jobs", "school_usage",
    "school_course_usage", "school_student_daily_usage", "journeys",
)


class OffboardingError(Exception):
    pass


def grace_days() -> int:
    return int(settings.SCHOOL_OFFBOARDING_GRACE_DAYS)


def due_school_ids() -> list[str]:
    """Terminated schools whose grace period has ended."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM schools
                 WHERE status = 'terminated'
                   AND terminated_at IS NOT NULL
                   AND terminated_at <= now() - make_interval(days => %s)
                 ORDER BY terminated_at
                """,
                (grace_days(),),
            )
            return [str(r["id"]) for r in cur.fetchall()]


def remaining(school_id: str) -> dict[str, int]:
    """Rows still holding this school's data (empty dict = nothing left).
    The audit log is excluded — it is kept on purpose."""
    left: dict[str, int] = {}
    with get_db() as conn:
        with conn.cursor() as cur:
            for table in _SCHOOL_TABLES:
                col = "id" if table == "schools" else "school_id"
                cur.execute(f"SELECT count(*) AS n FROM {table} WHERE {col} = %s", (school_id,))
                n = cur.fetchone()["n"]
                if n:
                    left[table] = n
            cur.execute(
                "SELECT count(*) AS n FROM course_versions v JOIN journeys j ON j.id = v.journey_id "
                "WHERE j.school_id = %s", (school_id,))
            if cur.fetchone()["n"]:
                left["course_versions"] = 1
    return left


def _delete_files(school_id: str) -> int:
    """Delete stored documents and hero images. Raises if any delete fails."""
    from app.services import image_service
    from app.services import school_storage_service as storage
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT storage_path FROM source_documents WHERE school_id = %s "
                        "AND storage_path IS NOT NULL", (school_id,))
            paths = [r["storage_path"] for r in cur.fetchall()]
            cur.execute("SELECT hero_image_url FROM journeys WHERE school_id = %s "
                        "AND hero_image_url IS NOT NULL", (school_id,))
            heroes = [r["hero_image_url"] for r in cur.fetchall()]
    if paths and not storage.storage_enabled():
        raise OffboardingError("document storage is not configured; can't delete stored files")
    for path in paths:
        storage.delete(path, strict=True)
    for url in heroes:
        image_service.delete_journey_image(url)
    return len(paths) + len(heroes)


async def _delete_students(school_id: str) -> tuple[int, int]:
    """Erase every student of the school. Returns (deleted, firebase_failures)."""
    from app.services.account_service import delete_user_account
    from app.services.firebase_admin import purge_login
    from app.services.school_student_service import _invalidate_student
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT uid FROM school_students WHERE school_id = %s", (school_id,))
            uids = [r["uid"] for r in cur.fetchall()]
    failures = 0
    for uid in uids:
        delete_user_account(uid, consent_event={
            "action": "revoked", "method": "school_offboarding", "details": {"school_id": school_id},
        })
        _invalidate_student(uid)
        try:
            if not await purge_login(uid):
                failures += 1
        except Exception as e:  # the DB data is gone; a stray login can't sign in without a custom token
            failures += 1
            logger.warning("offboarding: firebase purge failed for a student of %s: %s", school_id, e)
    return len(uids), failures


def _delete_rows(school_id: str, counts: dict) -> Optional[dict]:
    """Delete the courses and the school row in one transaction. Returns the
    school's name/dates for the audit row, or None if the school is gone."""
    from app.core.school_auth import invalidate_school_member_cache
    from app.services.school_service import school_audit
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, terminated_at FROM schools WHERE id = %s FOR UPDATE", (school_id,))
            school = cur.fetchone()
            if not school:
                return None
            cur.execute("SELECT uid FROM school_members WHERE school_id = %s", (school_id,))
            staff = [r["uid"] for r in cur.fetchall()]
            cur.execute("SELECT count(*) AS n FROM journeys WHERE school_id = %s", (school_id,))
            counts["courses"] = cur.fetchone()["n"]
            school_journeys = "SELECT id FROM journeys WHERE school_id = %s"
            for table in _JOURNEY_TABLES:
                cur.execute(f"DELETE FROM {table} WHERE journey_id IN ({school_journeys})", (school_id,))
            cur.execute(f"UPDATE journeys SET forked_from_id = NULL WHERE forked_from_id IN ({school_journeys})",
                        (school_id,))
            cur.execute("DELETE FROM journeys WHERE school_id = %s", (school_id,))
            cur.execute("DELETE FROM schools WHERE id = %s", (school_id,))
            counts["staff_memberships"] = len(staff)
            school_audit(cur, school_id, None, "school.data_deleted", "school", school_id, {
                **counts,
                "name": school["name"],
                "terminated_at": school["terminated_at"].isoformat() if school["terminated_at"] else None,
            })
    invalidate_school_member_cache(school_id=school_id)
    return dict(school)


async def purge_school(school_id: str) -> dict:
    """Delete everything a terminated school left behind. Refuses a school
    that isn't terminated. Safe to re-run."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM schools WHERE id = %s", (school_id,))
            row = cur.fetchone()
    if not row:
        return {"school_id": school_id, "status": "already_deleted"}
    if row["status"] != "terminated":
        raise OffboardingError(f"school {school_id} is {row['status']}, not terminated")

    counts: dict = {"files": _delete_files(school_id)}
    counts["students"], counts["firebase_failures"] = await _delete_students(school_id)
    _delete_rows(school_id, counts)

    left = remaining(school_id)
    if left:
        logger.error("offboarding: school %s still has rows after deletion: %s", school_id, left)
        return {"school_id": school_id, "status": "incomplete", "remaining": left, **counts}
    logger.info("offboarding: deleted school %s (%s)", school_id, counts)
    return {"school_id": school_id, "status": "deleted", **counts}


async def run_due() -> list[dict]:
    """Nightly entry point: purge every school past its grace period. One
    school failing doesn't stop the others."""
    results = []
    for school_id in due_school_ids():
        try:
            results.append(await purge_school(school_id))
        except Exception as e:
            logger.error("offboarding: school %s failed: %s", school_id, e)
            results.append({"school_id": school_id, "status": "failed", "error": str(e)[:200]})
    return results
