"""APScheduler async jobs for notification dispatch.

Jobs registered:
  every 15 min  — queue_processor       (drain notification_queue)
  every 15 min  — daily_spark_dispatch  (08:00 user local time window)
  daily 09:00   — re_engagement_ladder  (tiered: 3→7→14→30 day inactive)
  daily 09:00   — streak_lost_check     (streak broke yesterday)
  daily 20:00   — streak_risk_check     (streak at risk tonight)
  daily 10:00   — streak_milestone_check
  daily 10:00   — mind_signature_nudge
  every 6h      — journey_completion_nudge
  Sunday 18:00  — weekly_digest_dispatch
"""
import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("app.services.scheduler")

scheduler = AsyncIOScheduler(timezone="UTC")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _not_sent_recently(notif_type: str, days: int) -> str:
    """SQL fragment: user has NOT received `notif_type` in the last `days` days."""
    return f"""
        NOT EXISTS (
            SELECT 1 FROM notification_log nl
            WHERE nl.uid = u.uid
              AND nl.notification_type = '{notif_type}'
              AND nl.sent_at >= now() - interval '{days} days'
        )
    """


def _not_queued(notif_type: str) -> str:
    """SQL fragment: user does NOT have a pending queue row for `notif_type`."""
    return f"""
        NOT EXISTS (
            SELECT 1 FROM notification_queue nq
            WHERE nq.uid = u.uid
              AND nq.notification_type = '{notif_type}'
              AND nq.status = 'pending'
        )
    """


def _active_channel_clause() -> str:
    """SQL fragment: user has at least one notification channel enabled."""
    return """
        (
            np.email_enabled = TRUE
            OR (np.whatsapp_opted_in = TRUE AND np.whatsapp_enabled = TRUE)
        )
    """


async def _enqueue(uid: str, notif_type: str, channel: str, payload: dict) -> None:
    from app.core.database import get_db
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for, payload)
                    VALUES (%s, %s, %s, now(), %s)
                    """,
                    (uid, notif_type, channel, json.dumps(payload)),
                )
    except Exception as e:
        logger.error("_enqueue failed uid=%s type=%s: %s", uid, notif_type, e)


def _preferred_channel(row) -> str:
    """Pick channel from a DB row that includes np.* fields."""
    wa_ok = row.get("whatsapp_opted_in") and row.get("whatsapp_enabled")
    email_ok = row.get("email_enabled", True)
    preferred = row.get("preferred_channel", "email")
    if preferred == "whatsapp" and wa_ok:
        return "whatsapp"
    if email_ok:
        return "email"
    if wa_ok:
        return "whatsapp"
    return "email"


# ── Job 1: Queue processor ────────────────────────────────────────────────────

async def _queue_processor() -> None:
    """Drain pending notification_queue rows whose scheduled_for <= now()."""
    from app.core.database import get_db
    from app.services.notification_service import notification_service

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, uid, notification_type, channel, payload
                    FROM notification_queue
                    WHERE status = 'pending' AND scheduled_for <= now()
                    ORDER BY scheduled_for
                    LIMIT 50
                    """,
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.error("queue_processor: DB read failed: %s", e)
        return

    for row in rows:
        uid = row["uid"]
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT email, display_name FROM users WHERE uid = %s", (uid,))
                    user = cur.fetchone()
            if not user:
                continue

            payload = row["payload"] or {}
            payload.setdefault("name", user["display_name"] or "")

            success = await notification_service.send_notification(
                uid=uid,
                email=user["email"],
                notification_type=row["notification_type"],
                channel=row["channel"],
                context=payload,
            )
            new_status = "sent" if success else "pending"
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE notification_queue SET status = %s WHERE id = %s",
                        (new_status, str(row["id"])),
                    )
        except Exception as e:
            logger.error("queue_processor: row=%s uid=%s failed: %s", row["id"], uid, e)


# ── Job 2: Daily spark dispatch ───────────────────────────────────────────────

async def _daily_spark_dispatch() -> None:
    """Send daily spark to users whose local time is currently 07:00–09:00."""
    from app.core.database import get_db
    from app.services.notification_service import notification_service

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.uid, u.email, u.display_name,
                           COALESCE(ui.topics, ARRAY['science']) AS topics,
                           COALESCE(np.preferred_channel, 'email') AS preferred_channel
                    FROM users u
                    LEFT JOIN user_interests ui ON ui.uid = u.uid
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE EXTRACT(HOUR FROM (now() AT TIME ZONE COALESCE(np.timezone, 'UTC'))) BETWEEN 7 AND 9
                      AND {not_sent}
                    LIMIT 200
                    """.format(not_sent=_not_sent_recently("daily_spark", 1)),
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("daily_spark_dispatch failed: %s", e)
        return

    for u in users:
        try:
            topics = list(u["topics"] or ["science"])
            await notification_service.send_notification(
                uid=u["uid"],
                email=u["email"],
                notification_type="daily_spark",
                channel=u["preferred_channel"],
                context={
                    "name": u["display_name"] or "",
                    "topics": ", ".join(topics[:3]),
                    "angle": topics[0],
                },
            )
        except Exception as e:
            logger.error("daily_spark_dispatch: uid=%s failed: %s", u["uid"], e)


# ── Job 3: Re-engagement ladder ───────────────────────────────────────────────

async def _re_engagement_ladder() -> None:
    """Tiered re-engagement — different message type per inactivity tier.

    Tier  3–6 days : re_engagement  (first nudge — curiosity hook about their domain)
    Tier  7–13 days: re_engagement  (second nudge — suppress ensures different timing)
    Tier 14–29 days: mind_signature_nudge (progress at stake angle)
    Tier 30+ days  : weekly_digest  (show them what they built, last-ditch)
    """
    from app.core.database import get_db

    tiers = [
        (3,  7,  "re_engagement",        7,  False),
        (7,  14, "re_engagement",        7,  False),
        (14, 30, "mind_signature_nudge", 14, True),
        (30, 999,"weekly_digest",        14, False),
    ]

    for min_days, max_days, notif_type, suppress_days, needs_mastery in tiers:
        max_clause = f"AND u.last_active_date > CURRENT_DATE - {max_days}" if max_days < 999 else ""
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT DISTINCT ON (u.uid)
                               u.uid, u.email, u.display_name,
                               COALESCE(ui.topics[1], 'science') AS domain,
                               ROUND(EXTRACT(EPOCH FROM (now() - u.last_active_date::timestamptz)) / 86400) AS days_inactive,
                               COALESCE(np.preferred_channel, 'email') AS preferred_channel,
                               np.email_enabled,
                               np.whatsapp_opted_in,
                               np.whatsapp_enabled,
                               dm.domain AS mastery_domain,
                               ROUND(dm.mastery_level * 100) AS mastery_pct
                        FROM users u
                        LEFT JOIN user_interests ui ON ui.uid = u.uid
                        LEFT JOIN notification_preferences np ON np.uid = u.uid
                        LEFT JOIN domain_mastery dm ON dm.uid = u.uid
                        WHERE u.last_active_date IS NOT NULL
                          AND u.last_active_date <= CURRENT_DATE - {min_days}
                          {max_clause}
                          AND {_not_sent_recently(notif_type, suppress_days)}
                          AND {_not_queued(notif_type)}
                        {"ORDER BY u.uid, dm.mastery_level DESC NULLS LAST" if needs_mastery else "ORDER BY u.uid"}
                        LIMIT 100
                        """,
                    )
                    users = cur.fetchall()
        except Exception as e:
            logger.error("re_engagement_ladder tier=%s failed: %s", notif_type, e)
            continue

        for u in users:
            try:
                channel = _preferred_channel(u)
                context: dict = {
                    "name": u["display_name"] or "",
                    "domain": u["mastery_domain"] or u["domain"],
                    "days_inactive": int(u["days_inactive"] or min_days),
                }
                if notif_type == "mind_signature_nudge":
                    context["mastery_pct"] = int(u["mastery_pct"] or 0)
                if notif_type == "weekly_digest":
                    context.update({
                        "new_concepts": 0, "active_domains": 0,
                        "domains": u["domain"], "journeys_touched": 0,
                    })
                await _enqueue(u["uid"], notif_type, channel, context)
            except Exception as e:
                logger.error("re_engagement_ladder: uid=%s failed: %s", u["uid"], e)


# ── Job 4: Streak at risk (runs 20:00 UTC) ───────────────────────────────────

async def _streak_risk_check() -> None:
    """Notify users whose streak >= 3 will break tonight if they don't study."""
    from app.core.database import get_db

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.uid, u.email, u.display_name, u.streak_days,
                           COALESCE(np.preferred_channel, 'whatsapp') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE u.streak_days >= 3
                      AND u.last_active_date = CURRENT_DATE - 1
                      AND {_not_sent_recently("streak_at_risk", 1)}
                      AND {_not_queued("streak_at_risk")}
                    LIMIT 500
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("streak_risk_check failed: %s", e)
        return

    for u in users:
        await _enqueue(
            u["uid"], "streak_at_risk", _preferred_channel(u),
            {"name": u["display_name"] or "", "streak_days": int(u["streak_days"])},
        )


# ── Job 5: Streak lost (runs 09:00 UTC) ──────────────────────────────────────

async def _streak_lost_check() -> None:
    """Notify users whose streak of >= 3 days just broke (missed yesterday)."""
    from app.core.database import get_db

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.uid, u.email, u.display_name, u.streak_days,
                           COALESCE(np.preferred_channel, 'whatsapp') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE u.streak_days >= 2
                      AND u.last_active_date = CURRENT_DATE - 2
                      AND {_not_sent_recently("streak_lost", 2)}
                      AND {_not_queued("streak_lost")}
                    LIMIT 500
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("streak_lost_check failed: %s", e)
        return

    for u in users:
        await _enqueue(
            u["uid"], "streak_lost", _preferred_channel(u),
            {"name": u["display_name"] or "", "streak_days": int(u["streak_days"])},
        )


# ── Job 6: Streak milestone (runs 10:00 UTC) ─────────────────────────────────

async def _streak_milestone_check() -> None:
    """Celebrate when a user hits a streak milestone today (3, 7, 14, 30 days)."""
    from app.core.database import get_db

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.uid, u.email, u.display_name, u.streak_days,
                           COALESCE(np.preferred_channel, 'whatsapp') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE u.streak_days IN (3, 7, 14, 30)
                      AND u.last_active_date = CURRENT_DATE
                      AND {_not_sent_recently("streak_milestone", 1)}
                      AND {_not_queued("streak_milestone")}
                    LIMIT 500
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("streak_milestone_check failed: %s", e)
        return

    for u in users:
        await _enqueue(
            u["uid"], "streak_milestone", _preferred_channel(u),
            {"name": u["display_name"] or "", "streak_days": int(u["streak_days"])},
        )


# ── Job 7: Journey completion nudge (runs every 6h) ──────────────────────────

async def _journey_completion_nudge() -> None:
    """Nudge users who are 1-2 steps away from finishing a journey they started."""
    from app.core.database import get_db

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (u.uid)
                           u.uid, u.email, u.display_name,
                           j.title AS journey_title,
                           jsonb_array_length(j.steps) - COUNT(up.step_id) AS steps_remaining,
                           COALESCE(np.preferred_channel, 'whatsapp') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    JOIN journeys j ON j.uid = u.uid
                    LEFT JOIN user_progress up ON up.uid = u.uid AND up.journey_id = j.id
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE j.steps IS NOT NULL
                      AND {_not_sent_recently("journey_almost_done", 3)}
                      AND {_not_queued("journey_almost_done")}
                    GROUP BY u.uid, u.email, u.display_name, j.id, j.title,
                             np.preferred_channel, np.email_enabled,
                             np.whatsapp_opted_in, np.whatsapp_enabled
                    HAVING COUNT(up.step_id) > 0
                       AND jsonb_array_length(j.steps) - COUNT(up.step_id) BETWEEN 1 AND 2
                    ORDER BY u.uid, steps_remaining ASC
                    LIMIT 200
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("journey_completion_nudge failed: %s", e)
        return

    for u in users:
        await _enqueue(
            u["uid"], "journey_almost_done", _preferred_channel(u),
            {
                "name": u["display_name"] or "",
                "journey_title": u["journey_title"],
                "steps_remaining": int(u["steps_remaining"]),
            },
        )


# ── Job 8: Mind signature nudge (runs 10:00 UTC) ─────────────────────────────

async def _mind_signature_nudge() -> None:
    """Nudge users who are 30-49% of the way to a Mind Signature — show them how close they are."""
    from app.core.database import get_db

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (u.uid)
                           u.uid, u.email, u.display_name,
                           dm.domain, ROUND(dm.mastery_level * 100) AS mastery_pct,
                           COALESCE(np.preferred_channel, 'whatsapp') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    JOIN domain_mastery dm ON dm.uid = u.uid
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE dm.mastery_level BETWEEN 0.30 AND 0.49
                      AND dm.concept_count >= 2
                      AND {_not_sent_recently("mind_signature_nudge", 7)}
                      AND {_not_queued("mind_signature_nudge")}
                    ORDER BY u.uid, dm.mastery_level DESC
                    LIMIT 200
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("mind_signature_nudge failed: %s", e)
        return

    for u in users:
        await _enqueue(
            u["uid"], "mind_signature_nudge", _preferred_channel(u),
            {
                "name": u["display_name"] or "",
                "domain": u["domain"],
                "mastery_pct": int(u["mastery_pct"]),
            },
        )


# ── Job 9: Weekly digest (runs Sunday 18:00 UTC) ─────────────────────────────

async def _weekly_digest_dispatch() -> None:
    """Send a weekly learning summary to all users active in the past 7 days."""
    from app.core.database import get_db
    from app.services.notification_service import notification_service

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT u.uid, u.email, u.display_name,
                           COUNT(DISTINCT kn.concept)
                               FILTER (WHERE kn.discovered_at >= now() - interval '7 days') AS new_concepts,
                           COUNT(DISTINCT kn.domain)
                               FILTER (WHERE kn.last_reinforced >= now() - interval '7 days') AS active_domains,
                           STRING_AGG(DISTINCT kn.domain, ', ')
                               FILTER (WHERE kn.last_reinforced >= now() - interval '7 days') AS domains,
                           COUNT(DISTINCT up.journey_id)
                               FILTER (WHERE up.completed_at >= now() - interval '7 days') AS journeys_touched,
                           COALESCE(np.preferred_channel, 'email') AS preferred_channel,
                           np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    FROM users u
                    LEFT JOIN knowledge_nodes kn ON kn.uid = u.uid
                    LEFT JOIN user_progress up ON up.uid = u.uid
                    LEFT JOIN notification_preferences np ON np.uid = u.uid
                    WHERE u.last_active_date >= CURRENT_DATE - 6
                      AND {_not_sent_recently("weekly_digest", 6)}
                    GROUP BY u.uid, u.email, u.display_name, np.preferred_channel,
                             np.email_enabled, np.whatsapp_opted_in, np.whatsapp_enabled
                    HAVING COUNT(kn.concept) FILTER (WHERE kn.discovered_at >= now() - interval '7 days') > 0
                    LIMIT 1000
                    """,
                )
                users = cur.fetchall()
    except Exception as e:
        logger.error("weekly_digest_dispatch failed: %s", e)
        return

    for u in users:
        try:
            await notification_service.send_notification(
                uid=u["uid"],
                email=u["email"],
                notification_type="weekly_digest",
                channel=_preferred_channel(u),
                context={
                    "name": u["display_name"] or "",
                    "new_concepts": int(u["new_concepts"] or 0),
                    "active_domains": int(u["active_domains"] or 0),
                    "domains": u["domains"] or "various topics",
                    "journeys_touched": int(u["journeys_touched"] or 0),
                },
            )
        except Exception as e:
            logger.error("weekly_digest: uid=%s failed: %s", u["uid"], e)


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_scheduler() -> AsyncIOScheduler:
    jobs = [
        (_queue_processor,           "cron", {"minute": "*/15"},          "queue_processor"),
        (_daily_spark_dispatch,      "cron", {"minute": "*/15"},          "daily_spark_dispatch"),
        (_re_engagement_ladder,      "cron", {"hour": 9,  "minute": 0},   "re_engagement_ladder"),
        (_streak_lost_check,         "cron", {"hour": 9,  "minute": 0},   "streak_lost_check"),
        (_streak_milestone_check,    "cron", {"hour": 10, "minute": 0},   "streak_milestone_check"),
        (_mind_signature_nudge,      "cron", {"hour": 10, "minute": 0},   "mind_signature_nudge"),
        (_streak_risk_check,         "cron", {"hour": 20, "minute": 0},   "streak_risk_check"),
        (_journey_completion_nudge,  "cron", {"hour": "*/6"},             "journey_completion_nudge"),
        (_weekly_digest_dispatch,    "cron", {"day_of_week": "sun",
                                              "hour": 18, "minute": 0},   "weekly_digest_dispatch"),
    ]
    for func, trigger, kwargs, job_id in jobs:
        scheduler.add_job(func, trigger, id=job_id, replace_existing=True, **kwargs)
    return scheduler
