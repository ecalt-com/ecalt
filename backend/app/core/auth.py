import logging
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException, Depends

from app.core.config import settings

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
