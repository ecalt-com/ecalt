import logging
import time
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException, Depends, Request

from app.core.config import settings

_admin_cache: dict[str, tuple[bool, float]] = {}
_ADMIN_CACHE_TTL = 60.0

logger = logging.getLogger(__name__)

# Google publishes the RS256 public keys for Firebase token verification here.
# PyJWKClient fetches and caches these automatically (5-min cache by default).
_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)


def _decode_firebase_token(token: str) -> Optional[dict]:
    """Verify a Firebase ID token and return its claims on success, None on failure."""
    if not settings.FIREBASE_PROJECT_ID:
        logger.warning("FIREBASE_PROJECT_ID not set — cannot verify tokens")
        return None
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}",
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Rejected token: expired")
    except jwt.InvalidAudienceError:
        logger.warning("Rejected token: wrong audience (project ID mismatch?)")
    except jwt.PyJWKClientError as e:
        logger.warning("Rejected token: could not fetch Google public keys — %s", e)
    except jwt.InvalidTokenError as e:
        logger.warning("Rejected token: invalid — %s", e)
    except Exception as e:
        logger.warning("Rejected token: unexpected error — %s: %s", type(e).__name__, e)
    return None


def _verify_firebase_token(token: str) -> Optional[str]:
    """Verify a Firebase ID token and return the uid on success, None on failure."""
    decoded = _decode_firebase_token(token)
    if not decoded:
        return None
    uid = decoded.get("uid") or decoded.get("sub")
    return uid if uid else None


def token_claims(authorization: Optional[str]) -> Optional[dict]:
    """Verified claims of the request's Firebase ID token, or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return _decode_firebase_token(authorization.split(" ", 1)[1])


def token_auth_time(authorization: Optional[str]) -> Optional[int]:
    """Epoch seconds of the user's last real sign-in (Firebase 'auth_time'
    claim — unchanged by silent token refreshes). Used to require a fresh
    Google sign-in for sensitive actions such as resetting the parent PIN."""
    decoded = token_claims(authorization)
    try:
        return int(decoded["auth_time"]) if decoded and decoded.get("auth_time") else None
    except (TypeError, ValueError):
        return None


_identity_cache: dict[str, tuple[str, float]] = {}
_IDENTITY_CACHE_TTL = 60.0


def _map_identity(firebase_uid: str) -> str:
    """Firebase uid → users.uid. Identical except for a claimed family profile,
    whose learner data stays under its original 'prof_…' uid (auth_identities).

    Fails closed: on a DB error with nothing cached, guessing the raw Firebase
    uid would hand a claimed learner an empty new account — reject instead.
    """
    from app.core.database import get_db
    now = time.monotonic()
    cached = _identity_cache.get(firebase_uid)
    if cached is not None and now - cached[1] < _IDENTITY_CACHE_TTL:
        return cached[0]
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT uid FROM auth_identities WHERE firebase_uid = %s", (firebase_uid,))
                row = cur.fetchone()
        uid = row["uid"] if row else firebase_uid
    except Exception:
        if cached is not None:
            return cached[0]
        raise HTTPException(status_code=503, detail="Could not verify your account. Please try again.")
    _identity_cache[firebase_uid] = (uid, now)
    return uid


def invalidate_identity_cache(firebase_uid: str) -> None:
    _identity_cache.pop(firebase_uid, None)


def get_signed_in_uid(request: Request, authorization: Optional[str] = Header(None)) -> Optional[str]:
    """The signed-in account's uid — never a family profile. Use for account-level
    bootstrap (POST /users) and the profile picker.

    Every authenticated dependency builds on this, so it is also where school
    students are confined to their route allowlist (core/school_auth.py)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    firebase_uid = _verify_firebase_token(token)
    if not firebase_uid:
        return None
    uid = _map_identity(firebase_uid)
    from app.core.school_auth import enforce_student_route, is_school_student_uid
    if is_school_student_uid(uid):
        enforce_student_route(request)
    return uid


_profile_access_cache: dict[tuple[str, str], tuple[bool, float]] = {}
_has_profiles_cache: dict[str, tuple[bool, float]] = {}
_PROFILE_CACHE_TTL = 60.0


def invalidate_profile_cache(parent_uid: Optional[str] = None, profile_uid: Optional[str] = None) -> None:
    """Call after creating, deleting, revoking or claiming a profile."""
    if parent_uid:
        _has_profiles_cache.pop(parent_uid, None)
    for key in list(_profile_access_cache):
        if (parent_uid and key[0] == parent_uid) or (profile_uid and key[1] == profile_uid):
            _profile_access_cache.pop(key, None)


def _verify_profile_access(account_uid: str, profile_uid: str) -> None:
    """Raise 403 unless profile_uid is a family profile managed by account_uid.

    Fails closed, and never falls back to the account's own uid: acting as the
    wrong person would write a child's activity onto the parent (or reverse).
    """
    from app.core.database import get_db
    key = (account_uid, profile_uid)
    now = time.monotonic()
    cached = _profile_access_cache.get(key)
    if cached is not None and now - cached[1] < _PROFILE_CACHE_TTL:
        ok = cached[0]
    else:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1
                          FROM family_links fl
                          JOIN users u ON u.uid = fl.child_uid
                         WHERE fl.parent_uid = %s AND fl.child_uid = %s
                           AND fl.status = 'active' AND u.profile_type = 'profile'
                        """,
                        (account_uid, profile_uid),
                    )
                    ok = cur.fetchone() is not None
            _profile_access_cache[key] = (ok, now)
        except Exception:
            ok = False
    if not ok:
        raise HTTPException(status_code=403, detail={
            "error": "profile_not_allowed",
            "message": "This profile isn't available on your account.",
        })


def get_optional_user(
    real_uid: Optional[str] = Depends(get_signed_in_uid),
    x_profile_id: Optional[str] = Header(None),
    x_impersonate_session: Optional[str] = Header(None),
) -> Optional[str]:
    """The uid whose data this request reads and writes: the signed-in account,
    or one of its family profiles when X-Profile-Id names one. None when
    unauthenticated. Every learner dependency below builds on this."""
    if not real_uid:
        return None
    if not x_profile_id or x_profile_id == real_uid:
        return real_uid
    if x_impersonate_session:
        raise HTTPException(status_code=400, detail={
            "error": "conflicting_headers",
            "message": "Can't switch profiles while impersonating.",
        })
    _verify_profile_access(real_uid, x_profile_id)
    return x_profile_id


def get_required_user(uid: Optional[str] = Depends(get_optional_user)) -> str:
    """Like get_optional_user but raises 401 if no valid token."""
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return uid


# ── Account-holder (parent-only) dependencies ────────────────────────────────

def get_bootstrap_uid(
    real_uid: Optional[str] = Depends(get_signed_in_uid),
    x_profile_id: Optional[str] = Header(None),
) -> str:
    """Like get_account_holder, but also lets a school student through. Only
    for POST /users, which returns early for students (no age or consent gate:
    the school authorised them)."""
    if not real_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    if x_profile_id and x_profile_id != real_uid:
        raise HTTPException(status_code=403, detail={
            "error": "parent_profile_required",
            "message": "Switch to the parent profile to do this.",
        })
    return real_uid


def get_account_holder(
    real_uid: Optional[str] = Depends(get_signed_in_uid),
    x_profile_id: Optional[str] = Header(None),
) -> str:
    """The signed-in account itself. Rejects requests made from inside a child
    profile — family controls, billing and account deletion belong to the
    account holder, never to a profile — and school students, who have no
    account of their own (second layer behind the student route allowlist)."""
    uid = get_bootstrap_uid(real_uid, x_profile_id)
    from app.core.school_auth import is_school_student_uid, student_not_allowed
    if is_school_student_uid(uid):
        raise student_not_allowed()
    return uid


def account_has_profiles(uid: str) -> bool:
    """True when the account manages at least one family profile. Cached 60 s;
    a DB error counts as True so the unlock requirement fails closed."""
    from app.core.database import get_db
    now = time.monotonic()
    cached = _has_profiles_cache.get(uid)
    if cached is not None and now - cached[1] < _PROFILE_CACHE_TTL:
        return cached[0]
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                      FROM family_links fl
                      JOIN users u ON u.uid = fl.child_uid
                     WHERE fl.parent_uid = %s AND fl.status = 'active'
                       AND u.profile_type = 'profile'
                     LIMIT 1
                    """,
                    (uid,),
                )
                has = cur.fetchone() is not None
    except Exception:
        return True
    _has_profiles_cache[uid] = (has, now)
    return has


def require_parent_unlock(uid: str, unlock_token: Optional[str]) -> None:
    """Accounts with family profiles must present a fresh PIN unlock token for
    parent-only actions, so a child on a shared device can't reach them by
    calling the API without the profile header."""
    from app.services.profile_service import verify_unlock_token
    if account_has_profiles(uid) and not verify_unlock_token(unlock_token, uid):
        raise HTTPException(status_code=403, detail={
            "error": "parent_unlock_required",
            "message": "Enter your parent PIN to continue.",
        })


def get_unlocked_account_holder(
    uid: str = Depends(get_account_holder),
    x_parent_unlock: Optional[str] = Header(None),
) -> str:
    """Account holder + parent PIN unlock (when the account has profiles).
    No account-status check — e.g. a consent-pending teen may still delete."""
    require_parent_unlock(uid, x_parent_unlock)
    return uid


def get_active_account_holder(uid: str = Depends(get_account_holder)) -> str:
    """Account holder whose account is active. No PIN needed — use for the
    profile picker and setting the PIN."""
    assert_account_active(uid)
    return uid


def get_active_signed_in_account(real_uid: Optional[str] = Depends(get_signed_in_uid)) -> str:
    """The signed-in account, active, even when the request comes from inside a
    child profile. Only for the PIN check and PIN reset: they are how a parent
    leaves a child's profile, and the PIN (or a fresh Google sign-in) is the gate."""
    if not real_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app.core.school_auth import is_school_student_uid, student_not_allowed
    if is_school_student_uid(real_uid):
        raise student_not_allowed()
    assert_account_active(real_uid)
    return real_uid


def get_parent_session(
    uid: str = Depends(get_active_account_holder),
    x_parent_unlock: Optional[str] = Header(None),
) -> str:
    """Active account holder + parent PIN unlock. Default for /family routes."""
    require_parent_unlock(uid, x_parent_unlock)
    return uid


_status_cache: dict[str, tuple[str, float]] = {}
_STATUS_CACHE_TTL = 60.0


def invalidate_status_cache(uid: str) -> None:
    """Call when account_status changes (e.g. consent granted) so the user isn't
    blocked for up to a TTL by a stale cached status."""
    _status_cache.pop(uid, None)


def get_active_user(uid: str = Depends(get_required_user)) -> str:
    """Like get_required_user but raises 403 if the account is consent-pending
    or paused by the managing parent."""
    assert_account_active(uid)
    return uid


def assert_account_active(uid: str) -> None:
    """Raise 403 if the account is consent-pending or paused by the managing
    parent. Use directly in endpoints with optional auth.

    Fails closed: if the status can't be determined (DB error, nothing cached),
    the request is rejected rather than letting a blocked child through.
    Status is cached for 60 s per uid to keep the hot path off the DB.
    """
    from app.core.database import get_db
    from app.core.school_auth import OPEN_SCHOOL_STATUSES, is_school_student_uid
    now = time.monotonic()
    cached = _status_cache.get(uid)
    if cached is not None and now - cached[1] < _STATUS_CACHE_TTL:
        status = cached[0]
    else:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    if is_school_student_uid(uid):
                        # Students are created by their school, never mid-sign-up:
                        # no row (or an archived student / closed school) blocks.
                        cur.execute(
                            """
                            SELECT ss.status AS student_status, s.status AS school_status
                              FROM school_students ss
                              JOIN schools s ON s.id = ss.school_id
                             WHERE ss.uid = %s
                            """,
                            (uid,),
                        )
                        row = cur.fetchone()
                        if (row and row["student_status"] == "active"
                                and row["school_status"] in OPEN_SCHOOL_STATUSES):
                            status = "active"
                        else:
                            status = "school_suspended"
                    else:
                        cur.execute("SELECT account_status, paused FROM users WHERE uid = %s", (uid,))
                        row = cur.fetchone()
                        # No row yet = user record mid-creation on first sign-in — allow.
                        if row and row.get("paused"):
                            status = "paused"
                        else:
                            status = (row.get("account_status") if row else None) or "active"
            _status_cache[uid] = (status, now)
        except Exception:
            if cached is not None:
                status = cached[0]  # stale but known beats guessing
            else:
                raise HTTPException(
                    status_code=503,
                    detail="Could not verify account status. Please try again.",
                )

    if status == "parental_consent_pending":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "consent_pending",
                "message": "Your account is waiting for parental approval. Check your parent's inbox.",
            },
        )
    if status == "paused":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_paused",
                "message": "Your account is paused. Ask your parent to unpause it from the Family dashboard.",
            },
        )
    if status == "school_suspended":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "school_access_suspended",
                "message": "Your school sign-in isn't active right now. Ask your teacher.",
            },
        )


def ensure_chat_allowed(uid: str) -> None:
    """Parental control: raise 403 when the managing parent disabled AI chat.
    No child_settings row (the common case for unlinked users) means allowed."""
    from app.core.database import get_db
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chat_enabled FROM child_settings WHERE child_uid = %s",
                    (uid,),
                )
                row = cur.fetchone()
    except Exception:
        return  # settings lookup failure must not take chat down for everyone
    if row is not None and not row.get("chat_enabled"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "chat_disabled",
                "message": "AI chat is turned off for your account. Ask your parent to enable it.",
            },
        )


def verify_parent_of(parent_uid: str, child_uid: str) -> None:
    """Raise 403 unless parent_uid has an active family link to child_uid.

    Fails closed — parental access to a child's account must never be granted
    on a DB error.
    """
    from app.core.database import get_db
    ok = False
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM family_links WHERE parent_uid = %s AND child_uid = %s AND status = 'active'",
                    (parent_uid, child_uid),
                )
                ok = cur.fetchone() is not None
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=403, detail="You do not manage this account")


def get_admin_user(uid: str = Depends(get_required_user)) -> str:
    """Raises 403 if user is not an admin. Result is cached for 60 s per uid."""
    now = time.monotonic()
    cached = _admin_cache.get(uid)
    if cached is not None:
        is_admin, ts = cached
        if now - ts < _ADMIN_CACHE_TTL:
            if not is_admin:
                raise HTTPException(status_code=403, detail="Admin access required")
            return uid

    from app.core.database import get_db
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                is_admin = bool(row and row["is_admin"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin access required")

    _admin_cache[uid] = (is_admin, now)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return uid


def _check_admin(uid: str) -> None:
    """Raise 403 if uid is not an admin. Uses the same cache as get_admin_user."""
    now = time.monotonic()
    cached = _admin_cache.get(uid)
    if cached is not None:
        is_admin, ts = cached
        if now - ts < _ADMIN_CACHE_TTL:
            if not is_admin:
                raise HTTPException(status_code=403, detail="Admin access required")
            return

    from app.core.database import get_db
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                is_admin = bool(row and row["is_admin"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin access required")

    _admin_cache[uid] = (is_admin, now)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _resolve_impersonation_session(session_id: str) -> Optional[tuple[str, str]]:
    """
    Validate an impersonation session ID.
    Returns (target_uid, admin_uid) if valid and not expired, else None.
    """
    from app.core.database import get_db
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT target_uid, admin_uid
                    FROM admin_impersonation_sessions
                    WHERE id = %s
                      AND ended_at IS NULL
                      AND expires_at > now()
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
        if row:
            return row["target_uid"], row["admin_uid"]
    except Exception:
        pass
    return None


def get_acting_uid(
    real_uid: str = Depends(get_required_user),
    x_impersonate_session: Optional[str] = Header(None),
) -> tuple[str, str]:
    """
    Returns (acting_uid, real_uid).
    acting_uid — the uid used for data queries (may be a different user when impersonating).
    real_uid   — always the authenticated Firebase user.
    When no valid impersonation session is present, both values are identical.
    """
    if x_impersonate_session:
        result = _resolve_impersonation_session(x_impersonate_session)
        if result:
            target_uid, session_admin_uid = result
            # Confirm the real caller is still an admin and matches the session owner
            _check_admin(real_uid)
            if session_admin_uid != real_uid:
                raise HTTPException(status_code=403, detail="Impersonation session belongs to a different admin")
            return target_uid, real_uid
        # Invalid/expired session — reject rather than silently fall back to real uid
        raise HTTPException(status_code=403, detail="Impersonation session is invalid or expired")
    return real_uid, real_uid


def get_active_acting_uid(ctx: tuple[str, str] = Depends(get_acting_uid)) -> tuple[str, str]:
    """get_acting_uid + the paused / consent-pending block. Use on endpoints
    that generate AI content or write learner data. An admin impersonating a
    blocked account is let through so support can still inspect it."""
    acting_uid, real_uid = ctx
    if acting_uid == real_uid:
        assert_account_active(real_uid)
    return ctx


def get_optional_acting_uid(
    real_uid: Optional[str] = Depends(get_optional_user),
    x_impersonate_session: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Like get_acting_uid but for endpoints that allow unauthenticated access.
    Returns None when no auth, target_uid when impersonating, real_uid otherwise.
    """
    if not real_uid:
        return None
    if x_impersonate_session:
        result = _resolve_impersonation_session(x_impersonate_session)
        if result:
            target_uid, session_admin_uid = result
            _check_admin(real_uid)
            if session_admin_uid != real_uid:
                raise HTTPException(status_code=403, detail="Impersonation session belongs to a different admin")
            return target_uid
        raise HTTPException(status_code=403, detail="Impersonation session is invalid or expired")
    return real_uid
