"""Ops alerting: email every admin when an AI provider account runs out of credits.

Triggered from provider_service when a model call fails with a quota/billing
error (e.g. OpenAI `insufficient_quota` / `credit_balance_exhausted`). Keeps a
per-provider in-memory cooldown so a storm of failing requests produces one
email, not hundreds. In-memory is deliberate: each environment runs a single
backend instance, and the worst case after a restart is one extra email.
"""
import logging
import time

from app.core.database import get_db
from app.services.email_service import send_ai_credits_exhausted_email

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = 6 * 3600

# Substrings that identify "the account is out of money", as opposed to a
# transient per-minute rate limit which should never page anyone.
_CREDIT_MARKERS = (
    "insufficient_quota",            # OpenAI error type
    "credit_balance_exhausted",      # OpenAI error code
    "no credits remaining",          # OpenAI message
    "exceeded your current quota",   # OpenAI legacy message
    "billing_hard_limit_reached",    # OpenAI hard limit
    "credit balance is too low",     # Anthropic message
)

_last_alert_at: dict[str, float] = {}


def is_credit_exhaustion(error: Exception) -> bool:
    """True when the provider error means the account has no credits left."""
    text = str(error).lower()
    return any(marker in text for marker in _CREDIT_MARKERS)


def _get_admin_recipients() -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid, email FROM users WHERE is_admin = true AND email IS NOT NULL"
            )
            return [dict(r) for r in cur.fetchall()]


def reset_cooldown() -> None:
    """Test hook / manual reset."""
    _last_alert_at.clear()


async def alert_credits_exhausted(provider: str, error: Exception) -> None:
    """Email all admins that `provider` is out of credits. Never raises — the
    caller is already propagating the provider error to the user."""
    try:
        now = time.monotonic()
        last = _last_alert_at.get(provider)
        if last is not None and now - last < ALERT_COOLDOWN_SECONDS:
            return
        # Mark before sending so concurrent failing requests don't all email.
        _last_alert_at[provider] = now

        admins = _get_admin_recipients()
        if not admins:
            logger.error("%s credits exhausted but no admin has an email to alert", provider)
            return

        detail = str(error)[:500]
        sent = 0
        for admin in admins:
            ok = await send_ai_credits_exhausted_email(
                admin_email=admin["email"],
                admin_uid=admin["uid"],
                provider=provider,
                error_detail=detail,
            )
            if ok:
                sent += 1
        logger.warning(
            "%s credits exhausted — alerted %d/%d admins", provider, sent, len(admins)
        )
    except Exception:
        logger.exception("failed to send %s credit-exhaustion alert", provider)
