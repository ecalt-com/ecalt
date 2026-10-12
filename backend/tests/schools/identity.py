"""Test identities (TESTING.md §3 "Identity in tests").

`Authorization: Bearer test:<uid>[:<auth_time>]` resolves to <uid> by patching
core.auth._decode_firebase_token, so every real dependency still runs: identity
mapping, the student allowlist, status checks and school membership. Prefer
this to app.dependency_overrides, which skips exactly the layers under test.
"""
import time
from typing import Optional

_EXTRA_CLAIMS: dict[str, dict] = {}


def register(uid: str, **claims) -> None:
    """Extra token claims for uid (e.g. email, email_verified)."""
    _EXTRA_CLAIMS[uid] = claims


def reset() -> None:
    _EXTRA_CLAIMS.clear()


def fake_decode(token: str) -> Optional[dict]:
    if not token.startswith("test:"):
        return None
    parts = token.split(":")
    uid = parts[1]
    auth_time = int(parts[2]) if len(parts) > 2 and parts[2] else int(time.time())
    return {"uid": uid, "sub": uid, "user_id": uid, "auth_time": auth_time, **_EXTRA_CLAIMS.get(uid, {})}


def bearer(uid: Optional[str], auth_time: Optional[int] = None, **headers: str) -> dict:
    """Request headers for uid (None → anonymous). Extra headers are passed
    through with underscores turned into dashes (x_profile_id → X-Profile-Id)."""
    out = {k.replace("_", "-").title(): v for k, v in headers.items()}
    if uid:
        out["Authorization"] = f"Bearer test:{uid}" + (f":{auth_time}" if auth_time else "")
    return out
