"""Schools, staff and invites (plans/school-courses M1: SC-111, SC-112, SC-113).

A school is a tenant created by an ECALT admin. Staff are ordinary adult ECALT
accounts that join through an emailed invite. Every staff mutation writes
school_audit_log in the same transaction (school_audit).

Callers pass a SchoolCtx from core.school_auth.school_member(...); every query on
a school-owned table filters by ctx.school_id.
"""
import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings
from app.core.database import get_db
from app.core.school_auth import (
    ADMIN_ROLES,
    ALL_ROLES,
    SchoolCtx,
    invalidate_school_member_cache,
    parse_school_id,
    school_not_found,
)

logger = logging.getLogger(__name__)

SCHOOL_STATUSES = ("onboarding", "active", "suspended", "terminated")


class SchoolSettings(BaseModel):
    """School-level settings. Unknown keys are rejected so a typo can't
    silently do nothing. Later milestones enforce these (README §3.3, §3.9)."""
    model_config = ConfigDict(extra="forbid")

    teachers_can_create_students: bool = False          # D9
    login_roster_visible: bool = True                    # class-code page lists names
    teacher_transcript_access: bool = True               # D4
    delete_originals_after_days: Optional[int] = Field(None, ge=1, le=3650)
    student_daily_tutor_messages: int = Field(30, ge=0, le=500)
    student_daily_quiz_sets: int = Field(20, ge=0, le=500)


def effective_settings(raw: Optional[dict]) -> dict:
    """Stored settings merged over defaults (ignores keys from older versions)."""
    known = {k: v for k, v in (raw or {}).items() if k in SchoolSettings.model_fields}
    try:
        return SchoolSettings(**known).model_dump()
    except ValidationError:
        # Salvage the valid fields rather than discarding all of them — one bad
        # value shouldn't silently reset every other setting (L7).
        salvaged: dict = {}
        for key, value in known.items():
            try:
                SchoolSettings(**{key: value})
            except ValidationError:
                logger.warning("ignoring invalid stored school setting %r", key)
            else:
                salvaged[key] = value
        return SchoolSettings(**salvaged).model_dump()


# ── helpers ──────────────────────────────────────────────────────────────────

def school_audit(cur, school_id: str, actor_uid: Optional[str], action: str,
                 target_type: Optional[str] = None, target_id: Optional[str] = None,
                 meta: Optional[dict] = None) -> None:
    """Append to school_audit_log inside the caller's transaction. Never put
    secrets, student names or document text in meta."""
    cur.execute(
        """
        INSERT INTO school_audit_log (school_id, actor_uid, action, target_type, target_id, meta)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (school_id, actor_uid, action, target_type, target_id, json.dumps(meta or {})),
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        raise HTTPException(status_code=422, detail={"error": "invalid_email", "message": "Enter a valid email address."})
    return email


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    return slug or "school"


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _row(r) -> dict:
    return {k: _iso(v) for k, v in dict(r).items()}


def _school_out(row: dict) -> dict:
    out = _row(row)
    out["settings"] = effective_settings(row.get("settings"))
    out["monthly_ai_budget_cents"] = float(row.get("monthly_ai_budget_cents") or 0)
    out["dpa_current_version"] = settings.SCHOOL_DPA_VERSION
    out["dpa_accepted"] = row.get("dpa_version") == settings.SCHOOL_DPA_VERSION
    return out


def _invalidate_school_access(school_id: str) -> None:
    """A school's status changed: drop every cached decision that depends on it."""
    from app.core.auth import _status_cache
    from app.services.journey_access import invalidate_journey_access
    from app.services.subscription_service import invalidate_student_school
    invalidate_school_member_cache(school_id=school_id)
    invalidate_journey_access()
    invalidate_student_school()
    for uid in [k for k in _status_cache if k.startswith("stu_")]:
        _status_cache.pop(uid, None)


# ── ECALT admin: schools ─────────────────────────────────────────────────────

def create_school(actor_uid: str, name: str, country: str, seat_limit: int,
                  monthly_ai_budget_cents: float) -> dict:
    base = _slugify(name)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM schools WHERE slug = %s OR slug LIKE %s", (base, f"{base}-%"))
            taken = {r["slug"] for r in cur.fetchall()}
            slug, n = base, 2
            while slug in taken:
                slug, n = f"{base}-{n}", n + 1
            cur.execute(
                """
                INSERT INTO schools (name, slug, country, seat_limit, monthly_ai_budget_cents, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (name.strip(), slug, country.upper(), seat_limit, monthly_ai_budget_cents, actor_uid),
            )
            row = cur.fetchone()
            school_audit(cur, str(row["id"]), actor_uid, "school.created", "school", str(row["id"]),
                         {"seat_limit": seat_limit, "monthly_ai_budget_cents": float(monthly_ai_budget_cents)})
    return _school_out(row)


def list_schools(q: Optional[str] = None, status: Optional[str] = None,
                 limit: int = 50, offset: int = 0) -> dict:
    filters, params = ["TRUE"], []
    if q:
        filters.append("(s.name ILIKE %s OR s.slug ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if status:
        filters.append("s.status = %s")
        params.append(status)
    where = " AND ".join(filters)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM schools s WHERE {where}", params)
            total = int(cur.fetchone()["n"])
            cur.execute(
                f"""
                SELECT s.*,
                       (SELECT COUNT(*) FROM school_members m
                         WHERE m.school_id = s.id AND m.status = 'active')   AS staff_count,
                       (SELECT COUNT(*) FROM school_students st
                         WHERE st.school_id = s.id AND st.status = 'active') AS student_count
                  FROM schools s
                 WHERE {where}
                 ORDER BY s.created_at DESC
                 LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()
    return {"schools": [_school_out(r) for r in rows], "total": total}


def get_school(school_id: str) -> dict:
    sid = parse_school_id(school_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.*,
                       (SELECT COUNT(*) FROM school_members m
                         WHERE m.school_id = s.id AND m.status = 'active')   AS staff_count,
                       (SELECT COUNT(*) FROM school_students st
                         WHERE st.school_id = s.id AND st.status = 'active') AS student_count
                  FROM schools s WHERE s.id = %s
                """,
                (sid,),
            )
            row = cur.fetchone()
    if not row:
        raise school_not_found()
    return _school_out(row)


def admin_update_school(actor_uid: str, school_id: str, changes: dict) -> dict:
    """ECALT admin: name, status, seats, budget. Terminated is final here —
    offboarding (SC-803) deletes the data after the grace period."""
    sid = parse_school_id(school_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM schools WHERE id = %s FOR UPDATE", (sid,))
            current = cur.fetchone()
            if not current:
                raise school_not_found()
            if current["status"] == "terminated" and changes.get("status") not in (None, "terminated"):
                raise HTTPException(status_code=409, detail={
                    "error": "school_terminated",
                    "message": "A terminated school can't be reopened.",
                })
            sets, params = [], []
            for col in ("name", "status", "seat_limit", "monthly_ai_budget_cents"):
                if col in changes and changes[col] is not None:
                    sets.append(f"{col} = %s")
                    params.append(changes[col].strip() if col == "name" else changes[col])
            if changes.get("status") == "terminated" and current["status"] != "terminated":
                sets.append("terminated_at = now()")
            if not sets:
                return get_school(sid)
            sets.append("updated_at = now()")
            cur.execute(f"UPDATE schools SET {', '.join(sets)} WHERE id = %s", params + [sid])
            school_audit(cur, sid, actor_uid, "school.updated", "school", sid,
                         {k: (float(v) if k == "monthly_ai_budget_cents" else v)
                          for k, v in changes.items() if v is not None})
    if changes.get("status") and changes["status"] != current["status"]:
        _invalidate_school_access(sid)
    elif "monthly_ai_budget_cents" in changes:
        from app.services.subscription_service import invalidate_student_school
        invalidate_student_school()
    return get_school(sid)


# ── Staff-facing: schools ────────────────────────────────────────────────────

def my_schools(uid: str) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.name, s.slug, s.status, m.role
                  FROM school_members m
                  JOIN schools s ON s.id = m.school_id
                 WHERE m.uid = %s AND m.status = 'active' AND s.status <> 'terminated'
                 ORDER BY s.name
                """,
                (uid,),
            )
            return [_row(r) for r in cur.fetchall()]


def school_detail(ctx: SchoolCtx) -> dict:
    school = get_school(ctx.school_id)
    school["my_role"] = ctx.role
    if not ctx.is_admin:
        # Teachers don't need commercial terms.
        school.pop("monthly_ai_budget_cents", None)
    return school


def update_school(ctx: SchoolCtx, name: Optional[str], settings_patch: Optional[dict]) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT settings FROM schools WHERE id = %s FOR UPDATE", (ctx.school_id,))
            row = cur.fetchone()
            merged = effective_settings(row["settings"] if row else None)
            if settings_patch:
                try:
                    merged = SchoolSettings(**{**merged, **settings_patch}).model_dump()
                except ValidationError as e:
                    raise HTTPException(status_code=422, detail={
                        "error": "invalid_settings",
                        "message": "Some settings are not valid.",
                        "fields": [".".join(str(p) for p in err["loc"]) for err in e.errors()],
                    })
            cur.execute(
                """
                UPDATE schools SET name = COALESCE(%s, name), settings = %s::jsonb, updated_at = now()
                 WHERE id = %s
                """,
                (name.strip() if name else None, json.dumps(merged), ctx.school_id),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "school.settings_updated", "school", ctx.school_id,
                         {"name_changed": bool(name), "settings": sorted((settings_patch or {}).keys())})
    if settings_patch:
        from app.services.subscription_service import invalidate_student_school
        invalidate_student_school()
    return school_detail(ctx)


def accept_dpa(ctx: SchoolCtx, version: str) -> dict:
    """The school (controller) accepts ECALT's DPA (processor). Required before
    any student can be created; moves an onboarding school to active."""
    if version != settings.SCHOOL_DPA_VERSION:
        raise HTTPException(status_code=409, detail={
            "error": "dpa_version_mismatch",
            "message": "The agreement has changed. Reload and review the current version.",
            "current_version": settings.SCHOOL_DPA_VERSION,
        })
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE schools
                   SET dpa_version = %s, dpa_accepted_at = now(), dpa_accepted_by = %s,
                       status = CASE WHEN status = 'onboarding' THEN 'active' ELSE status END,
                       updated_at = now()
                 WHERE id = %s
                """,
                (version, ctx.uid, ctx.school_id),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "school.dpa_accepted", "school", ctx.school_id,
                         {"dpa_version": version})
    _invalidate_school_access(ctx.school_id)
    return school_detail(ctx)


# ── Staff and invites ────────────────────────────────────────────────────────

def list_staff(ctx: SchoolCtx) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.uid, m.role, m.created_at, u.display_name, u.email, u.photo_url
                  FROM school_members m
                  JOIN users u ON u.uid = m.uid
                 WHERE m.school_id = %s AND m.status = 'active'
                 ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                          lower(coalesce(u.display_name, u.email, ''))
                """,
                (ctx.school_id,),
            )
            members = [_row(r) for r in cur.fetchall()]
            invites: list[dict] = []
            if ctx.is_admin:
                cur.execute(
                    """
                    SELECT id, email, role, expires_at, created_at
                      FROM school_invites
                     WHERE school_id = %s AND accepted_at IS NULL AND revoked_at IS NULL
                     ORDER BY created_at DESC
                    """,
                    (ctx.school_id,),
                )
                invites = [{**_row(r), "expired": r["expires_at"] < datetime.now(timezone.utc)}
                           for r in cur.fetchall()]
    return {"members": members, "invites": invites}


def _check_can_grant(actor_role: Optional[str], role: str) -> None:
    """Owners grant any role, admins grant admin/teacher, ECALT admins (actor
    role None) invite owners only."""
    if role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail={"error": "invalid_role", "message": "Unknown role."})
    if actor_role == "admin" and role == "owner":
        raise HTTPException(status_code=403, detail={
            "error": "school_role_required",
            "message": "Only an owner can add another owner.",
            "required_roles": ["owner"],
        })


def create_invite(school_id: str, actor_uid: str, actor_role: Optional[str],
                  email: str, role: str) -> tuple[dict, str, str]:
    """Create an invite and return (invite, token, school name). The token is
    returned once, for the email; only its hash is stored. Re-inviting an
    address revokes its earlier open invites."""
    _check_can_grant(actor_role, role)
    email = _normalize_email(email)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SCHOOL_INVITE_TTL_DAYS)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, status FROM schools WHERE id = %s", (school_id,))
            school = cur.fetchone()
            if not school or school["status"] == "terminated":
                raise school_not_found()
            cur.execute(
                """
                SELECT 1 FROM school_members m JOIN users u ON u.uid = m.uid
                 WHERE m.school_id = %s AND m.status = 'active' AND lower(u.email) = %s
                """,
                (school_id, email),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "already_member",
                    "message": "This person is already on the school's staff.",
                })
            cur.execute(
                """
                UPDATE school_invites SET revoked_at = now()
                 WHERE school_id = %s AND email = %s AND accepted_at IS NULL AND revoked_at IS NULL
                """,
                (school_id, email),
            )
            cur.execute(
                """
                INSERT INTO school_invites (school_id, email, role, token_hash, invited_by, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, email, role, expires_at, created_at
                """,
                (school_id, email, role, _hash_token(token), actor_uid, expires_at),
            )
            invite = _row(cur.fetchone())
            school_audit(cur, school_id, actor_uid, "staff.invited", "invite", invite["id"], {"role": role})
    return invite, token, school["name"]


def revoke_invite(ctx: SchoolCtx, invite_id: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_invites SET revoked_at = now()
                 WHERE id = %s AND school_id = %s AND accepted_at IS NULL AND revoked_at IS NULL
                RETURNING id
                """,
                (invite_id, ctx.school_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail={"error": "invite_not_found", "message": "Invite not found."})
            school_audit(cur, ctx.school_id, ctx.uid, "staff.invite_revoked", "invite", invite_id)


def _load_open_invite(cur, token: str, for_update: bool = False) -> dict:
    cur.execute(
        f"""
        SELECT i.*, s.name AS school_name, s.status AS school_status
          FROM school_invites i
          JOIN schools s ON s.id = i.school_id
         WHERE i.token_hash = %s
         {"FOR UPDATE OF i" if for_update else ""}
        """,
        (_hash_token(token),),
    )
    invite = cur.fetchone()
    if (not invite or invite["accepted_at"] or invite["revoked_at"]
            or invite["school_status"] == "terminated"):
        raise HTTPException(status_code=404, detail={
            "error": "invite_invalid",
            "message": "This invite link isn't valid any more. Ask the school for a new one.",
        })
    if invite["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail={
            "error": "invite_expired",
            "message": "This invite has expired. Ask the school to send a new one.",
        })
    return dict(invite)


def preview_invite(token: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            invite = _load_open_invite(cur, token)
    return {
        "school_name": invite["school_name"],
        "role": invite["role"],
        "email_hint": _mask_email(invite["email"]),
        "expires_at": _iso(invite["expires_at"]),
    }


def accept_invite(token: str, uid: str, token_email: Optional[str], email_verified: bool) -> dict:
    """Join the school. The signed-in Google account's verified email must
    match the invited address — the invite link alone isn't enough."""
    with get_db() as conn:
        with conn.cursor() as cur:
            invite = _load_open_invite(cur, token, for_update=True)
            if invite["school_status"] == "suspended":
                raise HTTPException(status_code=403, detail={
                    "error": "school_access_suspended",
                    "message": "This school's ECALT access is suspended. Contact ECALT support.",
                })
            if not email_verified or (token_email or "").strip().lower() != invite["email"]:
                raise HTTPException(status_code=403, detail={
                    "error": "invite_email_mismatch",
                    "message": f"This invite was sent to {_mask_email(invite['email'])}. "
                               "Sign in with that Google account to accept it.",
                })
            cur.execute("SELECT profile_type, age_group_flag FROM users WHERE uid = %s", (uid,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=409, detail={
                    "error": "account_setup_required",
                    "message": "Finish setting up your ECALT account, then open the invite again.",
                })
            if user["profile_type"] != "account" or user["age_group_flag"] != "adult":
                raise HTTPException(status_code=403, detail={
                    "error": "staff_must_be_adult",
                    "message": "School staff accounts must belong to an adult.",
                })
            cur.execute(
                """
                INSERT INTO school_members (school_id, uid, role, invited_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (school_id, uid) DO UPDATE
                    SET role = EXCLUDED.role, status = 'active', removed_at = NULL,
                        invited_by = EXCLUDED.invited_by
                """,
                (invite["school_id"], uid, invite["role"], invite["invited_by"]),
            )
            cur.execute(
                "UPDATE school_invites SET accepted_at = now(), accepted_uid = %s WHERE id = %s",
                (uid, invite["id"]),
            )
            school_id = str(invite["school_id"])
            school_audit(cur, school_id, uid, "staff.joined", "member", uid, {"role": invite["role"]})
    invalidate_school_member_cache(school_id=school_id, uid=uid)
    return {"school_id": school_id, "school_name": invite["school_name"], "role": invite["role"]}


def _active_owner_count(cur, school_id: str) -> int:
    cur.execute(
        "SELECT COUNT(*) AS n FROM school_members WHERE school_id = %s AND role = 'owner' AND status = 'active'",
        (school_id,),
    )
    return int(cur.fetchone()["n"])


def _load_member_for_update(cur, school_id: str, member_uid: str) -> dict:
    cur.execute(
        "SELECT role FROM school_members WHERE school_id = %s AND uid = %s AND status = 'active' FOR UPDATE",
        (school_id, member_uid),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "member_not_found", "message": "Staff member not found."})
    return dict(row)


def _last_owner() -> HTTPException:
    return HTTPException(status_code=409, detail={
        "error": "last_owner",
        "message": "A school needs at least one owner. Make someone else an owner first.",
    })


def change_member_role(ctx: SchoolCtx, member_uid: str, role: str) -> dict:
    _check_can_grant(ctx.role, role)
    with get_db() as conn:
        with conn.cursor() as cur:
            # Lock the owner rows first so two concurrent demotions can't both pass the guard.
            cur.execute(
                "SELECT uid FROM school_members WHERE school_id = %s AND role = 'owner' FOR UPDATE",
                (ctx.school_id,),
            )
            member = _load_member_for_update(cur, ctx.school_id, member_uid)
            if member["role"] == "owner" and ctx.role != "owner":
                raise HTTPException(status_code=403, detail={
                    "error": "school_role_required",
                    "message": "Only an owner can change another owner's role.",
                    "required_roles": ["owner"],
                })
            if member["role"] == "owner" and role != "owner" and _active_owner_count(cur, ctx.school_id) <= 1:
                raise _last_owner()
            cur.execute(
                "UPDATE school_members SET role = %s WHERE school_id = %s AND uid = %s",
                (role, ctx.school_id, member_uid),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "staff.role_changed", "member", member_uid,
                         {"from": member["role"], "to": role})
    invalidate_school_member_cache(school_id=ctx.school_id, uid=member_uid)
    return {"uid": member_uid, "role": role}


def remove_member(ctx: SchoolCtx, member_uid: str) -> None:
    """Admins remove staff; anyone may leave. Courses the member created stay
    with the school (they're school-owned, uid NULL)."""
    leaving = member_uid == ctx.uid
    if not leaving and ctx.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={
            "error": "school_role_required",
            "message": "Only school admins can remove staff.",
            "required_roles": list(ADMIN_ROLES),
        })
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid FROM school_members WHERE school_id = %s AND role = 'owner' FOR UPDATE",
                (ctx.school_id,),
            )
            member = _load_member_for_update(cur, ctx.school_id, member_uid)
            if member["role"] == "owner":
                if not leaving and ctx.role != "owner":
                    raise HTTPException(status_code=403, detail={
                        "error": "school_role_required",
                        "message": "Only an owner can remove another owner.",
                        "required_roles": ["owner"],
                    })
                if _active_owner_count(cur, ctx.school_id) <= 1:
                    raise _last_owner()
            cur.execute(
                """
                UPDATE school_members SET status = 'removed', removed_at = now()
                 WHERE school_id = %s AND uid = %s
                """,
                (ctx.school_id, member_uid),
            )
            cur.execute("DELETE FROM class_teachers WHERE school_id = %s AND uid = %s",
                        (ctx.school_id, member_uid))
            school_audit(cur, ctx.school_id, ctx.uid, "staff.left" if leaving else "staff.removed",
                         "member", member_uid, {"role": member["role"]})
    from app.services.journey_access import invalidate_journey_access
    invalidate_school_member_cache(school_id=ctx.school_id, uid=member_uid)
    invalidate_journey_access(uid=member_uid)
