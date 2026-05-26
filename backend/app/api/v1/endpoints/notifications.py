"""Notification preferences, WhatsApp opt-in, manual trigger, and unsubscribe endpoints.

Phases covered: 2 (trigger), 3 (WhatsApp opt-in wired to Twilio), 5 (preferences + unsubscribe).
"""
import re
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.core.auth import get_required_user, get_admin_user
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger("app.api.v1.endpoints.notifications")

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def _normalize_phone(raw: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", raw or "")
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned.lstrip("0")
    if not _E164_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number — use E.164 format (e.g. +919876543210)",
        )
    return cleaned


# ── Pydantic models ───────────────────────────────────────────────────────────

class NotificationPreferences(BaseModel):
    email_enabled: bool = True
    whatsapp_enabled: bool = False
    whatsapp_opted_in: bool = False
    whatsapp_phone: Optional[str] = None
    whatsapp_declined_onboarding: bool = False
    whatsapp_nudge_last_dismissed: Optional[str] = None
    quiet_hours_start: int = 22
    quiet_hours_end: int = 7
    timezone: str = "UTC"
    preferred_channel: str = "email"


class PreferencesPatch(BaseModel):
    email_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_phone: Optional[str] = None
    whatsapp_declined_onboarding: Optional[bool] = None
    whatsapp_nudge_dismissed: Optional[bool] = None
    quiet_hours_start: Optional[int] = Field(default=None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(default=None, ge=0, le=23)
    timezone: Optional[str] = None
    preferred_channel: Optional[str] = None


class WhatsAppOptInRequest(BaseModel):
    phone: str


class WhatsAppConfirmRequest(BaseModel):
    phone: str


class TriggerRequest(BaseModel):
    uid: str
    notification_type: str
    channel: str = "email"
    context: dict = {}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _row_to_prefs(row) -> NotificationPreferences:
    if not row:
        return NotificationPreferences()
    d = dict(row)
    ts = d.get("whatsapp_nudge_last_dismissed")
    return NotificationPreferences(
        email_enabled=d.get("email_enabled", True),
        whatsapp_enabled=d.get("whatsapp_enabled", False),
        whatsapp_opted_in=d.get("whatsapp_opted_in", False),
        whatsapp_phone=d.get("whatsapp_phone"),
        whatsapp_declined_onboarding=d.get("whatsapp_declined_onboarding", False),
        whatsapp_nudge_last_dismissed=ts.isoformat() if ts else None,
        quiet_hours_start=d.get("quiet_hours_start", 22),
        quiet_hours_end=d.get("quiet_hours_end", 7),
        timezone=d.get("timezone") or "UTC",
        preferred_channel=d.get("preferred_channel") or "email",
    )


def _ensure_row(cur, uid: str) -> None:
    cur.execute(
        "INSERT INTO notification_preferences (uid) VALUES (%s) ON CONFLICT (uid) DO NOTHING",
        (uid,),
    )


# ── Preferences endpoints ─────────────────────────────────────────────────────

@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM notification_preferences WHERE uid = %s", (uid,))
            row = cur.fetchone()
    return _row_to_prefs(row)


@router.patch("/preferences", response_model=NotificationPreferences)
def patch_preferences(body: PreferencesPatch, uid: str = Depends(get_required_user)):
    updates: dict = {}
    if body.email_enabled is not None:
        updates["email_enabled"] = body.email_enabled
    if body.whatsapp_enabled is not None:
        updates["whatsapp_enabled"] = body.whatsapp_enabled
    if body.whatsapp_phone is not None:
        updates["whatsapp_phone"] = _normalize_phone(body.whatsapp_phone) if body.whatsapp_phone else None
    if body.whatsapp_declined_onboarding is not None:
        updates["whatsapp_declined_onboarding"] = body.whatsapp_declined_onboarding
    if body.quiet_hours_start is not None:
        updates["quiet_hours_start"] = body.quiet_hours_start
    if body.quiet_hours_end is not None:
        updates["quiet_hours_end"] = body.quiet_hours_end
    if body.timezone is not None:
        updates["timezone"] = body.timezone
    if body.preferred_channel is not None:
        if body.preferred_channel not in ("email", "whatsapp"):
            raise HTTPException(status_code=400, detail="preferred_channel must be 'email' or 'whatsapp'")
        updates["preferred_channel"] = body.preferred_channel

    set_parts = [f"{k} = %s" for k in updates]
    params = list(updates.values())
    if body.whatsapp_nudge_dismissed:
        set_parts.append("whatsapp_nudge_last_dismissed = now()")
    set_parts.append("updated_at = now()")

    with get_db() as conn:
        with conn.cursor() as cur:
            _ensure_row(cur, uid)
            if updates or body.whatsapp_nudge_dismissed:
                cur.execute(
                    f"UPDATE notification_preferences SET {', '.join(set_parts)} WHERE uid = %s RETURNING *",
                    (*params, uid),
                )
                row = cur.fetchone()
            else:
                cur.execute("SELECT * FROM notification_preferences WHERE uid = %s", (uid,))
                row = cur.fetchone()
    return _row_to_prefs(row)


@router.delete("/preferences/email", response_model=NotificationPreferences)
def unsubscribe_email(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            _ensure_row(cur, uid)
            cur.execute(
                "UPDATE notification_preferences SET email_enabled = FALSE, updated_at = now() WHERE uid = %s RETURNING *",
                (uid,),
            )
            row = cur.fetchone()
    return _row_to_prefs(row)


@router.delete("/preferences/whatsapp", response_model=NotificationPreferences)
def opt_out_whatsapp(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            _ensure_row(cur, uid)
            cur.execute(
                """
                UPDATE notification_preferences
                   SET whatsapp_opted_in = FALSE, whatsapp_enabled = FALSE,
                       whatsapp_phone = NULL, updated_at = now()
                 WHERE uid = %s RETURNING *
                """,
                (uid,),
            )
            row = cur.fetchone()
    return _row_to_prefs(row)


# ── WhatsApp opt-in ───────────────────────────────────────────────────────────

@router.post("/whatsapp/opt-in", response_model=NotificationPreferences)
async def whatsapp_opt_in(body: WhatsAppOptInRequest, uid: str = Depends(get_required_user)):
    """Store phone number and begin the opt-in flow.

    Production: sends a Twilio WhatsApp consent prompt and leaves whatsapp_opted_in=FALSE
    until the user replies YES (handled via Twilio inbound webhook or /whatsapp/confirm).
    Development (ENVIRONMENT != 'production'): auto-confirms immediately.
    """
    phone = _normalize_phone(body.phone)
    dev_mode = settings.ENVIRONMENT != "production"

    with get_db() as conn:
        with conn.cursor() as cur:
            _ensure_row(cur, uid)
            cur.execute(
                """
                UPDATE notification_preferences
                   SET whatsapp_phone              = %s,
                       whatsapp_opted_in           = %s,
                       whatsapp_enabled            = %s,
                       whatsapp_declined_onboarding = FALSE,
                       updated_at                  = now()
                 WHERE uid = %s RETURNING *
                """,
                (phone, dev_mode, dev_mode, uid),
            )
            row = cur.fetchone()

    if not dev_mode:
        from app.services.whatsapp_service import send_opt_in_prompt
        try:
            await send_opt_in_prompt(phone)
            logger.info("whatsapp opt-in prompt sent uid=%s phone=%s", uid, phone)
        except Exception as e:
            logger.error("whatsapp opt-in prompt failed uid=%s: %s", uid, e)
    else:
        logger.info("whatsapp opt-in auto-confirmed (dev) uid=%s phone=%s", uid, phone)

    return _row_to_prefs(row)


@router.post("/whatsapp/confirm", response_model=NotificationPreferences)
def whatsapp_confirm(body: WhatsAppConfirmRequest, uid: str = Depends(get_required_user)):
    """Confirm WhatsApp opt-in. In production this is triggered by a Twilio inbound webhook
    that matches the user's stored phone number after they reply YES."""
    phone = _normalize_phone(body.phone)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notification_preferences
                   SET whatsapp_opted_in = TRUE, whatsapp_enabled = TRUE, updated_at = now()
                 WHERE uid = %s AND whatsapp_phone = %s RETURNING *
                """,
                (uid, phone),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No pending opt-in for that phone number")
    return _row_to_prefs(row)


# ── Admin trigger (Phase 2) ───────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_notification(body: TriggerRequest, _admin: str = Depends(get_admin_user)):
    """Admin-only: manually fire a notification for a specific user. Used for testing."""
    from app.services.notification_service import notification_service

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM users WHERE uid = %s", (body.uid,))
            user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = await notification_service.send_notification(
        uid=body.uid,
        email=user["email"],
        notification_type=body.notification_type,
        channel=body.channel,
        context=body.context,
    )
    return {"sent": success, "uid": body.uid, "type": body.notification_type, "channel": body.channel}


# ── One-click unsubscribe (Phase 5) ──────────────────────────────────────────

@router.get("/unsubscribe", include_in_schema=False)
def one_click_unsubscribe(uid: str = Query(...), token: str = Query(...)):
    """GDPR one-click unsubscribe. No auth required — validated by signed token."""
    from app.services.email_service import verify_unsubscribe_token

    if not verify_unsubscribe_token(uid, token):
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")

    with get_db() as conn:
        with conn.cursor() as cur:
            _ensure_row(cur, uid)
            cur.execute(
                "UPDATE notification_preferences SET email_enabled = FALSE, updated_at = now() WHERE uid = %s",
                (uid,),
            )

    logger.info("one-click unsubscribe uid=%s", uid)
    return HTMLResponse(
        content="<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
                "<h2>You've been unsubscribed</h2>"
                "<p>You will no longer receive email notifications from ECALT.</p>"
                "</body></html>"
    )


# ── Open tracking pixel (Phase 2) ────────────────────────────────────────────

_TRANSPARENT_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


@router.get("/open", include_in_schema=False)
def track_open(log_id: str = Query(...)):
    """Tracking pixel endpoint — sets opened_at on the notification_log row."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE notification_log SET opened_at = now() WHERE id = %s AND opened_at IS NULL",
                    (log_id,),
                )
    except Exception as e:
        logger.debug("track_open failed log_id=%s: %s", log_id, e)
    return Response(content=_TRANSPARENT_GIF, media_type="image/gif")
