import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, computed_field

from app.core.auth import (
    assert_account_active,
    get_account_holder,
    get_acting_uid,
    get_bootstrap_uid,
    get_required_user,
    get_unlocked_account_holder,
    invalidate_identity_cache,
    invalidate_profile_cache,
    invalidate_status_cache,
)
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.school_auth import is_school_student_uid
from app.core.jurisdiction import (
    CONSENT_POLICY_VERSION,
    age_from_birth,
    is_hard_blocked,
    required_verification_tier,
    requires_parental_consent,
)
from app.services.consent_service import (
    hash_ip,
    record_consent_event,
    schedule_email_plus_followup,
    verify_consent_report_token,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    onboarding_done: bool = False
    streak_days: int = 0
    whatsapp_opted_in: bool = False
    has_notification_prefs: bool = False
    account_status: str = "active"
    consent_given_at: Optional[datetime] = None
    needs_birth_year: bool = False
    # Echoed back so a pending teen who re-logs in can resubmit the consent
    # request (the upsert's teen branch requires birth_year in the body).
    birth_year: Optional[int] = None
    birth_month: Optional[int] = None
    profession: Optional[str] = None
    role: str = "learner"  # 'parent' once they manage a family
    # Parental-control state, so the client can show the right screen at
    # sign-in: a managed child awaiting the parent's card check must not be
    # shown the self-signup "enter your parent's email" form.
    managed: bool = False
    paused: bool = False
    # Family profiles: 'profile' = a child profile used through the parent's login.
    profile_type: str = "account"
    avatar: Optional[str] = None
    age_group_flag: Optional[str] = None
    # School students (plans/school-courses): {id, name} and
    # {display_name, grade, classes: [{id, name, grade, subject}]}.
    school: Optional[dict] = None
    student: Optional[dict] = None

    @computed_field
    @property
    def account_kind(self) -> str:
        """'account' | 'profile' | 'school_student' — drives the client's
        post-sign-in flow (school students skip every sign-up gate)."""
        return self.profile_type


class UserUpsertRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    birth_year: Optional[int] = None
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    parent_email: Optional[str] = None
    country: Optional[str] = Field(None, min_length=2, max_length=2,
                                   description="ISO 3166-1 alpha-2, from geo detection or user declaration")


def _load_existing_user(uid: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.birth_year, u.account_status, u.consent_given_at, u.jurisdiction,
                       COALESCE(cs.managed, false) AS managed
                  FROM users u
             LEFT JOIN child_settings cs ON cs.child_uid = u.uid
                 WHERE u.uid = %s
                """,
                (uid,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def _is_managed(uid: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT managed FROM child_settings WHERE child_uid = %s", (uid,))
            row = cur.fetchone()
    return bool(row and row.get("managed"))


def _issue_consent_request(uid: str, parent_email: str, jurisdiction: Optional[str],
                           ip: Optional[str]) -> str:
    """Create a fresh consent token. Earlier tokens are marked superseded,
    never deleted — the request trail is part of the consent record."""
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE parental_consent SET status = 'superseded' "
                "WHERE uid = %s AND status = 'pending'",
                (uid,),
            )
            cur.execute(
                """
                INSERT INTO parental_consent (token, uid, parent_email, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (token, uid, parent_email, expires_at),
            )
            record_consent_event(
                uid, "requested",
                parent_email=parent_email, method="email_link",
                jurisdiction=jurisdiction, ip_hash=ip, cur=cur,
            )
    return token


def _update_profile_only(uid: str, body: UserUpsertRequest) -> UserProfile:
    """Refresh display fields only — never age, status or consent."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (uid, email, display_name, photo_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE
                    SET email        = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        photo_url    = EXCLUDED.photo_url
                RETURNING *
                """,
                (uid, body.email, body.display_name, body.photo_url),
            )
            row = dict(cur.fetchone())
    return UserProfile(**{
        **row,
        "needs_birth_year": row.get("birth_year") is None,
        "managed": _is_managed(uid),
    })


def _school_student_profile(uid: str) -> UserProfile:
    """Profile for a school student. Their school created the account and
    recorded the school authorisation, so there is no age or consent gate and
    nothing the client may update."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.uid, u.streak_days, u.profile_type,
                       ss.display_name, ss.grade, ss.avatar,
                       s.id AS school_id, s.name AS school_name
                  FROM users u
                  JOIN school_students ss ON ss.uid = u.uid
                  JOIN schools s ON s.id = ss.school_id
                 WHERE u.uid = %s
                """,
                (uid,),
            )
            row = cur.fetchone()
            cur.execute(
                """
                SELECT c.id::text AS id, c.name, c.grade, c.subject
                  FROM class_enrollments e
                  JOIN classes c ON c.id = e.class_id AND c.archived_at IS NULL
                 WHERE e.student_uid = %s AND e.removed_at IS NULL
                 ORDER BY c.name
                """,
                (uid,),
            )
            classes = [dict(r) for r in cur.fetchall()]
    if not row:
        raise HTTPException(status_code=403, detail={
            "error": "school_access_suspended",
            "message": "Your school sign-in isn't active right now. Ask your teacher.",
        })
    return UserProfile(
        uid=uid,
        display_name=row["display_name"],
        onboarding_done=True,
        streak_days=row["streak_days"] or 0,
        profile_type="school_student",
        avatar=row["avatar"],
        school={"id": str(row["school_id"]), "name": row["school_name"]},
        student={"display_name": row["display_name"], "grade": row["grade"], "classes": classes},
    )


@router.post("", response_model=UserProfile, summary="Upsert user on sign-in")
async def upsert_user(body: UserUpsertRequest, request: Request, uid: str = Depends(get_bootstrap_uid)):
    """Called once after Google sign-in. Enforces the COPPA/GDPR/DPDP age gate when birth_year is provided."""
    if is_school_student_uid(uid):
        assert_account_active(uid)
        return _school_student_profile(uid)
    if body.birth_year is not None:
        existing = _load_existing_user(uid)
        if existing and existing.get("birth_year") is not None:
            # Birth data is immutable once recorded. Re-submitting a different
            # birth year must never re-run the age gate: an adult year would
            # lift a pending teen or managed child straight to 'active', and an
            # under-13 year would purge a managed child's parent-made login.
            # The one legitimate re-submit is a self-signup teen still waiting
            # on consent, re-sending the request (judged on the STORED age).
            if (body.parent_email
                    and existing.get("account_status") == "parental_consent_pending"
                    and existing.get("consent_given_at") is None
                    and not existing.get("managed")):
                profile = _update_profile_only(uid, body)
                jurisdiction = existing.get("jurisdiction")
                token = _issue_consent_request(
                    uid, body.parent_email, jurisdiction,
                    hash_ip(request.client.host if request.client else None),
                )
                from app.services.email_service import send_parental_consent_email
                asyncio.ensure_future(send_parental_consent_email(body.parent_email, uid, token))
                return profile
            return _update_profile_only(uid, body)

    if body.birth_year is not None:
        age = age_from_birth(body.birth_year, body.birth_month)
        jurisdiction = body.country.strip().upper() if body.country else None
        ip = hash_ip(request.client.host if request.client else None)

        # COPPA absolute requirement: under-13 data must never be collected.
        # Google sign-in already created a Firebase Auth record (name, email,
        # photo) before this gate ran — purge it so no child PII is retained.
        if is_hard_blocked(age):
            from app.services.firebase_admin import delete_firebase_user
            asyncio.ensure_future(delete_firebase_user(uid))
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "under_13",
                    "message": (
                        "ECALT is for learners aged 13 and over. "
                        "Please ask a parent or guardian to create an account."
                    ),
                },
            )

        if requires_parental_consent(age):
            if not body.parent_email:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "parent_email_required",
                        "message": "Parental consent is required for users aged 13–17.",
                    },
                )
            # Insert with pending status — account locked until parent confirms.
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (uid, email, display_name, photo_url,
                                          birth_year, birth_month, jurisdiction,
                                          age_group_flag, account_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'teen', 'parental_consent_pending')
                        ON CONFLICT (uid) DO UPDATE
                            SET email          = EXCLUDED.email,
                                display_name   = EXCLUDED.display_name,
                                photo_url      = EXCLUDED.photo_url,
                                birth_year     = EXCLUDED.birth_year,
                                birth_month    = EXCLUDED.birth_month,
                                jurisdiction   = COALESCE(users.jurisdiction, EXCLUDED.jurisdiction),
                                age_group_flag = EXCLUDED.age_group_flag,
                                account_status = CASE
                                    WHEN users.birth_year IS NULL THEN EXCLUDED.account_status
                                    ELSE users.account_status
                                END
                        RETURNING *
                        """,
                        (uid, body.email, body.display_name, body.photo_url,
                         body.birth_year, body.birth_month, jurisdiction),
                    )
                    row = cur.fetchone()

            token = _issue_consent_request(uid, body.parent_email, jurisdiction, ip)

            # Fire-and-forget consent email
            from app.services.email_service import send_parental_consent_email
            asyncio.ensure_future(send_parental_consent_email(body.parent_email, uid, token))

            return UserProfile(**dict(row))

        # Adult: standard flow — record self-consent
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT consent_given_at FROM users WHERE uid = %s", (uid,))
                prior = cur.fetchone()
                already_consented = bool(prior and dict(prior).get("consent_given_at"))
                cur.execute(
                    """
                    INSERT INTO users (uid, email, display_name, photo_url,
                                      birth_year, birth_month, jurisdiction,
                                      age_group_flag, account_status,
                                      consent_given_at, consent_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'adult', 'active', now(), %s)
                    ON CONFLICT (uid) DO UPDATE
                        SET email            = EXCLUDED.email,
                            display_name     = EXCLUDED.display_name,
                            photo_url        = EXCLUDED.photo_url,
                            birth_year       = EXCLUDED.birth_year,
                            birth_month      = EXCLUDED.birth_month,
                            jurisdiction     = COALESCE(users.jurisdiction, EXCLUDED.jurisdiction),
                            age_group_flag   = EXCLUDED.age_group_flag,
                            account_status   = EXCLUDED.account_status,
                            consent_given_at = COALESCE(users.consent_given_at, EXCLUDED.consent_given_at),
                            consent_version  = EXCLUDED.consent_version
                    RETURNING *
                    """,
                    (uid, body.email, body.display_name, body.photo_url,
                     body.birth_year, body.birth_month, jurisdiction, CONSENT_POLICY_VERSION),
                )
                row = cur.fetchone()
                if not already_consented:
                    record_consent_event(
                        uid, "self_consent", method="signup",
                        jurisdiction=jurisdiction, ip_hash=ip, cur=cur,
                    )
        return UserProfile(**dict(row))

    # No birth_year (re-login or legacy client): update profile only
    return _update_profile_only(uid, body)


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
def get_me(ctx: tuple = Depends(get_acting_uid)):
    uid, _ = ctx
    if is_school_student_uid(uid):
        return _school_student_profile(uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*,
                       COALESCE(np.whatsapp_opted_in, FALSE) AS whatsapp_opted_in,
                       (np.uid IS NOT NULL)                  AS has_notification_prefs,
                       COALESCE(cs.managed, FALSE)           AS managed
                  FROM users u
             LEFT JOIN notification_preferences np ON np.uid = u.uid
             LEFT JOIN child_settings cs ON cs.child_uid = u.uid
                 WHERE u.uid = %s
                """,
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        return UserProfile(uid=uid)
    return UserProfile(**dict(row))


@router.patch("/me/onboarding", response_model=UserProfile, summary="Mark onboarding complete")
def complete_onboarding(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET onboarding_done = TRUE WHERE uid = %s RETURNING *",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**dict(row))


class InterestsRequest(BaseModel):
    topics: list[str]
    age_group: str = "all"


@router.patch("/me/interests", summary="Save user interest topics")
def save_interests(body: InterestsRequest, uid: str = Depends(get_required_user)):
    topics = [t.lower()[:50] for t in body.topics[:12]]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_interests (uid, topics, age_group)
                VALUES (%s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    topics = EXCLUDED.topics,
                    age_group = EXCLUDED.age_group,
                    last_updated = now()
                """,
                (uid, topics, body.age_group),
            )
    # Invalidate daily spark cache
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_sparks WHERE uid = %s", (uid,))
    return {"saved": True}


class ProfessionRequest(BaseModel):
    profession: str = Field(..., min_length=1, max_length=200)


@router.patch("/me/profession", summary="Save or update the user's profession")
def save_profession(body: ProfessionRequest, uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET profession = %s WHERE uid = %s",
                (body.profession.strip(), uid),
            )
    return {"saved": True}


# ── Claim a family profile with your own Google login ──────────────────────

class ClaimRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=16)


@router.post("/claim", summary="Attach the caller's Google login to a family profile")
@limiter.limit("10/hour")
def claim_profile(body: ClaimRequest, request: Request):
    """The child signs in with their own Google account and redeems the code
    their parent created. The profile keeps its uid and all learner data;
    auth_identities maps the new Firebase login onto it."""
    from app.core.auth import token_claims
    claims = token_claims(request.headers.get("authorization"))
    firebase_uid = claims and (claims.get("uid") or claims.get("sub"))
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Profiles have no login; a school student's login belongs to the school and
    # must never be re-pointed at a family profile (that would escape the
    # student route allowlist).
    if firebase_uid.startswith("prof_") or is_school_student_uid(firebase_uid):
        raise HTTPException(status_code=400, detail={"error": "invalid_login"})
    code = body.code.strip().upper()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pc.uid, pc.parent_uid, pc.expires_at, pc.claimed_at,
                       u.profile_type, u.jurisdiction
                  FROM profile_claims pc
                  JOIN users u ON u.uid = pc.uid
                  JOIN family_links fl ON fl.child_uid = pc.uid
                                      AND fl.parent_uid = pc.parent_uid
                                      AND fl.status = 'active'
                 WHERE pc.code = %s
                 FOR UPDATE OF pc
                """,
                (code,),
            )
            invite = cur.fetchone()
            expires_at = invite and invite["expires_at"]
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if (not invite or invite["claimed_at"] is not None
                    or invite["profile_type"] != "profile"
                    or expires_at <= datetime.now(timezone.utc)):
                raise HTTPException(status_code=400, detail={
                    "error": "invalid_claim_code",
                    "message": "This code is invalid or has expired. Ask your parent for a new one.",
                })

            cur.execute("SELECT 1 FROM auth_identities WHERE firebase_uid = %s", (firebase_uid,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "account_exists",
                    "message": "This Google account is already linked to an ECALT profile.",
                })
            # A row with no birth year is the sign-in stub created before any
            # age gate — it holds only name/email, so it's safe to replace.
            # Anything more is a real account we must not silently abandon.
            cur.execute("SELECT birth_year FROM users WHERE uid = %s", (firebase_uid,))
            existing = cur.fetchone()
            if existing and existing.get("birth_year") is not None:
                raise HTTPException(status_code=409, detail={
                    "error": "account_exists",
                    "message": "This Google account already has its own ECALT account. "
                               "Sign in with a different Google account to claim this profile.",
                })
            if existing:
                cur.execute("DELETE FROM notification_preferences WHERE uid = %s", (firebase_uid,))
                cur.execute("DELETE FROM users WHERE uid = %s", (firebase_uid,))

            profile_uid = invite["uid"]
            cur.execute(
                "INSERT INTO auth_identities (firebase_uid, uid) VALUES (%s, %s)",
                (firebase_uid, profile_uid),
            )
            cur.execute(
                "UPDATE users SET profile_type = 'account', email = %s, "
                "photo_url = COALESCE(%s, photo_url) WHERE uid = %s",
                (claims.get("email"), claims.get("picture"), profile_uid),
            )
            cur.execute("UPDATE profile_claims SET claimed_at = now() WHERE code = %s", (code,))
            record_consent_event(
                profile_uid, "granted",
                parent_uid=invite["parent_uid"], method="claim",
                jurisdiction=invite.get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"trigger": "child_claimed_own_login"}, cur=cur,
            )

    invalidate_identity_cache(firebase_uid)
    invalidate_profile_cache(parent_uid=invite["parent_uid"], profile_uid=profile_uid)
    invalidate_status_cache(profile_uid)
    return {"status": "claimed", "uid": profile_uid}


# ── COPPA parental consent confirmation (no auth) ─────────────────────────────
# The GET is strictly read-only: email link prefetchers (Outlook SafeLinks etc.)
# follow GETs automatically, so consent must only ever be granted via the POST
# below, triggered by the parent pressing an explicit button.


def _load_consent_token(token: str) -> dict:
    """Fetch and validate a consent token row. Raises 400 unless it is pending."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pc.uid, pc.expires_at, pc.status, pc.parent_email,
                       u.display_name, u.birth_year, u.birth_month, u.jurisdiction
                  FROM parental_consent pc
             LEFT JOIN users u ON u.uid = pc.uid
                 WHERE pc.token = %s
                """,
                (token,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_token", "message": "This confirmation link is invalid."},
        )

    if row["status"] == "superseded":
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_token", "message": "This link was replaced by a newer email. Please use the most recent one."},
        )

    if row["status"] in ("confirmed", "refused"):
        return dict(row)

    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail={"error": "token_expired", "message": "This confirmation link has expired. Please ask your child to sign up again."},
        )

    return dict(row)


@router.get("/consent/confirm", summary="Check a parental consent token (read-only)")
def consent_status(token: str = Query(..., description="UUID token from consent email")):
    row = _load_consent_token(token)
    if row["status"] == "confirmed":
        return {"status": "already_confirmed", "message": "This account is already active."}
    if row["status"] == "refused":
        return {"status": "refused", "message": "Consent was declined for this account."}
    return {
        "status": "pending_review",
        "child_name": row.get("display_name"),
        "parent_email": row.get("parent_email"),
    }


class ConsentDecisionRequest(BaseModel):
    token: str
    approved: bool


@router.post("/consent/confirm", summary="Record the parent's consent decision")
def consent_decide(body: ConsentDecisionRequest, request: Request):
    row = _load_consent_token(body.token)
    if row["status"] == "confirmed":
        return {"status": "already_confirmed", "message": "This account is already active."}
    if row["status"] == "refused":
        return {"status": "refused", "message": "Consent was already declined for this account."}

    uid = row["uid"]
    ip = hash_ip(request.client.host if request.client else None)

    if body.approved:
        # Jurisdictions on the 'card' tier need a verified parent — the
        # anonymous email link isn't enough. The parent signs in and verifies
        # from the Family dashboard instead (POST /family/link-requests/...).
        if row.get("birth_year") is not None:
            child_age = age_from_birth(row["birth_year"], row.get("birth_month"))
            tier = required_verification_tier(row.get("jurisdiction"), child_age)
            if tier != "email_plus":
                return {
                    "status": "verification_required",
                    "message": "This region requires identity verification. Please sign in "
                               "with your own Google account on this page to continue.",
                }
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE parental_consent SET status = 'confirmed', confirmed_at = now() WHERE token = %s",
                    (body.token,),
                )
                cur.execute(
                    "UPDATE users SET account_status = 'active', consent_given_at = now(), consent_version = %s WHERE uid = %s",
                    (CONSENT_POLICY_VERSION, uid),
                )
                record_consent_event(
                    uid, "granted",
                    parent_email=row.get("parent_email"), method="email_link",
                    jurisdiction=row.get("jurisdiction"),
                    ip_hash=ip, cur=cur,
                )
                schedule_email_plus_followup(
                    uid, None, row["parent_email"], row.get("display_name"), cur=cur,
                )
        invalidate_status_cache(uid)
        return {"status": "confirmed", "message": "Account approved. Your child can now log in to ECALT."}

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE parental_consent SET status = 'refused' WHERE token = %s",
                (body.token,),
            )
            record_consent_event(
                uid, "refused",
                parent_email=row.get("parent_email"), method="email_link",
                jurisdiction=row.get("jurisdiction"),
                ip_hash=ip, cur=cur,
            )
    return {"status": "refused", "message": "Understood — the account will not be activated."}


# ── Consent email resend (rate-limited; caller is the pending child) ──────────

@router.post("/consent/resend", summary="Resend the parental consent email")
@limiter.limit("3/hour")
async def consent_resend(request: Request, uid: str = Depends(get_account_holder)):
    # async so ensure_future below has a running event loop (a sync endpoint
    # runs in a worker thread, where it raises "no current event loop").
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT account_status, jurisdiction FROM users WHERE uid = %s", (uid,))
            row = cur.fetchone()
            if not row or row.get("account_status") != "parental_consent_pending":
                raise HTTPException(status_code=400, detail={
                    "error": "not_pending", "message": "This account isn't waiting for consent.",
                })
            cur.execute(
                "SELECT parent_email FROM parental_consent WHERE uid = %s "
                "ORDER BY sent_at DESC LIMIT 1",
                (uid,),
            )
            prev = cur.fetchone()
            if not prev:
                raise HTTPException(status_code=404, detail={
                    "error": "no_request", "message": "No consent request found. Please sign up again.",
                })
            parent_email = prev["parent_email"]
            token = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            cur.execute(
                "UPDATE parental_consent SET status = 'superseded' WHERE uid = %s AND status = 'pending'",
                (uid,),
            )
            cur.execute(
                "INSERT INTO parental_consent (token, uid, parent_email, expires_at) VALUES (%s, %s, %s, %s)",
                (token, uid, parent_email, expires_at),
            )
            record_consent_event(
                uid, "requested", parent_email=parent_email, method="email_link",
                jurisdiction=row.get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"resend": True}, cur=cur,
            )

    from app.services.email_service import send_parental_consent_email
    asyncio.ensure_future(send_parental_consent_email(parent_email, uid, token))
    return {"status": "sent", "parent_email": parent_email}


# ── Email-plus objection: "this wasn't me" (no auth; HMAC token is the capability) ─

class ConsentReportRequest(BaseModel):
    child_uid: str
    token: str


@router.post("/consent/report", summary="Report an unauthorized consent approval")
def consent_report(body: ConsentReportRequest, request: Request):
    if not verify_consent_report_token(body.child_uid, body.token):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_token", "message": "This report link is invalid."},
        )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT jurisdiction FROM users WHERE uid = %s", (body.child_uid,))
            jrow = cur.fetchone()
            if not jrow:
                # Account already deleted — nothing to suspend, still acknowledge.
                return {"status": "reported", "message": "This account no longer exists."}
            # Suspend immediately: consent is disputed, so the account goes back
            # behind the consent gate until it is re-approved.
            cur.execute(
                "UPDATE users SET account_status = 'parental_consent_pending' WHERE uid = %s",
                (body.child_uid,),
            )
            cur.execute(
                "UPDATE parental_consent SET status = 'refused' WHERE uid = %s AND status = 'confirmed'",
                (body.child_uid,),
            )
            cur.execute(
                "UPDATE child_settings SET verification_status = 'unverified' WHERE child_uid = %s",
                (body.child_uid,),
            )
            record_consent_event(
                body.child_uid, "reported", method="email_plus",
                jurisdiction=dict(jrow).get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"trigger": "followup_objection"}, cur=cur,
            )
    invalidate_status_cache(body.child_uid)
    return {
        "status": "reported",
        "message": "The account has been suspended. Our team will follow up — "
                   "contact support@ecalt.com if you need anything else.",
    }


# ── GDPR: consent record ──────────────────────────────────────────────────────

@router.get("/me/consent", summary="Get consent record (GDPR transparency)")
def get_consent(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT account_status, consent_given_at, consent_version, birth_year FROM users WHERE uid = %s",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    d = dict(row)
    if d.get("consent_given_at") and hasattr(d["consent_given_at"], "isoformat"):
        d["consent_given_at"] = d["consent_given_at"].isoformat()
    d["current_policy_version"] = CONSENT_POLICY_VERSION
    d["needs_reconsent"] = bool(
        d.get("consent_given_at") and d.get("consent_version") != CONSENT_POLICY_VERSION
    )
    return d


@router.post("/me/reconsent", summary="Accept the current privacy policy version")
def reconsent(request: Request, uid: str = Depends(get_account_holder)):
    """Called after a policy-version bump (frontend shows the re-consent banner)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consent_version, jurisdiction FROM users WHERE uid = %s", (uid,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if row.get("consent_version") == CONSENT_POLICY_VERSION:
                return {"status": "current", "policy_version": CONSENT_POLICY_VERSION}
            cur.execute(
                "UPDATE users SET consent_version = %s, consent_given_at = now() WHERE uid = %s",
                (CONSENT_POLICY_VERSION, uid),
            )
            record_consent_event(
                uid, "reconsent", method="signup",
                jurisdiction=row.get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"from_version": row.get("consent_version")}, cur=cur,
            )
    return {"status": "reconsented", "policy_version": CONSENT_POLICY_VERSION}


# ── GDPR: data portability ────────────────────────────────────────────────────

@router.get("/me/export", summary="Export all personal data (GDPR Art. 20)")
def export_account(uid: str = Depends(get_unlocked_account_holder)):
    from app.services.account_service import build_user_export
    return JSONResponse(
        content=build_user_export(uid),
        headers={"Content-Disposition": "attachment; filename=ecalt-data-export.json"},
    )


# ── GDPR: right to erasure ────────────────────────────────────────────────────

@router.delete("/me", status_code=204, summary="Delete account and all personal data (GDPR Art. 17)")
async def delete_account(uid: str = Depends(get_unlocked_account_holder)):
    # Child profiles (no login of their own) and managed under-13s can't exist
    # without a consent holder — those must be deleted first. Teens with their
    # own login are unlinked and notified instead.
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fl.child_uid, u.email, u.display_name, u.age_group_flag,
                       u.profile_type, COALESCE(cs.managed, false) AS managed
                  FROM family_links fl
                  JOIN users u ON u.uid = fl.child_uid
             LEFT JOIN child_settings cs ON cs.child_uid = fl.child_uid
                 WHERE fl.parent_uid = %s AND fl.status = 'active'
                """,
                (uid,),
            )
            links = [dict(r) for r in cur.fetchall()]

    blockers = [l for l in links
                if l.get("profile_type") == "profile"
                or (l["managed"] and l["age_group_flag"] == "child")]
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "managed_children_exist",
                "message": "Delete your children's profiles from the Family dashboard before deleting your own.",
            },
        )

    from app.services.account_service import delete_user_account
    delete_user_account(uid)

    # Teens whose family link just ended get a heads-up (best-effort).
    from app.services.email_service import send_family_notice_email
    for link in links:
        if link.get("email"):
            try:
                await send_family_notice_email(
                    link["email"], link["child_uid"],
                    "Your ECALT family link has ended",
                    ["The parent account linked to yours was deleted, so your family link has "
                     "ended and your account is now self-managed. Your journeys and progress "
                     "are unaffected."],
                )
            except Exception:
                logger.warning("unlink notice failed for child=%s", link["child_uid"])

    # Erasure includes the auth record itself (no-op until service account is configured).
    from app.services.firebase_admin import purge_login
    await purge_login(uid)
