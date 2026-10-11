"""Family profiles (plans/family-profiles): parent PIN + parent-unlock tokens.

A child profile is a users row with no login (profile_type='profile'); the
parent's own Firebase session acts on it via the X-Profile-Id header (resolved
in core/auth.py). The parent PIN keeps a child on a shared device from leaving
their profile: verifying it mints a short-lived, HMAC-signed unlock token that
the client sends as X-Parent-Unlock on parent-only requests.
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.core.database import get_db

UNLOCK_TTL_SECONDS = 15 * 60
MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


# ── PIN hashing ──────────────────────────────────────────────────────────────

def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_pin(pin: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex),
                            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return hmac.compare_digest(digest.hex(), digest_hex)


def is_valid_pin_format(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6


# ── Unlock tokens ────────────────────────────────────────────────────────────

def _unlock_secret() -> bytes:
    # Domain-separated from the notification signing key so neither token
    # type can be replayed as the other.
    base = settings.NOTIFICATION_SIGNING_SECRET or "ecalt-unsub-secret"
    return hashlib.sha256(f"parent-unlock:{base}".encode()).digest()


def make_unlock_token(uid: str, now: Optional[float] = None) -> str:
    exp = int((now or time.time()) + UNLOCK_TTL_SECONDS)
    payload = f"{uid}|{exp}"
    sig = hmac.new(_unlock_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode().rstrip("=")


def verify_unlock_token(token: Optional[str], uid: str, now: Optional[float] = None) -> bool:
    if not token:
        return False
    try:
        padded = token + "=" * (-len(token) % 4)
        tok_uid, exp_s, sig = base64.urlsafe_b64decode(padded.encode()).decode().rsplit("|", 2)
        exp = int(exp_s)
    except Exception:
        return False
    expected = hmac.new(_unlock_secret(), f"{tok_uid}|{exp}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    return tok_uid == uid and exp > (now or time.time())


# ── PIN storage ──────────────────────────────────────────────────────────────

def has_pin(uid: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM parent_pins WHERE uid = %s", (uid,))
            return cur.fetchone() is not None


def set_pin(uid: str, pin: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parent_pins (uid, pin_hash) VALUES (%s, %s)
                ON CONFLICT (uid) DO UPDATE
                    SET pin_hash = EXCLUDED.pin_hash, failed_attempts = 0,
                        locked_until = NULL, updated_at = now()
                """,
                (uid, hash_pin(pin)),
            )


def verify_pin(uid: str, pin: str) -> tuple[str, Optional[dict]]:
    """Check a PIN with lockout. Returns (result, info) where result is one of
    'ok' | 'no_pin' | 'locked' | 'invalid'; info carries attempts_left or
    locked_until for the client."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pin_hash, failed_attempts, locked_until FROM parent_pins "
                "WHERE uid = %s FOR UPDATE",
                (uid,),
            )
            row = cur.fetchone()
            if not row:
                return "no_pin", None
            now = datetime.now(timezone.utc)
            locked_until = row.get("locked_until")
            if locked_until and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until and locked_until > now:
                return "locked", {"locked_until": locked_until.isoformat()}

            if check_pin(pin, row["pin_hash"]):
                cur.execute(
                    "UPDATE parent_pins SET failed_attempts = 0, locked_until = NULL WHERE uid = %s",
                    (uid,),
                )
                return "ok", None

            # A lapsed lock starts a fresh window of attempts.
            attempts = (0 if locked_until else row.get("failed_attempts") or 0) + 1
            if attempts >= MAX_PIN_ATTEMPTS:
                until = now + timedelta(minutes=PIN_LOCK_MINUTES)
                cur.execute(
                    "UPDATE parent_pins SET failed_attempts = 0, locked_until = %s WHERE uid = %s",
                    (until, uid),
                )
                return "locked", {"locked_until": until.isoformat()}
            cur.execute(
                "UPDATE parent_pins SET failed_attempts = %s, locked_until = NULL WHERE uid = %s",
                (attempts, uid),
            )
            return "invalid", {"attempts_left": MAX_PIN_ATTEMPTS - attempts}


# ── Profiles ─────────────────────────────────────────────────────────────────

def new_profile_uid() -> str:
    return "prof_" + secrets.token_hex(12)


def is_profile_uid(uid: Optional[str]) -> bool:
    return bool(uid) and uid.startswith("prof_")


def new_claim_code() -> str:
    # 8 chars from an unambiguous alphabet — short enough to read aloud.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))
