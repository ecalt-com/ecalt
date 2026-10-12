"""Classes, class teachers, enrollments, join codes and login cards
(plans/school-courses M2: SC-203, SC-204).

Any staff member may create a class (becoming its lead teacher) and read the
school's classes. Changing a class — details, teachers, students, join code,
login cards — needs a school admin or one of the class's teachers
(core.school_auth.load_class(manage=True)).
"""
import secrets
from typing import Any, Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import SchoolCtx, load_class
from app.services.profile_service import hash_pin
from app.services.school_service import school_audit
from app.services.school_student_service import generate_secret, new_badge_token

# No look-alikes: no I, L, O, 0, 1.
JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 8


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


def normalize_join_code(raw: str) -> Optional[str]:
    """Upper-case, drop spaces and dashes; None if it can't be a join code."""
    code = "".join(ch for ch in (raw or "").upper() if ch not in " -")
    if len(code) != JOIN_CODE_LENGTH or any(ch not in JOIN_CODE_ALPHABET for ch in code):
        return None
    return code


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _err(status: int, error: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message})


def _class_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "grade": row["grade"],
        "subject": row["subject"],
        "academic_year": row["academic_year"],
        "join_code": row["join_code"],
        "settings": row.get("settings") or {},
        "archived": row.get("archived_at") is not None,
        "created_at": _iso(row.get("created_at")),
        "is_mine": bool(row.get("is_teacher")),
        "student_count": int(row.get("student_count") or 0),
        "teachers": row.get("teachers") or [],
    }


def insert_class(cur, ctx: SchoolCtx, name: str, grade: Optional[int], subject: Optional[str],
                 academic_year: Optional[str]) -> dict:
    """Create a class in the caller's transaction; the creator becomes its lead teacher."""
    for _ in range(5):
        code = new_join_code()
        cur.execute("SELECT 1 FROM classes WHERE join_code = %s", (code,))
        if not cur.fetchone():
            break
    cur.execute(
        """
        INSERT INTO classes (school_id, name, grade, subject, academic_year, join_code, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (ctx.school_id, name.strip(), grade, subject, academic_year, code, ctx.uid),
    )
    row = dict(cur.fetchone())
    cur.execute(
        "INSERT INTO class_teachers (class_id, school_id, uid, role) VALUES (%s, %s, %s, 'lead')",
        (row["id"], ctx.school_id, ctx.uid),
    )
    school_audit(cur, ctx.school_id, ctx.uid, "class.created", "class", str(row["id"]))
    row["is_teacher"] = True
    return _class_out(row)


_LIST_SQL = """
    SELECT c.*,
           EXISTS (SELECT 1 FROM class_teachers t WHERE t.class_id = c.id AND t.uid = %s) AS is_teacher,
           (SELECT COUNT(*) FROM class_enrollments e
              JOIN school_students s ON s.uid = e.student_uid AND s.status = 'active'
             WHERE e.class_id = c.id AND e.removed_at IS NULL) AS student_count,
           COALESCE((SELECT json_agg(json_build_object('uid', t.uid, 'role', t.role,
                                                       'display_name', u.display_name) ORDER BY t.role DESC, u.display_name)
                       FROM class_teachers t JOIN users u ON u.uid = t.uid
                      WHERE t.class_id = c.id), '[]'::json) AS teachers
      FROM classes c
"""


def list_classes(ctx: SchoolCtx, include_archived: bool = False) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _LIST_SQL + f"""
                 WHERE c.school_id = %s {"" if include_archived else "AND c.archived_at IS NULL"}
                 ORDER BY c.archived_at IS NOT NULL, lower(c.name)
                """,
                (ctx.uid, ctx.school_id),
            )
            return [_class_out(dict(r)) for r in cur.fetchall()]


def create_class(ctx: SchoolCtx, name: str, grade: Optional[int], subject: Optional[str],
                 academic_year: Optional[str]) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            created = insert_class(cur, ctx, name, grade, subject, academic_year)
    return get_class(ctx, created["id"])


def get_class(ctx: SchoolCtx, class_id: str) -> dict:
    cls = load_class(ctx, class_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_LIST_SQL + " WHERE c.id = %s", (ctx.uid, cls["id"]))
            out = _class_out(dict(cur.fetchone()))
            cur.execute(
                """
                SELECT s.uid, s.display_name, s.grade, s.external_ref, s.avatar, s.status, s.secret_kind,
                       (s.secret_hash IS NOT NULL) AS has_secret, (s.badge_token_hash IS NOT NULL) AS has_badge,
                       s.locked_until, e.enrolled_at
                  FROM class_enrollments e
                  JOIN school_students s ON s.uid = e.student_uid
                 WHERE e.class_id = %s AND e.removed_at IS NULL
                 ORDER BY lower(s.display_name)
                """,
                (cls["id"],),
            )
            out["students"] = [{**dict(r), "locked_until": _iso(r["locked_until"]),
                                "enrolled_at": _iso(r["enrolled_at"])} for r in cur.fetchall()]
    out["can_manage"] = ctx.is_admin or out["is_mine"]
    return out


def update_class(ctx: SchoolCtx, class_id: str, changes: dict) -> dict:
    cls = load_class(ctx, class_id, manage=True)
    cols = [c for c in ("name", "grade", "subject", "academic_year") if c in changes]
    with get_db() as conn:
        with conn.cursor() as cur:
            if cols:
                cur.execute(
                    f"UPDATE classes SET {', '.join(f'{c} = %s' for c in cols)} WHERE id = %s AND school_id = %s",
                    [changes[c] for c in cols] + [cls["id"], ctx.school_id],
                )
                school_audit(cur, ctx.school_id, ctx.uid, "class.updated", "class", str(cls["id"]),
                             {"fields": cols})
    return get_class(ctx, str(cls["id"]))


def archive_class(ctx: SchoolCtx, class_id: str) -> None:
    from app.services.journey_access import invalidate_journey_access
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE classes SET archived_at = now() WHERE id = %s AND school_id = %s AND archived_at IS NULL",
                        (cls["id"], ctx.school_id))
            school_audit(cur, ctx.school_id, ctx.uid, "class.archived", "class", str(cls["id"]))
    invalidate_journey_access()


def rotate_join_code(ctx: SchoolCtx, class_id: str) -> dict:
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            code = new_join_code()
            cur.execute("UPDATE classes SET join_code = %s WHERE id = %s AND school_id = %s",
                        (code, cls["id"], ctx.school_id))
            school_audit(cur, ctx.school_id, ctx.uid, "class.code_rotated", "class", str(cls["id"]))
    return {"join_code": code}


# ── Teachers ──────────────────────────────────────────────────────────────────

def add_teacher(ctx: SchoolCtx, class_id: str, uid: str, role: str) -> dict:
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM school_members WHERE school_id = %s AND uid = %s AND status = 'active'",
                (ctx.school_id, uid),
            )
            if not cur.fetchone():
                raise _err(404, "member_not_found", "That person isn't on this school's staff.")
            cur.execute(
                """
                INSERT INTO class_teachers (class_id, school_id, uid, role) VALUES (%s, %s, %s, %s)
                ON CONFLICT (class_id, uid) DO UPDATE SET role = EXCLUDED.role
                """,
                (cls["id"], ctx.school_id, uid, role),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "class.teacher_added", "class", str(cls["id"]),
                         {"teacher": uid, "role": role})
    return get_class(ctx, str(cls["id"]))


def remove_teacher(ctx: SchoolCtx, class_id: str, uid: str) -> None:
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM class_teachers WHERE class_id = %s AND uid = %s RETURNING uid",
                        (cls["id"], uid))
            if not cur.fetchone():
                raise _err(404, "member_not_found", "That person doesn't teach this class.")
            school_audit(cur, ctx.school_id, ctx.uid, "class.teacher_removed", "class", str(cls["id"]),
                         {"teacher": uid})


# ── Students ──────────────────────────────────────────────────────────────────

def enroll_students(ctx: SchoolCtx, class_id: str, student_uids: list[str]) -> dict:
    from app.services.journey_access import invalidate_journey_access
    cls = load_class(ctx, class_id, manage=True)
    if cls["archived_at"] is not None:
        raise _err(409, "class_archived", "This class is archived.")
    uids = list(dict.fromkeys(student_uids))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid FROM school_students WHERE school_id = %s AND uid = ANY(%s) AND status = 'active'",
                (ctx.school_id, uids),
            )
            found = {r["uid"] for r in cur.fetchall()}
            if found != set(uids):
                raise _err(404, "student_not_found", "Student not found.")
            for uid in uids:
                cur.execute(
                    """
                    INSERT INTO class_enrollments (class_id, school_id, student_uid) VALUES (%s, %s, %s)
                    ON CONFLICT (class_id, student_uid) DO UPDATE SET removed_at = NULL, enrolled_at = now()
                    """,
                    (cls["id"], ctx.school_id, uid),
                )
            school_audit(cur, ctx.school_id, ctx.uid, "class.students_added", "class", str(cls["id"]),
                         {"count": len(uids)})
    for uid in uids:
        invalidate_journey_access(uid=uid)
    return get_class(ctx, str(cls["id"]))


def unenroll_student(ctx: SchoolCtx, class_id: str, student_uid: str) -> None:
    from app.services.journey_access import invalidate_journey_access
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE class_enrollments SET removed_at = now()
                 WHERE class_id = %s AND student_uid = %s AND removed_at IS NULL
                RETURNING student_uid
                """,
                (cls["id"], student_uid),
            )
            if not cur.fetchone():
                raise _err(404, "student_not_found", "That student isn't in this class.")
            school_audit(cur, ctx.school_id, ctx.uid, "class.student_removed", "class", str(cls["id"]),
                         {"student": student_uid})
    invalidate_journey_access(uid=student_uid)


# ── Login cards ───────────────────────────────────────────────────────────────

def login_cards(ctx: SchoolCtx, class_id: str, student_uids: Optional[list[str]], reset: bool) -> dict:
    """Printable sign-in cards. Secrets are stored hashed, so a card can only
    show a secret that is generated now: with reset=True every chosen student
    gets a new picture/PIN and QR badge (old ones stop working); with
    reset=False only students who have none yet get one, and the others'
    cards show no secret."""
    cls = load_class(ctx, class_id, manage=True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM schools WHERE id = %s", (ctx.school_id,))
            school_name = cur.fetchone()["name"]
            cur.execute(
                """
                SELECT s.uid, s.display_name, s.avatar, s.secret_kind, s.secret_hash, s.badge_token_hash
                  FROM class_enrollments e
                  JOIN school_students s ON s.uid = e.student_uid AND s.status = 'active'
                 WHERE e.class_id = %s AND e.removed_at IS NULL
                 ORDER BY lower(s.display_name)
                 FOR UPDATE OF s
                """,
                (cls["id"],),
            )
            students = [dict(r) for r in cur.fetchall()]
            if student_uids is not None:
                wanted = set(student_uids)
                students = [s for s in students if s["uid"] in wanted]
                if {s["uid"] for s in students} != wanted:
                    raise _err(404, "student_not_found", "Student not found in this class.")
            cards = []
            regenerated = 0
            for s in students:
                card = {"uid": s["uid"], "display_name": s["display_name"], "avatar": s["avatar"],
                        "secret_kind": s["secret_kind"], "secret": None, "badge_token": None}
                if reset or not s["secret_hash"]:
                    canonical, card["secret"] = generate_secret(s["secret_kind"])
                    card["badge_token"], badge_hash = new_badge_token()
                    cur.execute(
                        """
                        UPDATE school_students
                           SET secret_hash = %s, badge_token_hash = %s, failed_attempts = 0, locked_until = NULL
                         WHERE uid = %s
                        """,
                        (hash_pin(canonical), badge_hash, s["uid"]),
                    )
                    regenerated += 1
                cards.append(card)
            school_audit(cur, ctx.school_id, ctx.uid, "class.login_cards", "class", str(cls["id"]),
                         {"cards": len(cards), "new_secrets": regenerated})
    return {
        "school_name": school_name,
        "class": {"id": str(cls["id"]), "name": cls["name"], "join_code": cls["join_code"]},
        "cards": cards,
    }
