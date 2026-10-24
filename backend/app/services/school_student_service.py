"""School students: accounts, secrets, roster import (plans/school-courses M2:
SC-201, SC-202, SC-204, SC-209).

A student is a `users` row (profile_type 'school_student', uid 'stu_<hex>', no
email) plus a `school_students` row. Students never sign up: staff create them
under the school's data processing agreement, recorded as a consent_events
'school_authorization' entry.

Secrets: a picture password (3 of 16 icons) or a 6-digit PIN, scrypt-hashed.
The plaintext is returned exactly once — when it's generated — so staff can
print login cards. QR badge tokens are long random strings stored as sha256.
"""
import csv
import hashlib
import io
import json
import logging
import re
import secrets
from typing import Any, Optional

import psycopg2.extras
from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_db
from app.core.school_auth import ADMIN_ROLES, SchoolCtx, uuid_or_404
from app.services.profile_service import check_pin, hash_pin
from app.services.school_service import effective_settings, school_audit

logger = logging.getLogger(__name__)

PICTURE_ICONS = 16
PICTURE_LENGTH = 3
PIN_LENGTH = 6
SECRET_KINDS = ("picture", "pin")
# Picture passwords (16^3 = 4096 combinations) are only for the youngest
# children (D1); older students must use a 6-digit PIN. Lockouts bound online
# guessing regardless, but this keeps the low-entropy secret off older grades.
PICTURE_MAX_GRADE = 4
# Same keys as the frontend's avatars.ts — a picture helps young children find their name.
STUDENT_AVATARS = ("fox", "owl", "panda", "octopus", "turtle", "rocket", "star", "dino")
MAX_IMPORT_ROWS = 2000


# ── Secrets ───────────────────────────────────────────────────────────────────

def default_secret_kind(grade: Optional[int]) -> str:
    """Picture passwords up to grade 4, PINs after (decision D1)."""
    return "picture" if grade is None or grade <= PICTURE_MAX_GRADE else "pin"


def resolve_secret_kind(requested: Optional[str], grade: Optional[int]) -> str:
    """The secret kind to use: an explicit choice (validated against the grade),
    else the grade-based default. Rejects a picture password for an older
    student (M3) — their known grade would otherwise get a 4096-space secret."""
    if requested == "picture" and grade is not None and grade > PICTURE_MAX_GRADE:
        raise _err(422, "picture_secret_too_old",
                   "Picture passwords are only for younger grades. Use a PIN instead.")
    return requested or default_secret_kind(grade)


def generate_secret(kind: str) -> tuple[str, Any]:
    """(canonical form to hash, value to show once)."""
    if kind == "picture":
        icons = [secrets.randbelow(PICTURE_ICONS) for _ in range(PICTURE_LENGTH)]
        return "picture:" + "-".join(map(str, icons)), icons
    pin = f"{secrets.randbelow(10 ** PIN_LENGTH):0{PIN_LENGTH}d}"
    return "pin:" + pin, pin


def canonical_secret(kind: str, value: Any) -> Optional[str]:
    """Canonical form of a secret typed at sign-in, or None if malformed."""
    if kind == "picture":
        if (not isinstance(value, list) or len(value) != PICTURE_LENGTH
                or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < PICTURE_ICONS for i in value)):
            return None
        return "picture:" + "-".join(map(str, value))
    if kind == "pin":
        if not isinstance(value, str) or not re.fullmatch(rf"\d{{{PIN_LENGTH}}}", value):
            return None
        return "pin:" + value
    return None


def verify_secret(canonical: str, stored_hash: Optional[str]) -> bool:
    return bool(stored_hash) and check_pin(canonical, stored_hash)


def new_badge_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(24)
    return token, hash_badge_token(token)


def hash_badge_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _err(status: int, error: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message, **extra})


def student_not_found() -> HTTPException:
    return _err(404, "student_not_found", "Student not found.")


def _load_school(cur, school_id: str, for_update: bool = False) -> dict:
    cur.execute(
        f"SELECT * FROM schools WHERE id = %s {'FOR UPDATE' if for_update else ''}",
        (school_id,),
    )
    return dict(cur.fetchone())


def _require_dpa(school: dict) -> None:
    if school.get("dpa_version") != settings.SCHOOL_DPA_VERSION:
        raise _err(409, "dpa_required",
                   "The school's owner must accept the data processing agreement before students can be added.")


def _active_student_count(cur, school_id: str) -> int:
    cur.execute("SELECT COUNT(*) AS n FROM school_students WHERE school_id = %s AND status = 'active'", (school_id,))
    return int(cur.fetchone()["n"])


def _require_seats(cur, school: dict, needed: int) -> None:
    available = int(school["seat_limit"]) - _active_student_count(cur, str(school["id"]))
    if needed > available:
        raise _err(409, "seat_limit_reached",
                   f"This would need {needed} seat(s); the school has {max(available, 0)} left. "
                   "Archive students who have left, or ask ECALT for more seats.",
                   seats_available=max(available, 0), seats_needed=needed)


def can_manage_students(ctx: SchoolCtx, school_settings: dict) -> bool:
    """Create, import, archive, delete (decision D9)."""
    return ctx.is_admin or bool(school_settings.get("teachers_can_create_students"))


def _require_manage(ctx: SchoolCtx, school: dict) -> None:
    if not can_manage_students(ctx, effective_settings(school.get("settings"))):
        raise _err(403, "school_role_required", "Only school admins can manage student accounts here.",
                   required_roles=list(ADMIN_ROLES))


def _teacher_class_ids(cur, ctx: SchoolCtx) -> set[str]:
    cur.execute(
        "SELECT class_id::text AS id FROM class_teachers WHERE school_id = %s AND uid = %s",
        (ctx.school_id, ctx.uid),
    )
    return {r["id"] for r in cur.fetchall()}


def _require_secret_access(cur, ctx: SchoolCtx, student_uid: str) -> None:
    """Reset a secret / rotate a badge: admins, or a teacher of one of the
    student's active classes."""
    if ctx.is_admin:
        return
    cur.execute(
        """
        SELECT 1 FROM class_enrollments e
          JOIN class_teachers t ON t.class_id = e.class_id AND t.uid = %s
         WHERE e.student_uid = %s AND e.school_id = %s AND e.removed_at IS NULL
         LIMIT 1
        """,
        (ctx.uid, student_uid, ctx.school_id),
    )
    if not cur.fetchone():
        raise _err(403, "school_role_required", "Only the student's teachers and school admins can do this.",
                   required_roles=list(ADMIN_ROLES))


def _load_student(cur, ctx: SchoolCtx, uid: str, for_update: bool = False) -> dict:
    if not uid.startswith("stu_"):
        raise student_not_found()
    cur.execute(
        f"SELECT * FROM school_students WHERE uid = %s AND school_id = %s {'FOR UPDATE' if for_update else ''}",
        (uid, ctx.school_id),
    )
    row = cur.fetchone()
    if not row:
        raise student_not_found()
    return dict(row)


def _student_out(row: dict, classes: Optional[list] = None) -> dict:
    return {
        "uid": row["uid"],
        "display_name": row["display_name"],
        "grade": row["grade"],
        "external_ref": row["external_ref"],
        "avatar": row.get("avatar"),
        "status": row["status"],
        "secret_kind": row["secret_kind"],
        "has_secret": bool(row.get("secret_hash")),
        "has_badge": bool(row.get("badge_token_hash")),
        "locked_until": _iso(row.get("locked_until")),
        "created_at": _iso(row.get("created_at")),
        "archived_at": _iso(row.get("archived_at")),
        "classes": classes if classes is not None else row.get("classes") or [],
    }


def _validate_class_ids(cur, ctx: SchoolCtx, class_ids: list[str]) -> list[str]:
    ids = [uuid_or_404(c, "class_not_found") for c in dict.fromkeys(class_ids)]
    if not ids:
        return []
    cur.execute(
        "SELECT id::text AS id FROM classes WHERE id = ANY(%s::uuid[]) AND school_id = %s AND archived_at IS NULL",
        (ids, ctx.school_id),
    )
    found = {r["id"] for r in cur.fetchall()}
    if found != set(ids):
        raise _err(404, "class_not_found", "Class not found.")
    if not ctx.is_admin:
        mine = _teacher_class_ids(cur, ctx)
        if not set(ids) <= mine:
            raise _err(403, "school_role_required", "You can only add students to classes you teach.")
    return ids


def _age_group(grade: Optional[int]) -> str:
    return "teen" if grade is not None and grade >= 7 else "child"


def _insert_students(cur, school: dict, ctx_uid: str, rows: list[dict], with_secrets: bool) -> list[dict]:
    """Insert users + school_students + consent rows in bulk. Each row:
    display_name, grade, external_ref, secret_kind. Returns created students
    with their one-time secret/badge when with_secrets."""
    if not rows:
        return []
    created = []
    users_rows, student_rows, consent_rows = [], [], []
    for r in rows:
        uid = f"stu_{secrets.token_hex(8)}"
        kind = r.get("secret_kind")
        if kind == "picture" and (r.get("grade") or 0) > PICTURE_MAX_GRADE:
            kind = None  # older students can't use a picture password (M3) — fall back to PIN
        kind = kind or default_secret_kind(r.get("grade"))
        secret_value = badge = None
        secret_hash = badge_hash = None
        if with_secrets:
            canonical, secret_value = generate_secret(kind)
            secret_hash = hash_pin(canonical)
            badge, badge_hash = new_badge_token()
        avatar = secrets.choice(STUDENT_AVATARS)
        users_rows.append((uid, r["display_name"], "school_student", "active", True, _age_group(r.get("grade")),
                           school["country"], f"school:{school['dpa_version']}"))
        student_rows.append((uid, school["id"], r["display_name"], r.get("external_ref"), r.get("grade"), avatar,
                             kind, secret_hash, badge_hash, ctx_uid))
        consent_rows.append((uid, "granted", "school_authorization", school["dpa_version"], school["country"],
                             json.dumps({"school_id": str(school["id"]), "dpa_version": school["dpa_version"]})))
        created.append({"uid": uid, "display_name": r["display_name"], "grade": r.get("grade"),
                        "external_ref": r.get("external_ref"), "avatar": avatar, "secret_kind": kind,
                        "secret": secret_value, "badge_token": badge})
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO users (uid, display_name, profile_type, account_status, onboarding_done, age_group_flag,
                           jurisdiction, consent_version, consent_given_at)
        VALUES %s
        """,
        users_rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, now())",
    )
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO school_students (uid, school_id, display_name, external_ref, grade, avatar,
                                     secret_kind, secret_hash, badge_token_hash, created_by)
        VALUES %s
        """,
        student_rows,
    )
    # consent_events is append-only; the school authorises each student.
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO consent_events (uid, action, method, policy_version, jurisdiction, details) VALUES %s",
        consent_rows,
        template="(%s, %s, %s, %s, %s, %s::jsonb)",
    )
    return created


def _enroll(cur, school_id: str, pairs: list[tuple[str, str]]) -> None:
    """(class_id, student_uid) pairs; re-enrolling clears removed_at."""
    if not pairs:
        return
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO class_enrollments (class_id, school_id, student_uid) VALUES %s
        ON CONFLICT (class_id, student_uid) DO UPDATE SET removed_at = NULL, enrolled_at = now()
        """,
        [(cid, school_id, uid) for cid, uid in pairs],
    )


def _invalidate_student(uid: str) -> None:
    from app.core.auth import invalidate_status_cache
    from app.services.journey_access import invalidate_journey_access
    invalidate_status_cache(uid)
    invalidate_journey_access(uid=uid)


# ── Queries ───────────────────────────────────────────────────────────────────

_CLASSES_AGG = """
    COALESCE((
        SELECT json_agg(json_build_object('id', c.id, 'name', c.name) ORDER BY c.name)
          FROM class_enrollments e
          JOIN classes c ON c.id = e.class_id AND c.archived_at IS NULL
         WHERE e.student_uid = s.uid AND e.removed_at IS NULL
    ), '[]'::json) AS classes
"""


def list_students(ctx: SchoolCtx, q: Optional[str], class_id: Optional[str], status: Optional[str],
                  limit: int, offset: int) -> dict:
    filters, params = ["s.school_id = %s"], [ctx.school_id]
    if q:
        filters.append("(s.display_name ILIKE %s OR s.external_ref ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if status:
        filters.append("s.status = %s")
        params.append(status)
    if class_id:
        filters.append(
            "EXISTS (SELECT 1 FROM class_enrollments e WHERE e.student_uid = s.uid AND e.class_id = %s "
            "AND e.removed_at IS NULL)"
        )
        params.append(uuid_or_404(class_id, "class_not_found"))
    where = " AND ".join(filters)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM school_students s WHERE {where}", params)
            total = int(cur.fetchone()["n"])
            cur.execute(
                f"""
                SELECT s.*, {_CLASSES_AGG}
                  FROM school_students s
                 WHERE {where}
                 ORDER BY lower(s.display_name), s.uid
                 LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = [_student_out(dict(r)) for r in cur.fetchall()]
            school = _load_school(cur, ctx.school_id)
            seats_used = _active_student_count(cur, ctx.school_id)
    return {
        "students": rows, "total": total,
        "seat_limit": school["seat_limit"], "seats_used": seats_used,
        "can_manage": can_manage_students(ctx, effective_settings(school.get("settings"))),
    }


def get_student(ctx: SchoolCtx, uid: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            _load_student(cur, ctx, uid)
            cur.execute(f"SELECT s.*, {_CLASSES_AGG} FROM school_students s WHERE s.uid = %s", (uid,))
            return _student_out(dict(cur.fetchone()))


# ── Create / update ───────────────────────────────────────────────────────────

def create_student(ctx: SchoolCtx, display_name: str, grade: Optional[int], external_ref: Optional[str],
                   secret_kind: Optional[str], class_ids: list[str]) -> dict:
    secret_kind = resolve_secret_kind(secret_kind, grade)
    with get_db() as conn:
        with conn.cursor() as cur:
            school = _load_school(cur, ctx.school_id, for_update=True)
            _require_manage(ctx, school)
            _require_dpa(school)
            _require_seats(cur, school, 1)
            ids = _validate_class_ids(cur, ctx, class_ids)
            if external_ref:
                cur.execute("SELECT 1 FROM school_students WHERE school_id = %s AND external_ref = %s",
                            (ctx.school_id, external_ref))
                if cur.fetchone():
                    raise _err(409, "external_ref_taken", "Another student already has this school reference number.")
            [student] = _insert_students(cur, school, ctx.uid, [{
                "display_name": display_name, "grade": grade, "external_ref": external_ref,
                "secret_kind": secret_kind,
            }], with_secrets=True)
            _enroll(cur, ctx.school_id, [(cid, student["uid"]) for cid in ids])
            school_audit(cur, ctx.school_id, ctx.uid, "student.created", "student", student["uid"],
                         {"classes": len(ids)})
    out = get_student(ctx, student["uid"])
    out["secret"] = student["secret"]
    out["badge_token"] = student["badge_token"]
    return out


def update_student(ctx: SchoolCtx, uid: str, changes: dict) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            school = _load_school(cur, ctx.school_id)
            _require_manage(ctx, school)
            _load_student(cur, ctx, uid, for_update=True)
            sets, params = [], []
            for col in ("display_name", "grade", "external_ref", "avatar"):
                if col in changes:
                    sets.append(f"{col} = %s")
                    params.append(changes[col])
            if "external_ref" in changes and changes["external_ref"]:
                cur.execute(
                    "SELECT 1 FROM school_students WHERE school_id = %s AND external_ref = %s AND uid <> %s",
                    (ctx.school_id, changes["external_ref"], uid),
                )
                if cur.fetchone():
                    raise _err(409, "external_ref_taken", "Another student already has this school reference number.")
            if sets:
                cur.execute(f"UPDATE school_students SET {', '.join(sets)} WHERE uid = %s", params + [uid])
                if "display_name" in changes:
                    cur.execute("UPDATE users SET display_name = %s WHERE uid = %s", (changes["display_name"], uid))
                if "grade" in changes:
                    cur.execute("UPDATE users SET age_group_flag = %s WHERE uid = %s",
                                (_age_group(changes["grade"]), uid))
                school_audit(cur, ctx.school_id, ctx.uid, "student.updated", "student", uid,
                             {"fields": sorted(changes)})
    return get_student(ctx, uid)


def reset_secret(ctx: SchoolCtx, uid: str, secret_kind: Optional[str]) -> dict:
    """New picture/PIN (shown once); also clears a lockout."""
    if secret_kind is not None and secret_kind not in SECRET_KINDS:
        raise _err(422, "invalid_secret_kind", "Choose a picture password or a PIN.")
    with get_db() as conn:
        with conn.cursor() as cur:
            student = _load_student(cur, ctx, uid, for_update=True)
            _require_secret_access(cur, ctx, uid)
            kind = resolve_secret_kind(secret_kind, student["grade"]) if secret_kind else student["secret_kind"]
            canonical, value = generate_secret(kind)
            cur.execute(
                """
                UPDATE school_students
                   SET secret_kind = %s, secret_hash = %s, failed_attempts = 0, locked_until = NULL
                 WHERE uid = %s
                """,
                (kind, hash_pin(canonical), uid),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "student.secret_reset", "student", uid, {"kind": kind})
    return {"uid": uid, "secret_kind": kind, "secret": value}


def rotate_badge(ctx: SchoolCtx, uid: str) -> dict:
    """New QR badge token (shown once); the old badge stops working at once."""
    with get_db() as conn:
        with conn.cursor() as cur:
            _load_student(cur, ctx, uid, for_update=True)
            _require_secret_access(cur, ctx, uid)
            token, token_hash = new_badge_token()
            cur.execute("UPDATE school_students SET badge_token_hash = %s WHERE uid = %s", (token_hash, uid))
            school_audit(cur, ctx.school_id, ctx.uid, "student.badge_rotated", "student", uid)
    return {"uid": uid, "badge_token": token}


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def set_archived(ctx: SchoolCtx, uids: list[str], archived: bool) -> dict:
    """Archive blocks sign-in and keeps the data (year end); restore needs a seat."""
    uids = list(dict.fromkeys(uids))
    with get_db() as conn:
        with conn.cursor() as cur:
            school = _load_school(cur, ctx.school_id, for_update=True)
            _require_manage(ctx, school)
            cur.execute(
                "SELECT uid, status FROM school_students WHERE school_id = %s AND uid = ANY(%s) FOR UPDATE",
                (ctx.school_id, uids),
            )
            found = {r["uid"]: r["status"] for r in cur.fetchall()}
            if set(found) != set(uids):
                raise student_not_found()
            targets = [u for u, st in found.items() if st == ("active" if archived else "archived")]
            if not archived:
                _require_seats(cur, school, len(targets))
            if targets:
                cur.execute(
                    f"""
                    UPDATE school_students
                       SET status = %s, archived_at = {"now()" if archived else "NULL"}
                     WHERE uid = ANY(%s)
                    """,
                    ("archived" if archived else "active", targets),
                )
                school_audit(cur, ctx.school_id, ctx.uid,
                             "students.archived" if archived else "students.restored",
                             "student", targets[0] if len(targets) == 1 else None, {"count": len(targets)})
    for uid in uids:
        _invalidate_student(uid)
    return {"changed": len(targets)}


async def delete_student(ctx: SchoolCtx, uid: str) -> None:
    """Erase the student's account and learner data (account_service cascade),
    pseudonymise their consent record and purge their Firebase login."""
    from app.services.account_service import delete_user_account
    from app.services.firebase_admin import purge_login
    with get_db() as conn:
        with conn.cursor() as cur:
            school = _load_school(cur, ctx.school_id)
            _require_manage(ctx, school)
            _load_student(cur, ctx, uid)
            school_audit(cur, ctx.school_id, ctx.uid, "student.deleted", "student", uid)
    delete_user_account(uid, consent_event={
        "action": "revoked", "method": "school_deletion", "details": {"school_id": ctx.school_id},
    })
    _invalidate_student(uid)
    await purge_login(uid)


def export_student(ctx: SchoolCtx, uid: str) -> dict:
    from app.services.account_service import build_user_export
    if not ctx.is_admin:
        raise _err(403, "school_role_required", "Only school admins can export student data.",
                   required_roles=list(ADMIN_ROLES))
    student = get_student(ctx, uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            school_audit(cur, ctx.school_id, ctx.uid, "student.exported", "student", uid)
    return {"student": student, "data": build_user_export(uid)}


# ── CSV roster import (SC-202) ───────────────────────────────────────────────

_HEADERS = {
    "display_name": {"name", "student", "student name", "display name", "display_name", "full name"},
    "grade": {"grade", "class grade", "year", "std", "standard"},
    "external_ref": {"roll", "roll no", "roll number", "roll_number", "admission no", "admission number",
                     "external_ref", "student id", "id", "reference"},
    "class_name": {"class", "class name", "class_name", "section", "group"},
    "secret_kind": {"sign-in", "sign in", "login", "secret", "secret_kind"},
}
_KG = {"kg", "lkg", "ukg", "nursery", "k", "reception"}


def _parse_grade(raw: str) -> tuple[Optional[int], Optional[str]]:
    raw = raw.strip().lower()
    if not raw:
        return None, None
    if raw in _KG:
        return 0, None
    m = re.search(r"\d+", raw)
    if not m or not 0 <= int(m.group()) <= 12:
        return None, "grade must be a number from 0 (KG) to 12"
    return int(m.group()), None


def parse_roster_csv(text: str) -> tuple[list[dict], list[str]]:
    """Rows (with 1-based CSV line numbers and per-row errors) and file-level
    errors. Cells are treated as plain text — nothing is evaluated."""
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], ["The file is empty."]
    columns: dict[str, int] = {}
    for idx, name in enumerate(header):
        key = name.strip().lower()
        for field, aliases in _HEADERS.items():
            if key in aliases and field not in columns:
                columns[field] = idx
    if "display_name" not in columns:
        return [], ["Add a header row with a 'name' column (optional: grade, roll number, class, sign-in)."]

    rows, file_errors = [], []
    for line_no, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        if len(rows) >= MAX_IMPORT_ROWS:
            file_errors.append(f"Only {MAX_IMPORT_ROWS} students can be imported at once.")
            break

        def cell(field: str) -> str:
            idx = columns.get(field)
            return cells[idx].strip() if idx is not None and idx < len(cells) else ""

        errors = []
        name = cell("display_name")
        if not name:
            errors.append("name is missing")
        elif len(name) > 80:
            errors.append("name is longer than 80 characters")
        grade, grade_error = _parse_grade(cell("grade"))
        if grade_error:
            errors.append(grade_error)
        ref = cell("external_ref") or None
        if ref and len(ref) > 40:
            errors.append("roll number is longer than 40 characters")
        class_name = cell("class_name") or None
        if class_name and len(class_name) > 80:
            errors.append("class name is longer than 80 characters")
        kind_raw = cell("secret_kind").lower()
        kind = {"picture": "picture", "pictures": "picture", "pin": "pin"}.get(kind_raw) if kind_raw else None
        if kind_raw and not kind:
            errors.append("sign-in must be 'picture' or 'pin'")
        rows.append({"line": line_no, "display_name": name, "grade": grade, "external_ref": ref,
                     "class_name": class_name, "secret_kind": kind, "errors": errors, "warnings": []})
    if not rows and not file_errors:
        file_errors.append("No students found under the header row.")
    return rows, file_errors


def import_students(ctx: SchoolCtx, csv_text: str, dry_run: bool) -> dict:
    """Dry run → a report, nothing written. Commit → all-or-nothing in one
    transaction; rows whose roll number matches an existing student update
    that student. Imported students get no secret yet — printing a class's
    login cards generates them (keeps a 2,000-row import fast)."""
    rows, file_errors = parse_roster_csv(csv_text)
    with get_db() as conn:
        with conn.cursor() as cur:
            school = _load_school(cur, ctx.school_id, for_update=not dry_run)
            _require_manage(ctx, school)
            dpa_ok = school.get("dpa_version") == settings.SCHOOL_DPA_VERSION

            refs = [r["external_ref"] for r in rows if r["external_ref"]]
            cur.execute(
                "SELECT uid, external_ref, status FROM school_students WHERE school_id = %s AND external_ref = ANY(%s)",
                (ctx.school_id, refs),
            )
            existing = {r["external_ref"]: dict(r) for r in cur.fetchall()}
            cur.execute(
                "SELECT id::text AS id, lower(name) AS key FROM classes WHERE school_id = %s AND archived_at IS NULL",
                (ctx.school_id,),
            )
            classes = {r["key"]: r["id"] for r in cur.fetchall()}
            mine = None if ctx.is_admin else _teacher_class_ids(cur, ctx)

            seen_refs: dict[str, int] = {}
            seen_names: dict[str, int] = {}
            new_classes: dict[str, str] = {}
            for r in rows:
                ref = r["external_ref"]
                if ref:
                    if ref in seen_refs:
                        r["errors"].append(f"roll number repeats line {seen_refs[ref]}")
                    seen_refs.setdefault(ref, r["line"])
                key = r["display_name"].lower()
                if key and not ref and key in seen_names:
                    r["warnings"].append(f"same name as line {seen_names[key]} — add roll numbers to tell them apart")
                seen_names.setdefault(key, r["line"])
                match = existing.get(ref) if ref else None
                r["action"] = "update" if match else "create"
                if match and match["status"] == "archived":
                    r["warnings"].append("this student is archived — they stay archived")
                if r["class_name"]:
                    class_key = r["class_name"].lower()
                    if class_key in classes:
                        if mine is not None and classes[class_key] not in mine:
                            r["errors"].append(f"you don't teach class '{r['class_name']}'")
                    else:
                        new_classes.setdefault(class_key, r["class_name"])

            creates = sum(1 for r in rows if r["action"] == "create" and not r["errors"])
            seats_available = int(school["seat_limit"]) - _active_student_count(cur, ctx.school_id)
            if creates > seats_available:
                file_errors.append(f"This adds {creates} students but the school has {max(seats_available, 0)} seats left.")
            if not dpa_ok:
                file_errors.append("The school's owner must accept the data processing agreement first.")

            report = {
                "dry_run": dry_run,
                "rows": [{k: v for k, v in r.items()} for r in rows],
                "errors": file_errors,
                "summary": {
                    "rows": len(rows),
                    "create": creates,
                    "update": sum(1 for r in rows if r["action"] == "update" and not r["errors"]),
                    "rows_with_errors": sum(1 for r in rows if r["errors"]),
                    "new_classes": sorted(new_classes.values(), key=str.lower),
                    "seats_available": max(seats_available, 0),
                },
            }
            has_errors = bool(file_errors) or any(r["errors"] for r in rows)
            if dry_run:
                return report
            if has_errors:
                raise _err(422, "import_has_errors", "Fix the errors in the file, then import again.", report=report)

            for key, name in new_classes.items():
                from app.services.school_class_service import insert_class
                created_class = insert_class(cur, ctx, name, None, None, None)
                classes[key] = created_class["id"]

            to_create = [r for r in rows if r["action"] == "create"]
            created = _insert_students(cur, school, ctx.uid, to_create, with_secrets=False)
            for r, c in zip(to_create, created):
                r["uid"] = c["uid"]
            for r in rows:
                if r["action"] == "update":
                    r["uid"] = existing[r["external_ref"]]["uid"]
                    cur.execute(
                        """
                        UPDATE school_students
                           SET display_name = %s, grade = COALESCE(%s, grade),
                               secret_kind = COALESCE(%s, secret_kind)
                         WHERE uid = %s
                        """,
                        (r["display_name"], r["grade"], r["secret_kind"], r["uid"]),
                    )
                    cur.execute("UPDATE users SET display_name = %s WHERE uid = %s", (r["display_name"], r["uid"]))
            _enroll(cur, ctx.school_id, [(classes[r["class_name"].lower()], r["uid"]) for r in rows if r["class_name"]])
            school_audit(cur, ctx.school_id, ctx.uid, "students.imported", None, None, {
                "created": len(created), "updated": report["summary"]["update"], "new_classes": len(new_classes),
            })
    for r in rows:
        if r.get("action") == "update":
            _invalidate_student(r["uid"])
    report["summary"]["created_classes"] = len(new_classes)
    return report
