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


async def purge_login(uid: str) -> bool:
    """Delete the Firebase login behind a users.uid, if it has one.

    Ordinary accounts: the users.uid is the Firebase uid. Family profiles
    ('prof_…') have no login unless the child claimed theirs, in which case
    auth_identities maps their Firebase uid to the profile. The mapping row is
    always removed so a later sign-in with that Google account starts fresh.
    """
    if not uid.startswith("prof_"):
        return await delete_firebase_user(uid)

    from app.core.auth import invalidate_identity_cache
    from app.core.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auth_identities WHERE uid = %s RETURNING firebase_uid", (uid,))
            row = cur.fetchone()
    if not row:
        return True  # unclaimed profile — there is no login to purge
    invalidate_identity_cache(row["firebase_uid"])
    return await delete_firebase_user(row["firebase_uid"])
