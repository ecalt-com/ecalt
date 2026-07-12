"""Minimal Firebase Auth admin operations via the Identity Toolkit REST API.

COPPA gap fix (plan G4): Google sign-in creates the Firebase Auth record
(name, email, photo) *before* the age gate runs, so an under-13 rejection must
purge that record — otherwise we retain a child's PII.

Uses the service-account JSON in FIREBASE_SERVICE_ACCOUNT_JSON to mint an
OAuth2 access token with PyJWT + httpx (both already dependencies), avoiding
the firebase-admin package. Fails gracefully (log + False) when unconfigured.
"""
import json
import logging
import time
from typing import Optional

import httpx
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/identitytoolkit"
_token_cache: dict = {}  # {"token": str, "exp": epoch seconds}


async def _get_access_token() -> Optional[str]:
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("exp", 0) - 60 > now:
        return _token_cache["token"]

    raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if not raw:
        return None
    sa = json.loads(raw)
    assertion = jwt.encode(
        {
            "iss": sa["client_email"],
            "scope": _SCOPE,
            "aud": sa["token_uri"],
            "iat": int(now),
            "exp": int(now) + 3600,
        },
        sa["private_key"],
        algorithm="RS256",
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            sa["token_uri"],
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        r.raise_for_status()
        data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["exp"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


async def create_firebase_user(email: str, password: str, display_name: str) -> tuple[Optional[str], Optional[str]]:
    """Create an email/password Firebase Auth user (managed child credential).

    Returns (uid, None) on success, (None, error_code) on failure — error_code is
    "not_configured", a Firebase error like "EMAIL_EXISTS", or an HTTP/exception tag.
    The password is passed straight through to Firebase and never stored.
    """
    try:
        token = await _get_access_token()
        if not token:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON not set — cannot create Firebase user")
            return None, "not_configured"
        body = {"email": email, "password": password, "displayName": display_name, "emailVerified": False}
        if settings.FIREBASE_PROJECT_ID:
            body["targetProjectId"] = settings.FIREBASE_PROJECT_ID
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://identitytoolkit.googleapis.com/v1/accounts:signUp",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        if r.status_code == 200:
            uid = r.json().get("localId")
            if uid:
                logger.info("created Firebase auth user %s (managed child)", uid)
                return uid, None
            return None, "no_local_id"
        try:
            code = r.json().get("error", {}).get("message") or f"http_{r.status_code}"
        except Exception:
            code = f"http_{r.status_code}"
        logger.warning("Firebase user create failed status=%s code=%s", r.status_code, code)
        return None, code
    except Exception as e:
        logger.warning("Firebase user create errored: %s", e)
        return None, type(e).__name__


async def delete_firebase_user(uid: str) -> bool:
    """Delete a Firebase Auth user. Returns True on success, False otherwise."""
    try:
        token = await _get_access_token()
        if not token:
            logger.warning(
                "FIREBASE_SERVICE_ACCOUNT_JSON not set — cannot delete Firebase user %s "
                "(under-13 PII remains in Firebase Auth)", uid,
            )
            return False
        body = {"localId": uid}
        if settings.FIREBASE_PROJECT_ID:
            body["targetProjectId"] = settings.FIREBASE_PROJECT_ID
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://identitytoolkit.googleapis.com/v1/accounts:delete",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        if r.status_code == 200:
            logger.info("deleted Firebase auth user %s (age-gate rejection)", uid)
            return True
        logger.warning(
            "Firebase user delete failed uid=%s status=%s body=%s",
            uid, r.status_code, r.text[:200],
        )
        return False
    except Exception as e:
        logger.warning("Firebase user delete errored uid=%s: %s", uid, e)
        return False
