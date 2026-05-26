"""SendGrid transactional email service."""
import hashlib
import hmac
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("app.services.email_service")

_FOOTER_TPL = """\
<br><br>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="color:#999;font-size:12px;text-align:center;font-family:sans-serif">
  You're receiving this because you signed up to ECALT.<br>
  <a href="{frontend_url}/api/v1/notifications/unsubscribe?token={token}"
     style="color:#999;text-decoration:underline">Unsubscribe</a>
</p>"""

_PIXEL_TPL = (
    '<img src="{frontend_url}/api/v1/notifications/open?log_id={log_id}" '
    'width="1" height="1" style="display:none" alt="">'
)


def make_unsubscribe_token(uid: str) -> str:
    """HMAC-SHA256 signed token so the unsubscribe endpoint needs no auth."""
    secret = (settings.NOTIFICATION_SIGNING_SECRET or "ecalt-unsub-secret").encode()
    return hmac.new(secret, uid.encode(), hashlib.sha256).hexdigest()


def verify_unsubscribe_token(uid: str, token: str) -> bool:
    return hmac.compare_digest(make_unsubscribe_token(uid), token)


async def send_parental_consent_email(parent_email: str, uid: str, token: str) -> bool:
    """Send COPPA parental consent confirmation email."""
    confirm_url = f"{settings.FRONTEND_URL}/consent/confirm?token={token}"
    subject = "Action Required: Confirm your child's ECALT account"
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">
  Your child has signed up for <strong>ECALT</strong>, an AI-powered learning platform.
  ECALT requires parental consent for learners aged 13–17 under COPPA.
</p>
<h3 style="font-family:sans-serif">What ECALT collects for your child:</h3>
<ul style="font-family:sans-serif">
  <li>Their first name and email address (from Google sign-in)</li>
  <li>Their learning questions and journeys</li>
  <li>AI-generated knowledge nodes (topics they've explored)</li>
</ul>
<h3 style="font-family:sans-serif">ECALT does <em>not</em>:</h3>
<ul style="font-family:sans-serif">
  <li>Sell your child's data</li>
  <li>Share data with third parties for advertising</li>
  <li>Collect any data if you do not confirm</li>
</ul>
<p style="font-family:sans-serif">
  <a href="{confirm_url}"
     style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold;font-family:sans-serif">
    Confirm My Child's Account
  </a>
</p>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  This link expires in 7 days. If you did not expect this email, ignore it — no account will be activated.
</p>
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = (
        f"Hi,\n\nYour child has signed up for ECALT (ecalt.app).\n\n"
        f"To confirm their account, visit:\n{confirm_url}\n\n"
        f"This link expires in 7 days. If you did not expect this, ignore it.\n\n"
        f"Privacy Policy: {settings.FRONTEND_URL}/privacy"
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=uid,
    )


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    uid: str,
    log_id: Optional[str] = None,
) -> bool:
    """Send a transactional email via SendGrid. Returns True on success."""
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not configured — skipping email to %s", to)
        return False

    try:
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail

        unsub_token = make_unsubscribe_token(uid)
        footer = _FOOTER_TPL.format(frontend_url=settings.FRONTEND_URL, token=unsub_token)
        full_html = html_body + footer
        if log_id:
            full_html += _PIXEL_TPL.format(frontend_url=settings.FRONTEND_URL, log_id=log_id)

        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=to,
            subject=subject,
            html_content=full_html,
            plain_text_content=text_body,
        )

        client = sg_module.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        resp = client.send(message)
        if resp.status_code in (200, 201, 202):
            logger.info("email sent to=%s status=%s", to, resp.status_code)
            return True
        logger.error("SendGrid error status=%s to=%s", resp.status_code, to)
        return False
    except Exception as e:
        logger.error("send_email failed to=%s: %s", to, e)
        return False
