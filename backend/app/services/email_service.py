"""Transactional email — Brevo HTTP API (preferred) with SMTP fallback."""
import hashlib
import hmac
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib
import httpx

from app.core.config import settings

logger = logging.getLogger("app.services.email_service")

_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
_SMTP_TIMEOUT = 10  # seconds — fail fast so the scheduler queue doesn't back up

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


async def _send_via_brevo_api(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    payload = {
        "sender": {"name": "ECALT", "email": settings.SMTP_FROM_EMAIL},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _BREVO_SEND_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json"},
        )
    if resp.status_code in (200, 201):
        logger.info("email sent to=%s via Brevo API", to)
        return True
    logger.error("Brevo API error to=%s status=%s body=%s", to, resp.status_code, resp.text[:200])
    return False


async def _send_via_smtp(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"ECALT <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_LOGIN,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
        timeout=_SMTP_TIMEOUT,
    )
    logger.info("email sent to=%s via SMTP host=%s", to, settings.SMTP_HOST)
    return True


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    uid: str,
    log_id: Optional[str] = None,
) -> bool:
    """Send a transactional email. Returns True on success."""
    unsub_token = make_unsubscribe_token(uid)
    footer = _FOOTER_TPL.format(frontend_url=settings.FRONTEND_URL, token=unsub_token)
    full_html = html_body + footer
    if log_id:
        full_html += _PIXEL_TPL.format(frontend_url=settings.FRONTEND_URL, log_id=log_id)

    try:
        if settings.BREVO_API_KEY:
            return await _send_via_brevo_api(to, subject, full_html, text_body)

        if settings.SMTP_HOST and settings.SMTP_LOGIN:
            return await _send_via_smtp(to, subject, full_html, text_body)

        logger.warning("no email transport configured — skipping email to %s", to)
        return False

    except Exception as e:
        logger.error("send_email failed to=%s: %s", to, e)
        return False


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
    Review &amp; Decide
  </a>
</p>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  The link opens a review page where you can approve or decline. Signing in with your
  own Google account there also gives you a Family dashboard to see what your child
  is learning and manage their account.
</p>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  This link expires in 7 days. If you did not expect this email, ignore it — no account will be activated.
</p>
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = (
        f"Hi,\n\nYour child has signed up for ECALT (ecalt.app).\n\n"
        f"To review the request and approve or decline, visit:\n{confirm_url}\n\n"
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


async def send_child_account_created_email(parent_email: str, child_name: str,
                                           child_login_email: str, parent_uid: str) -> bool:
    """COPPA direct-notice receipt after a parent creates a managed child account."""
    family_url = f"{settings.FRONTEND_URL}/family"
    subject = f"You created an ECALT account for {child_name}"
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">
  You just created an ECALT account for <strong>{child_name}</strong>
  (login: {child_login_email}). This email is your record of the consent you gave.
</p>
<h3 style="font-family:sans-serif">What ECALT collects for {child_name}:</h3>
<ul style="font-family:sans-serif">
  <li>The name and login email you provided</li>
  <li>Their learning questions and journeys</li>
  <li>AI-generated knowledge nodes (topics they've explored)</li>
</ul>
<h3 style="font-family:sans-serif">Your rights as a parent:</h3>
<ul style="font-family:sans-serif">
  <li>See what they're learning from your <a href="{family_url}">Family dashboard</a></li>
  <li>Export or delete their data at any time</li>
  <li>Withdraw consent at any time — this deactivates and deletes the account</li>
</ul>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  If you did not create this account, reply to this email or contact support@ecalt.com immediately.
</p>
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = (
        f"Hi,\n\nYou created an ECALT account for {child_name} (login: {child_login_email}).\n\n"
        f"Manage it any time from your Family dashboard: {family_url}\n"
        f"You can export or delete their data, or withdraw consent, at any time.\n\n"
        f"If you did not create this account, contact support@ecalt.com immediately.\n\n"
        f"Privacy Policy: {settings.FRONTEND_URL}/privacy"
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=parent_uid,
    )


async def send_email_plus_followup(parent_email: str, child_name: str,
                                   report_url: str, parent_uid: str) -> bool:
    """Delayed 'email-plus' verification notice: confirms the earlier approval
    and gives the real parent an objection path if it wasn't them."""
    subject = f"Confirming: you approved {child_name}'s ECALT account"
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">
  Yesterday this email address approved an ECALT account for <strong>{child_name}</strong>.
  If that was you, there's nothing to do — this is just a confirmation for your records.
</p>
<p style="font-family:sans-serif">
  <strong>If you did not approve this account</strong>, click below and we'll suspend
  it immediately:
</p>
<p style="font-family:sans-serif">
  <a href="{report_url}"
     style="display:inline-block;padding:12px 24px;background:#e11d48;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold;font-family:sans-serif">
    This wasn't me — suspend the account
  </a>
</p>
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = (
        f"Hi,\n\nYesterday this email address approved an ECALT account for {child_name}.\n"
        f"If that was you, there's nothing to do.\n\n"
        f"If you did NOT approve this account, suspend it here:\n{report_url}\n\n"
        f"Privacy Policy: {settings.FRONTEND_URL}/privacy"
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=parent_uid,
    )


async def send_family_notice_email(to: str, uid: str, subject: str,
                                   paragraphs: list[str],
                                   cta_url: str | None = None,
                                   cta_label: str | None = None) -> bool:
    """Generic single-purpose family/lifecycle notice (age-up, re-consent,
    retention, unlink). Paragraphs are plain text; first one follows 'Hi,'."""
    body_html = "".join(
        f'<p style="font-family:sans-serif">{p}</p>' for p in paragraphs
    )
    cta_html = ""
    if cta_url and cta_label:
        cta_html = f"""\
<p style="font-family:sans-serif">
  <a href="{cta_url}"
     style="display:inline-block;padding:12px 24px;background:#4f46e5;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold;font-family:sans-serif">
    {cta_label}
  </a>
</p>"""
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
{body_html}
{cta_html}
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = "Hi,\n\n" + "\n\n".join(paragraphs)
    if cta_url:
        text_body += f"\n\n{cta_label or 'Open'}: {cta_url}"
    text_body += f"\n\nPrivacy Policy: {settings.FRONTEND_URL}/privacy"
    return await send_email(
        to=to, subject=subject, html_body=html_body, text_body=text_body, uid=uid,
    )


async def send_revocation_scheduled_email(parent_email: str, child_name: str,
                                          grace_days: int, parent_uid: str) -> bool:
    """Receipt after a parent withdraws consent: paused now, deleted after grace."""
    family_url = f"{settings.FRONTEND_URL}/family"
    subject = f"Consent withdrawn — {child_name}'s account will be deleted in {grace_days} days"
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">
  You withdrew consent for <strong>{child_name}</strong>'s ECALT account. The account
  is paused immediately, and all of their data will be permanently deleted in
  <strong>{grace_days} days</strong>.
</p>
<p style="font-family:sans-serif">
  Changed your mind? You can undo this any time before then from your
  <a href="{family_url}">Family dashboard</a>. You can also download a copy of their
  data there before it's gone.
</p>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  If you didn't do this, contact support@ecalt.com immediately.
</p>"""
    text_body = (
        f"Hi,\n\nYou withdrew consent for {child_name}'s ECALT account.\n"
        f"It is paused now and will be permanently deleted in {grace_days} days.\n\n"
        f"Undo or download their data before then: {family_url}\n\n"
        f"If you didn't do this, contact support@ecalt.com immediately."
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=parent_uid,
    )


async def send_family_digest_email(parent_email: str, parent_uid: str,
                                   children: list[dict]) -> bool:
    """Weekly parent digest: one row per active child (Phase 3)."""
    family_url = f"{settings.FRONTEND_URL}/family"
    subject = "This week on ECALT: your family's learning"

    child_rows = ""
    text_rows = []
    for c in children:
        accuracy = ""
        if c.get("quiz_answers"):
            pct = round(100 * (c.get("quiz_correct") or 0) / c["quiz_answers"])
            accuracy = f" · {pct}% quiz accuracy ({c['quiz_answers']} answered)"
        top = f" · exploring {c['top_domain']}" if c.get("top_domain") else ""
        child_rows += f"""\
<tr>
  <td style="font-family:sans-serif;padding:12px 16px;border-bottom:1px solid #eee">
    <strong>{c['name']}</strong><br>
    <span style="color:#555;font-size:14px">
      {c.get('steps_completed', 0)} steps completed ·
      {c.get('journeys_started', 0)} new journeys ·
      {c.get('streak_days', 0)}-day streak{accuracy}{top}
    </span>
  </td>
</tr>"""
        text_rows.append(
            f"- {c['name']}: {c.get('steps_completed', 0)} steps, "
            f"{c.get('journeys_started', 0)} new journeys, "
            f"{c.get('streak_days', 0)}-day streak{accuracy}{top}"
        )

    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">Here's what your family explored on ECALT this week:</p>
<table style="border-collapse:collapse;width:100%">{child_rows}</table>
<p style="font-family:sans-serif;margin-top:16px">
  <a href="{family_url}"
     style="display:inline-block;padding:10px 20px;background:#4f46e5;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold;font-family:sans-serif">
    Open Family Dashboard
  </a>
</p>"""
    text_body = (
        "Hi,\n\nHere's what your family explored on ECALT this week:\n\n"
        + "\n".join(text_rows)
        + f"\n\nFamily dashboard: {family_url}"
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=parent_uid,
    )


async def send_link_approved_email(parent_email: str, child_name: str, parent_uid: str) -> bool:
    """Receipt after a parent approves a child-initiated consent request."""
    family_url = f"{settings.FRONTEND_URL}/family"
    subject = f"You approved {child_name}'s ECALT account"
    html_body = f"""\
<p style="font-family:sans-serif;font-size:16px">Hi,</p>
<p style="font-family:sans-serif">
  You approved <strong>{child_name}</strong>'s ECALT account, and it is now linked to
  your family. From your <a href="{family_url}">Family dashboard</a> you can see what
  they're learning, export or delete their data, and withdraw consent at any time.
</p>
<p style="font-family:sans-serif;color:#666;font-size:14px">
  If this wasn't you, reply to this email or contact support@ecalt.com immediately and
  we'll deactivate the account.
</p>
<p style="font-family:sans-serif;font-size:12px;color:#999">
  ECALT Privacy Policy: {settings.FRONTEND_URL}/privacy
</p>"""
    text_body = (
        f"Hi,\n\nYou approved {child_name}'s ECALT account.\n\n"
        f"Manage it from your Family dashboard: {family_url}\n\n"
        f"If this wasn't you, contact support@ecalt.com immediately.\n\n"
        f"Privacy Policy: {settings.FRONTEND_URL}/privacy"
    )
    return await send_email(
        to=parent_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        uid=parent_uid,
    )
