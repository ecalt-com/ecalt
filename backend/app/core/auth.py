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


def _verify_firebase_token(token: str) -> Optional[str]:
    """Verify a Firebase ID token and return the uid on success, None on failure."""
    if not settings.FIREBASE_PROJECT_ID:
        logger.warning("FIREBASE_PROJECT_ID not set — cannot verify tokens")
        return None
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}",
        )
        uid = decoded.get("uid") or decoded.get("sub")
        return uid if uid else None
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


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Firebase uid from Bearer token. Returns None for unauthenticated requests."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return _verify_firebase_token(token)


def get_required_user(uid: Optional[str] = Depends(get_optional_user)) -> str:
    """Like get_optional_user but raises 401 if no valid token."""
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return uid


_status_cache: dict[str, tuple[str, float]] = {}
_STATUS_CACHE_TTL = 60.0


def invalidate_status_cache(uid: str) -> None:
    """Call when account_status changes (e.g. consent granted) so the user isn't
    blocked for up to a TTL by a stale cached status."""
    _status_cache.pop(uid, None)


def get_active_user(uid: str = Depends(get_required_user)) -> str:
    """Like get_required_user but raises 403 if the account is consent-pending
    or paused by the managing parent.

    Fails closed: if the status can't be determined (DB error, nothing cached),
    the request is rejected rather than letting a blocked child through.
    Status is cached for 60 s per uid to keep the hot path off the DB.
    """
    from app.core.database import get_db
    now = time.monotonic()
    cached = _status_cache.get(uid)
    if cached is not None and now - cached[1] < _STATUS_CACHE_TTL:
        status = cached[0]
    else:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
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
    return uid


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
