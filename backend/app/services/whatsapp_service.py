"""Twilio WhatsApp messaging service.

Hard constraint: callers must verify whatsapp_opted_in = TRUE before calling send_whatsapp.
This guard is also enforced in NotificationService.send_notification.
"""
import logging

from app.core.config import settings

logger = logging.getLogger("app.services.whatsapp_service")

_OPT_IN_MESSAGE = (
    "Hi! Reply YES to start receiving personalised learning nudges from ECALT on WhatsApp. "
    "Reply STOP at any time to unsubscribe."
)


def _get_client():
    from twilio.rest import Client
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def send_whatsapp(to_e164: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not set — skipping WhatsApp to %s", to_e164)
        return False
    try:
        client = _get_client()
        msg = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            body=message,
            to=f"whatsapp:{to_e164}",
        )
        logger.info("whatsapp sent sid=%s to=%s", msg.sid, to_e164)
        return True
    except Exception as e:
        logger.error("send_whatsapp failed to=%s: %s", to_e164, e)
        return False


async def send_opt_in_prompt(to_e164: str) -> bool:
    """Send the consent prompt. Called by the opt-in endpoint in production."""
    return await send_whatsapp(to_e164=to_e164, message=_OPT_IN_MESSAGE)
