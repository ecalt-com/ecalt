"""Append-only consent audit log (parental accounts plan, Phase 0).

Every consent-related action is recorded in consent_events. The table has a
trigger making it append-only; on account deletion the uid is pseudonymized
(the one permitted UPDATE) so proof of consent survives erasure requests.
"""
import hashlib
import hmac
import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.jurisdiction import CONSENT_POLICY_VERSION

logger = logging.getLogger(__name__)

# Actions where a missing audit record would leave us without proof of a
# consent decision — these must fail loudly rather than be skipped.
_CRITICAL_ACTIONS = {"granted", "refused", "revoked", "reconsent", "verified", "reported"}


def hash_ip(ip: Optional[str]) -> Optional[str]:
    """Store a sha256 of the consenting party's IP, never the raw address."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()


def pseudonymize_uid(uid: str) -> str:
    """Stable replacement uid used when the account is deleted (GDPR Art. 17)."""
    return "deleted:" + hashlib.sha256(uid.encode()).hexdigest()[:40]


def make_consent_report_token(child_uid: str) -> str:
    """Signed token for the email-plus "this wasn't me" link — the token is the
    capability, so the reporting parent needs no account."""
    secret = (settings.NOTIFICATION_SIGNING_SECRET or "ecalt-unsub-secret").encode()
    return hmac.new(secret, f"consent-report:{child_uid}".encode(), hashlib.sha256).hexdigest()


def verify_consent_report_token(child_uid: str, token: str) -> bool:
    return hmac.compare_digest(make_consent_report_token(child_uid), token)


def schedule_email_plus_followup(child_uid: str, parent_uid: Optional[str],
                                 parent_email: str, child_name: Optional[str],
                                 cur, delay_hours: int = 24) -> None:
    """Queue the delayed follow-up notice (email-plus tier). Runs in the
    caller's transaction so consent and its follow-up commit together."""
    cur.execute(
        """
        INSERT INTO consent_followups (uid, parent_uid, parent_email, child_name, send_after)
        VALUES (%s, %s, %s, %s, now() + make_interval(hours => %s))
        """,
        (child_uid, parent_uid, parent_email, child_name, delay_hours),
    )


def record_consent_event(
    uid: str,
    action: str,
    *,
    parent_uid: Optional[str] = None,
    parent_email: Optional[str] = None,
    method: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    ip_hash: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    cur=None,
) -> None:
    """Append one row to consent_events.

    Pass `cur` to write inside the caller's transaction (preferred for
    consent-critical actions so the decision and its proof commit atomically).
    Non-critical actions swallow failures; critical ones re-raise.
    """
    sql = """
        INSERT INTO consent_events
            (uid, parent_uid, parent_email, action, method,
             policy_version, jurisdiction, ip_hash, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        uid, parent_uid, parent_email, action, method,
        CONSENT_POLICY_VERSION, jurisdiction, ip_hash,
        json.dumps(details) if details is not None else None,
    )
    try:
        if cur is not None:
            cur.execute(sql, params)
        else:
            with get_db() as conn:
                with conn.cursor() as c:
                    c.execute(sql, params)
    except Exception:
        if action in _CRITICAL_ACTIONS:
            raise
        logger.exception("failed to record consent event uid=%s action=%s", uid, action)
