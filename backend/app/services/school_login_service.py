"""Student sign-in (plans/school-courses M2: SC-205, SC-206, SC-207; README §3.3).

Class code → pick your name (or type your roll number) → picture password or
PIN, or a QR badge. Success returns a Firebase custom token; the client calls
signInWithCustomToken and from then on sends ordinary Firebase ID tokens, so
core/auth.py needs no second authentication path.

Abuse controls never key on IP (a whole school shares one): 5 wrong secrets
lock that student for 15 minutes, and too many failures on one class code
throttle the code. Every failure and lockout is written to school_audit_log,
which is also what the class throttle counts.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_db
from app.core.school_auth import OPEN_SCHOOL_STATUSES
from app.services.firebase_admin import mint_custom_token
from app.services.school_class_service import normalize_join_code
from app.services.school_service import effective_settings, school_audit
from app.services.school_student_service import canonical_secret, hash_badge_token, verify_secret

STUDENT_MAX_FAILURES = 5
STUDENT_LOCK_MINUTES = 15
CLASS_FAILURE_LIMIT = 50
CLASS_FAILURE_WINDOW_MINUTES = 10

_dummy_hash: Optional[str] = None


def _equalise_timing(canonical: str) -> None:
    """Spend the same scrypt time when there's no student to check, so
    response time doesn't reveal whether a roll number exists."""
    global _dummy_hash
    from app.services.profile_service import hash_pin
    if _dummy_hash is None:
        _dummy_hash = hash_pin("pin:000000")
    verify_secret(canonical or "pin:000000", _dummy_hash)


def _err(status: int, error: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message, **extra})


def _code_invalid() -> HTTPException:
    return _err(404, "class_code_invalid", "We couldn't find that class code. Check it with your teacher.")


def _invalid_secret() -> HTTPException:
    return _err(401, "invalid_student_secret", "That's not right. Try again, or ask your teacher.")


def roster_name(display_name: str) -> str:
    """'Asha Kumari Rao' → 'Asha R.' — enough for a child to find themselves."""
    parts = display_name.split()
    if len(parts) < 2:
        return display_name
    return f"{parts[0]} {parts[-1][0]}."


def _require_login_configured() -> None:
    if not settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        raise _err(503, "login_unavailable", "Class sign-in isn't available right now. Ask your teacher.")


def _open_class(cur, code: str) -> Optional[dict]:
    cur.execute(
        """
        SELECT c.id, c.name, c.grade, c.school_id, s.name AS school_name, s.settings AS school_settings
          FROM classes c
          JOIN schools s ON s.id = c.school_id
         WHERE c.join_code = %s AND c.archived_at IS NULL AND s.status = ANY(%s)
        """,
        (code, list(OPEN_SCHOOL_STATUSES)),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def lookup_class(raw_code: str) -> dict:
    code = normalize_join_code(raw_code)
    if not code:
        raise _code_invalid()
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = _open_class(cur, code)
            if not cls:
                raise _code_invalid()
            roster_visible = effective_settings(cls["school_settings"])["login_roster_visible"]
            students = []
            if roster_visible:
                cur.execute(
                    """
                    SELECT s.uid, s.display_name, s.avatar, s.secret_kind
                      FROM class_enrollments e
                      JOIN school_students s ON s.uid = e.student_uid
                     WHERE e.class_id = %s AND e.removed_at IS NULL
                       AND s.status = 'active' AND s.secret_hash IS NOT NULL
                     ORDER BY lower(s.display_name)
                    """,
                    (cls["id"],),
                )
                students = [{"uid": r["uid"], "display_name": roster_name(r["display_name"]),
                             "avatar": r["avatar"], "secret_kind": r["secret_kind"]} for r in cur.fetchall()]
    return {
        "class": {"name": cls["name"], "grade": cls["grade"]},
        "school": {"name": cls["school_name"]},
        "roster_visible": roster_visible,
        "students": students,
    }


def _custom_token(uid: str, school_id: str) -> str:
    token = mint_custom_token(uid, {"school_id": school_id, "kind": "school_student"})
    if not token:
        raise _err(503, "login_unavailable", "Class sign-in isn't available right now. Ask your teacher.")
    return token


def sign_in(raw_code: str, student_uid: Optional[str], external_ref: Optional[str],
            secret_kind: str, secret_value: Any) -> dict:
    _require_login_configured()
    code = normalize_join_code(raw_code)
    if not code:
        raise _code_invalid()
    if not student_uid and not external_ref:
        raise _err(422, "student_required", "Pick your name or type your roll number.")
    canonical = canonical_secret(secret_kind, secret_value)

    error: Optional[HTTPException] = None
    student: Optional[dict] = None
    custom_token: Optional[str] = None
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = _open_class(cur, code)
            if not cls:
                raise _code_invalid()
            school_id, class_id = str(cls["school_id"]), str(cls["id"])
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM school_audit_log
                 WHERE school_id = %s AND action = 'student.sign_in_failed' AND target_id = %s
                   AND created_at > now() - make_interval(mins => %s)
                """,
                (school_id, class_id, CLASS_FAILURE_WINDOW_MINUTES),
            )
            if int(cur.fetchone()["n"]) >= CLASS_FAILURE_LIMIT:
                raise _err(429, "class_code_throttled",
                           "Too many wrong tries in this class. Wait a few minutes, or ask your teacher.",
                           retry_after_seconds=CLASS_FAILURE_WINDOW_MINUTES * 60)

            cur.execute(
                f"""
                SELECT s.* FROM school_students s
                  JOIN class_enrollments e ON e.student_uid = s.uid AND e.class_id = %s AND e.removed_at IS NULL
                 WHERE s.status = 'active' AND s.school_id = %s
                   AND {"s.uid = %s" if student_uid else "s.external_ref = %s"}
                 FOR UPDATE OF s
                """,
                (class_id, school_id, student_uid or external_ref),
            )
            row = cur.fetchone()
            student = dict(row) if row else None
            now = datetime.now(timezone.utc)

            if student is None or not student["secret_hash"]:
                _equalise_timing(canonical or "")
                error = _invalid_secret()
            elif student["locked_until"] and student["locked_until"] > now:
                error = _err(423, "student_locked", "Too many tries. Ask your teacher, or wait a few minutes.",
                             locked_until=student["locked_until"].isoformat())
            elif canonical and student["secret_kind"] == secret_kind and verify_secret(canonical, student["secret_hash"]):
                # Mint inside the transaction (M4): if the token can't be
                # minted, the lockout reset and the signed_in audit roll back
                # with it, so the audit never claims a sign-in that didn't ship.
                custom_token = _custom_token(student["uid"], school_id)
                cur.execute(
                    "UPDATE school_students SET failed_attempts = 0, locked_until = NULL WHERE uid = %s",
                    (student["uid"],),
                )
                school_audit(cur, school_id, None, "student.signed_in", "student", student["uid"],
                             {"method": "class_code", "class_id": class_id})
            elif canonical and student["secret_kind"] != secret_kind:
                # Wrong sign-in type (picture vs PIN): never a correct guess, so
                # don't burn a lockout attempt — just ask for the other kind.
                error = _invalid_secret()
            else:
                failures = int(student["failed_attempts"] or 0) + 1
                if failures >= STUDENT_MAX_FAILURES:
                    locked_until = now + timedelta(minutes=STUDENT_LOCK_MINUTES)
                    cur.execute(
                        "UPDATE school_students SET failed_attempts = 0, locked_until = %s WHERE uid = %s",
                        (locked_until, student["uid"]),
                    )
                    school_audit(cur, school_id, None, "student.locked", "student", student["uid"],
                                 {"class_id": class_id})
                    error = _err(423, "student_locked", "Too many tries. Ask your teacher, or wait a few minutes.",
                                 locked_until=locked_until.isoformat())
                else:
                    cur.execute("UPDATE school_students SET failed_attempts = %s WHERE uid = %s",
                                (failures, student["uid"]))
                    error = _invalid_secret()

            if error is not None and error.status_code in (401, 423):
                # Counted by the class throttle above. Committed before raising.
                school_audit(cur, school_id, None, "student.sign_in_failed", "class", class_id,
                             {"student_uid": student["uid"] if student else None})
    if error is not None:
        raise error
    return {
        "custom_token": custom_token,
        "expires_in": 3600,
        "student": {"uid": student["uid"], "display_name": student["display_name"]},
    }


def badge_sign_in(token: str) -> dict:
    """QR badge: a long random token printed on the student's card."""
    _require_login_configured()
    custom_token: Optional[str] = None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.uid, s.display_name, s.school_id::text AS school_id
                  FROM school_students s
                  JOIN schools sc ON sc.id = s.school_id
                 WHERE s.badge_token_hash = %s AND s.status = 'active' AND sc.status = ANY(%s)
                """,
                (hash_badge_token(token), list(OPEN_SCHOOL_STATUSES)),
            )
            student = cur.fetchone()
            if student:
                # Mint inside the transaction (M4) so the signed_in audit rolls
                # back with it if the token can't be minted.
                custom_token = _custom_token(student["uid"], student["school_id"])
                school_audit(cur, student["school_id"], None, "student.signed_in", "student", student["uid"],
                             {"method": "badge"})
    if not student:
        time.sleep(0.05)
        raise _err(401, "invalid_badge", "This badge doesn't work any more. Ask your teacher for a new card.")
    return {
        "custom_token": custom_token,
        "expires_in": 3600,
        "student": {"uid": student["uid"], "display_name": student["display_name"]},
    }
