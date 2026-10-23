"""Course assignments and the student home (plans/school-courses M5, §9).

A teacher assigns a *published* school course to one of their classes. The
assignment carries an optional due date and two per-class settings:

- ``tutor_enabled`` (default True)  — may students use the in-course tutor?
- ``quiz_required`` (default False) — must a step's quiz be passed to complete it?

Who may read a course is still decided by ``services.journey_access`` (an
assignment to one of the student's active classes); this module only writes the
assignments and reads them back for staff (the Courses tab) and for students
(the home screen). Settings are enforced in the chat and progress endpoints via
``student_assignment_settings`` (SC-503).
"""
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import SchoolCtx, is_school_student_uid, load_class, uuid_or_404
from app.services.journey_access import invalidate_journey_access

# Default per-assignment settings. The teacher can turn the tutor off or make
# quizzes mandatory per class; everything else about the course is fixed at
# publish time.
_DEFAULT_SETTINGS = {"tutor_enabled": True, "quiz_required": False}


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def _clean_settings(raw: Optional[dict]) -> dict:
    """Keep only the known booleans, falling back to the defaults."""
    raw = raw or {}
    return {
        "tutor_enabled": bool(raw.get("tutor_enabled", _DEFAULT_SETTINGS["tutor_enabled"])),
        "quiz_required": bool(raw.get("quiz_required", _DEFAULT_SETTINGS["quiz_required"])),
    }


def _assignment_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": "assignment_not_found", "message": "This assignment no longer exists.",
    })


# ── Staff: assign / list / update / unassign (SC-501) ─────────────────────────

def _require_publishable_course(cur, school_id: str, journey_id: str) -> None:
    """The journey must be a course of this school and currently published."""
    cur.execute(
        "SELECT status FROM school_courses WHERE journey_id = %s AND school_id = %s",
        (journey_id, school_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": "course_not_found", "message": "Course not found.",
        })
    if row["status"] != "published":
        raise HTTPException(status_code=409, detail={
            "error": "course_not_published",
            "message": "Only a published course can be assigned to a class.",
        })


def assign_course(ctx: SchoolCtx, class_id: str, journey_id: str,
                  due_at: Optional[datetime], settings: Optional[dict]) -> dict:
    """Assign a published course to a class. 409 ``already_assigned`` if the
    class already has an active assignment of this course."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    settings = _clean_settings(settings)
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = load_class(ctx, class_id, manage=True, cur=cur)
            _require_publishable_course(cur, ctx.school_id, journey_id)
            cur.execute(
                """
                SELECT 1 FROM course_assignments
                 WHERE class_id = %s AND journey_id = %s AND status = 'active'
                """,
                (cls["id"], journey_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "already_assigned",
                    "message": "This course is already assigned to this class.",
                })
            cur.execute(
                """
                INSERT INTO course_assignments
                       (school_id, class_id, journey_id, assigned_by, due_at, settings)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id, journey_id, due_at, settings, assigned_at
                """,
                (ctx.school_id, cls["id"], journey_id, ctx.uid, due_at, _json(settings)),
            )
            row = cur.fetchone()
    # A newly-assigned course becomes readable to the class's students.
    invalidate_journey_access(journey_id=journey_id)
    return _assignment_row(row)


def list_class_assignments(ctx: SchoolCtx, class_id: str) -> list[dict]:
    """Active assignments for a class, each with course meta and a progress
    summary across the class's enrolled students (§9, SC-505 light)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = load_class(ctx, class_id, cur=cur)
            cur.execute(
                """
                SELECT a.id, a.journey_id, a.due_at, a.settings, a.assigned_at,
                       j.title, j.icon,
                       jsonb_array_length(COALESCE(j.steps, '[]'::jsonb)) AS total_steps,
                       u.display_name AS assigned_by_name
                  FROM course_assignments a
                  JOIN journeys j ON j.id = a.journey_id
                  LEFT JOIN users u ON u.uid = a.assigned_by
                 WHERE a.class_id = %s AND a.school_id = %s AND a.status = 'active'
                 ORDER BY a.assigned_at DESC
                """,
                (cls["id"], ctx.school_id),
            )
            assignments = cur.fetchall()
            cur.execute(
                """
                SELECT a.journey_id, e.student_uid,
                       COUNT(up.step_id) AS done
                  FROM course_assignments a
                  JOIN class_enrollments e
                    ON e.class_id = a.class_id AND e.removed_at IS NULL
                  LEFT JOIN user_progress up
                    ON up.uid = e.student_uid AND up.journey_id = a.journey_id
                 WHERE a.class_id = %s AND a.school_id = %s AND a.status = 'active'
                 GROUP BY a.journey_id, e.student_uid
                """,
                (cls["id"], ctx.school_id),
            )
            done_rows = cur.fetchall()

    per_journey: dict[str, list[int]] = {}
    for r in done_rows:
        per_journey.setdefault(r["journey_id"], []).append(int(r["done"]))

    out = []
    for a in assignments:
        total = a["total_steps"] or 0
        counts = per_journey.get(a["journey_id"], [])
        out.append({
            **_assignment_row(a),
            "title": a["title"],
            "icon": a["icon"],
            "total_steps": total,
            "assigned_by_name": a["assigned_by_name"],
            "progress": _summarise(counts, total),
        })
    return out


def _summarise(done_counts: list[int], total_steps: int) -> dict:
    """Class-level progress summary for one assignment."""
    enrolled = len(done_counts)
    if not enrolled:
        return {"enrolled": 0, "started": 0, "completed": 0, "avg_percent": 0}
    started = sum(1 for d in done_counts if d > 0)
    completed = sum(1 for d in done_counts if total_steps and d >= total_steps)
    if total_steps:
        avg = sum(min(d / total_steps, 1.0) for d in done_counts) / enrolled
    else:
        avg = 0.0
    return {"enrolled": enrolled, "started": started, "completed": completed,
            "avg_percent": round(avg * 100)}


def update_assignment(ctx: SchoolCtx, class_id: str, assignment_id: str, patch: dict) -> dict:
    """Change the due date and/or settings of an active assignment. ``patch``
    holds only the fields the caller sent (``due_at`` present → set it, even to
    None; ``tutor_enabled`` / ``quiz_required`` present → merge)."""
    assignment_id = uuid_or_404(assignment_id, "assignment_not_found")
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = load_class(ctx, class_id, manage=True, cur=cur)
            cur.execute(
                """
                SELECT id, journey_id, due_at, settings, assigned_at
                  FROM course_assignments
                 WHERE id = %s AND class_id = %s AND school_id = %s AND status = 'active'
                """,
                (assignment_id, cls["id"], ctx.school_id),
            )
            row = cur.fetchone()
            if not row:
                raise _assignment_not_found()

            sets, params = [], []
            if "due_at" in patch:
                sets.append("due_at = %s")
                params.append(patch["due_at"])
            setting_keys = {k: patch[k] for k in ("tutor_enabled", "quiz_required") if k in patch}
            if setting_keys:
                merged = _clean_settings({**(row["settings"] or {}), **setting_keys})
                sets.append("settings = %s::jsonb")
                params.append(_json(merged))

            if sets:
                params.extend([assignment_id, cls["id"], ctx.school_id])
                cur.execute(
                    f"""
                    UPDATE course_assignments SET {', '.join(sets)}
                     WHERE id = %s AND class_id = %s AND school_id = %s
                    RETURNING id, journey_id, due_at, settings, assigned_at
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
    return _assignment_row(row)


def unassign(ctx: SchoolCtx, class_id: str, assignment_id: str) -> None:
    """Archive an assignment (students lose the course; their progress is
    kept so it reappears if re-assigned)."""
    assignment_id = uuid_or_404(assignment_id, "assignment_not_found")
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = load_class(ctx, class_id, manage=True, cur=cur)
            cur.execute(
                """
                UPDATE course_assignments
                   SET status = 'archived', archived_at = now()
                 WHERE id = %s AND class_id = %s AND school_id = %s AND status = 'active'
                RETURNING journey_id
                """,
                (assignment_id, cls["id"], ctx.school_id),
            )
            row = cur.fetchone()
    if not row:
        raise _assignment_not_found()
    invalidate_journey_access(journey_id=row["journey_id"])


def _assignment_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "journey_id": row["journey_id"],
        "due_at": _iso(row["due_at"]),
        "settings": _clean_settings(row["settings"]),
        "assigned_at": _iso(row["assigned_at"]),
    }


# ── Student home (SC-502) ─────────────────────────────────────────────────────

def student_home(uid: str) -> dict:
    """The student's classes, each with its assigned published courses, a
    completion ratio, due date and the lead teacher's name. Empty for anyone
    who isn't an active school student."""
    if not is_school_student_uid(uid):
        return {"classes": []}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id AS class_id, c.name AS class_name, c.grade,
                       a.id AS assignment_id, a.journey_id, a.due_at, a.settings,
                       sc.status AS course_status,
                       j.title, j.icon, j.description, j.hero_image_url,
                       jsonb_array_length(COALESCE(j.steps, '[]'::jsonb)) AS total_steps,
                       (SELECT COUNT(*) FROM user_progress up
                          WHERE up.uid = %s AND up.journey_id = a.journey_id) AS done_steps,
                       lt.teacher_name
                  FROM class_enrollments e
                  JOIN classes c       ON c.id = e.class_id AND c.archived_at IS NULL
                  JOIN schools s       ON s.id = c.school_id AND s.status IN ('onboarding', 'active')
                  LEFT JOIN course_assignments a ON a.class_id = c.id AND a.status = 'active'
                  LEFT JOIN school_courses sc ON sc.journey_id = a.journey_id
                  LEFT JOIN journeys j      ON j.id = a.journey_id
                  LEFT JOIN LATERAL (
                        SELECT u.display_name AS teacher_name
                          FROM class_teachers ct
                          JOIN users u ON u.uid = ct.uid
                         WHERE ct.class_id = c.id
                         ORDER BY (ct.role = 'lead') DESC, ct.added_at
                         LIMIT 1
                  ) lt ON TRUE
                 WHERE e.student_uid = %s AND e.removed_at IS NULL
                 ORDER BY c.name, a.due_at NULLS LAST, j.title
                """,
                (uid, uid),
            )
            rows = cur.fetchall()

    classes: dict[str, dict] = {}
    for r in rows:
        cls = classes.get(r["class_id"])
        if cls is None:
            cls = classes[r["class_id"]] = {
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "grade": r["grade"],
                "teacher_name": r["teacher_name"],
                "courses": [],
            }
        # A class with no active assignment, or one pointing at a course that
        # isn't published, still lists the class but contributes no card.
        if not r["journey_id"] or r["course_status"] != "published":
            continue
        total = r["total_steps"] or 0
        done = min(int(r["done_steps"]), total) if total else 0
        cls["courses"].append({
            "assignment_id": str(r["assignment_id"]),
            "journey_id": r["journey_id"],
            "title": r["title"],
            "icon": r["icon"],
            "description": r["description"],
            "hero_image_url": r["hero_image_url"],
            "total_steps": total,
            "done_steps": done,
            "percent": round(done / total * 100) if total else 0,
            "completed": bool(total) and done >= total,
            "due_at": _iso(r["due_at"]),
            "tutor_enabled": _clean_settings(r["settings"])["tutor_enabled"],
        })
    return {"classes": list(classes.values())}


# ── Settings enforcement (SC-503) ─────────────────────────────────────────────

def student_assignment_settings(uid: str, journey_id: str) -> dict:
    """The effective settings for a student on a course, aggregated across every
    active assignment to one of their classes. The tutor is available if *any*
    class allows it (permissive); a quiz is required if *any* class requires it
    (strict). Defaults apply when the student isn't assigned the course."""
    if not is_school_student_uid(uid):
        return dict(_DEFAULT_SETTINGS)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.settings
                  FROM course_assignments a
                  JOIN class_enrollments e
                    ON e.class_id = a.class_id AND e.removed_at IS NULL
                  JOIN classes c ON c.id = a.class_id AND c.archived_at IS NULL
                 WHERE a.journey_id = %s AND a.status = 'active' AND e.student_uid = %s
                """,
                (journey_id, uid),
            )
            rows = cur.fetchall()
    if not rows:
        return dict(_DEFAULT_SETTINGS)
    settings = [_clean_settings(r["settings"]) for r in rows]
    return {
        "tutor_enabled": any(s["tutor_enabled"] for s in settings),
        "quiz_required": any(s["quiz_required"] for s in settings),
    }


def student_tutor_allowed(uid: str, journey_id: str) -> bool:
    return student_assignment_settings(uid, journey_id)["tutor_enabled"]


def student_quiz_required(uid: str, journey_id: str) -> bool:
    return student_assignment_settings(uid, journey_id)["quiz_required"]


def _json(value) -> str:
    import json
    return json.dumps(value)
