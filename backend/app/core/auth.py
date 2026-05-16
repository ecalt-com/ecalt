from fastapi import Header, HTTPException, Depends
from typing import Optional
import firebase_admin
from firebase_admin import auth as firebase_auth


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Firebase uid from Bearer token. Returns None for unauthenticated requests."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        return None


def get_required_user(uid: Optional[str] = Depends(get_optional_user)) -> str:
    """Like get_optional_user but raises 401 if no valid token."""
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return uid
