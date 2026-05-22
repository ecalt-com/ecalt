"""Base notification service — routing, daily cap, quiet hours, logging, scheduling."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.database import get_db

logger = logging.getLogger("app.services.notification_service")

DAILY_CAP = 2


class NotificationService:

    # ── Counters ──────────────────────────────────────────────────────────────

    async def get_today_count(self, uid: str) -> int:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) AS cnt FROM notification_log WHERE uid = %s AND sent_at >= CURRENT_DATE::timestamptz",
                        (uid,),
                    )
                    row = cur.fetchone()
                    return int(row["cnt"]) if row else 0
        except Exception:
            return 0

    async def get_week_count(self, uid: str) -> int:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) AS cnt FROM notification_log WHERE uid = %s AND sent_at >= now() - interval '7 days'",
                        (uid,),
                    )
                    row = cur.fetchone()
                    return int(row["cnt"]) if row else 0
        except Exception:
            return 0

    async def get_open_rate(self, uid: str, last_n: int = 3) -> int:
        """Count how many of the last N sent notifications were opened."""
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS cnt FROM (
                            SELECT opened_at FROM notification_log
                            WHERE uid = %s ORDER BY sent_at DESC LIMIT %s
                        ) sub WHERE opened_at IS NOT NULL
                        """,
                        (uid, last_n),
                    )
                    row = cur.fetchone()
                    return int(row["cnt"]) if row else 0
        except Exception:
            return 0

    # ── Anti-annoyance gates ──────────────────────────────────────────────────

    async def can_send(self, uid: str) -> bool:
        today_count = await self.get_today_count(uid)
        if today_count >= DAILY_CAP:
            return False

        last_3_opens = await self.get_open_rate(uid, last_n=3)
        # 0/3 opened and already sent one today → cap at 1/day
        if last_3_opens == 0 and today_count >= 1:
            return False

        last_5_opens = await self.get_open_rate(uid, last_n=5)
        if last_5_opens == 0:
            # quiet mode: max 2 per week
            week_count = await self.get_week_count(uid)
            if week_count >= 2:
                return False

        return True

    async def is_quiet_hours(self, uid: str) -> bool:
        """True if the user's local hour is within their quiet window."""
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT quiet_hours_start, quiet_hours_end, timezone FROM notification_preferences WHERE uid = %s",
                        (uid,),
                    )
                    row = cur.fetchone()
            if not row:
                return False
            import zoneinfo
            try:
                tz = zoneinfo.ZoneInfo(row["timezone"] or "UTC")
            except Exception:
                tz = timezone.utc
            hour = datetime.now(tz).hour
            start, end = row["quiet_hours_start"], row["quiet_hours_end"]
            if start > end:          # window crosses midnight e.g. 22–07
                return hour >= start or hour < end
            return start <= hour < end
        except Exception:
            return False

    # ── Persistence helpers ───────────────────────────────────────────────────

    async def schedule_for_later(
        self,
        uid: str,
        notification_type: str,
        channel: str,
        payload: dict,
        when: datetime,
    ) -> None:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for, payload)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (uid, notification_type, channel, when, json.dumps(payload)),
                    )
        except Exception as e:
            logger.error("schedule_for_later failed uid=%s: %s", uid, e)

    async def log_notification(
        self,
        uid: str,
        notification_type: str,
        channel: str,
        subject: Optional[str],
        preview: Optional[str],
    ) -> Optional[str]:
        """Insert into notification_log and return the new UUID (for tracking pixels)."""
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO notification_log (uid, notification_type, channel, subject, message_preview)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                        """,
                        (uid, notification_type, channel, subject, (preview or "")[:100]),
                    )
                    row = cur.fetchone()
                    return str(row["id"]) if row else None
        except Exception as e:
            logger.error("log_notification failed uid=%s: %s", uid, e)
            return None

    async def get_engagement_stats(self, uid: str) -> dict:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS total_sent, COUNT(opened_at) AS total_opened
                        FROM notification_log
                        WHERE uid = %s AND sent_at >= now() - interval '30 days'
                        """,
                        (uid,),
                    )
                    row = cur.fetchone()
            if not row or row["total_sent"] == 0:
                return {"total_sent": 0, "total_opened": 0, "open_rate": 0.0}
            return {
                "total_sent": int(row["total_sent"]),
                "total_opened": int(row["total_opened"]),
                "open_rate": round(int(row["total_opened"]) / int(row["total_sent"]), 2),
            }
        except Exception:
            return {"total_sent": 0, "total_opened": 0, "open_rate": 0.0}

    # ── Main dispatch ─────────────────────────────────────────────────────────

    async def send_notification(
        self,
        uid: str,
        email: str,
        notification_type: str,
        channel: str,
        context: dict,
    ) -> bool:
        from app.core.config import settings
        from app.services.copy_generator import generate_copy
        from app.services.email_service import send_email
        from app.services.whatsapp_service import send_whatsapp

        # Global channel kill-switches (override per-user prefs)
        if channel == "email" and not settings.NOTIFICATIONS_EMAIL_ENABLED:
            logger.info("email channel disabled globally — skipping uid=%s type=%s", uid, notification_type)
            return False
        if channel == "whatsapp" and not settings.NOTIFICATIONS_WHATSAPP_ENABLED:
            logger.info("whatsapp channel disabled globally — skipping uid=%s type=%s", uid, notification_type)
            return False

        # Inject user's display_name into context if not already present
        if "name" not in context and "display_name" not in context:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT display_name FROM users WHERE uid = %s", (uid,))
                        row = cur.fetchone()
                        if row:
                            context = {**context, "name": row["display_name"] or ""}
            except Exception:
                pass

        if not await self.can_send(uid):
            logger.info("send blocked by daily cap / quiet-mode uid=%s type=%s", uid, notification_type)
            return False

        if await self.is_quiet_hours(uid):
            await self.schedule_for_later(
                uid, notification_type, channel, context,
                when=datetime.now(timezone.utc) + timedelta(hours=2),
            )
            logger.info("send deferred (quiet hours) uid=%s type=%s", uid, notification_type)
            return False

        copy = await generate_copy(notification_type, context)
        log_id = await self.log_notification(
            uid, notification_type, channel,
            copy.get("subject"), copy.get("short_message"),
        )
        success = False

        if channel == "email":
            success = await send_email(
                to=email,
                subject=copy["subject"],
                html_body=copy["body_html"],
                text_body=copy["short_message"],
                uid=uid,
                log_id=log_id,
            )

        elif channel == "whatsapp":
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT whatsapp_phone, whatsapp_opted_in FROM notification_preferences WHERE uid = %s",
                            (uid,),
                        )
                        pref = cur.fetchone()
            except Exception:
                pref = None

            if not pref or not pref["whatsapp_opted_in"] or not pref["whatsapp_phone"]:
                logger.warning("whatsapp send blocked: not opted in uid=%s", uid)
                return False

            success = await send_whatsapp(
                to_e164=pref["whatsapp_phone"],
                message=copy["short_message"],
            )

        if not success and log_id:
            # Clean up the log row so the failed attempt doesn't count against the cap
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM notification_log WHERE id = %s", (log_id,))
            except Exception:
                pass

        return success


notification_service = NotificationService()
