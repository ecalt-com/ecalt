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


# ── Consent follow-up (email-plus verification tier) ─────────────────────────

async def _consent_followup_dispatch() -> None:
    """Send the delayed 'you approved X's account — wasn't you?' notice.

    Sending the notice completes the email-plus verification: the child's
    verification_status flips to 'verified' unless the parent later objects
    via the report link (which suspends the account).
    """
    from app.core.config import settings
    from app.core.database import get_db
    from app.services.consent_service import make_consent_report_token, record_consent_event
    from app.services.email_service import send_email_plus_followup

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, uid, parent_uid, parent_email, child_name "
                    "FROM consent_followups WHERE sent_at IS NULL AND send_after <= now() "
                    "ORDER BY send_after LIMIT 50"
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.error("consent_followup: query failed: %s", e)
        return

    for r in rows:
        try:
            report_url = (
                f"{settings.FRONTEND_URL}/consent/report"
                f"?child={r['uid']}&token={make_consent_report_token(r['uid'])}"
            )
            ok = await send_email_plus_followup(
                r["parent_email"], r["child_name"] or "your child",
                report_url, r["parent_uid"] or r["uid"],
            )
            if not ok:
                continue  # transport failure — retried on the next run
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE consent_followups SET sent_at = now() WHERE id = %s",
                        (r["id"],),
                    )
                    cur.execute(
                        "UPDATE child_settings SET verification_status = 'verified', verified_at = now() "
                        "WHERE child_uid = %s AND verification_tier = 'email_plus' "
                        "  AND verification_status = 'unverified'",
                        (r["uid"],),
                    )
                    record_consent_event(
                        r["uid"], "followup_sent",
                        parent_uid=r["parent_uid"], parent_email=r["parent_email"],
                        method="email_plus", cur=cur,
                    )
        except Exception as e:
            logger.error("consent_followup: id=%s failed: %s", r.get("id"), e)


# ── Weekly family digest (Phase 3: parent visibility) ────────────────────────

async def _family_digest_dispatch() -> None:
    """One email per parent summarizing each linked child's week. Children with
    no activity are omitted; parents whose children were all inactive get nothing."""
    from app.core.database import get_db
    from app.services.email_service import send_family_digest_email

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fl.parent_uid, fl.child_uid,
                           u_p.email AS parent_email,
                           u_c.display_name AS child_name, u_c.streak_days
                      FROM family_links fl
                      JOIN users u_p ON u_p.uid = fl.parent_uid
                      JOIN users u_c ON u_c.uid = fl.child_uid
                 LEFT JOIN child_settings cs ON cs.child_uid = fl.child_uid
                     WHERE fl.status = 'active'
                       AND COALESCE(cs.weekly_digest_enabled, TRUE)
                       AND u_p.email IS NOT NULL
                    """
                )
                links = cur.fetchall()

                by_parent: dict[str, dict] = {}
                for link in links:
                    cur.execute(
                        """
                        SELECT
                          (SELECT count(*) FROM user_progress
                            WHERE uid = %(uid)s AND completed_at >= now() - interval '7 days') AS steps_completed,
                          (SELECT count(*) FROM journeys
                            WHERE uid = %(uid)s AND created_at >= now() - interval '7 days')   AS journeys_started,
                          (SELECT count(*) FROM quiz_results
                            WHERE uid = %(uid)s AND NOT skipped
                              AND answered_at >= now() - interval '7 days')                    AS quiz_answers,
                          (SELECT count(*) FROM quiz_results
                            WHERE uid = %(uid)s AND NOT skipped AND is_correct
                              AND answered_at >= now() - interval '7 days')                    AS quiz_correct,
                          (SELECT domain FROM domain_mastery
                            WHERE uid = %(uid)s ORDER BY updated_at DESC LIMIT 1)              AS top_domain
                        """,
                        {"uid": link["child_uid"]},
                    )
                    stats = dict(cur.fetchone() or {})
                    if not (stats.get("steps_completed") or stats.get("journeys_started")
                            or stats.get("quiz_answers")):
                        continue  # inactive child — nothing to report
                    entry = by_parent.setdefault(
                        link["parent_uid"],
                        {"parent_email": link["parent_email"], "children": []},
                    )
                    entry["children"].append({
                        "name": link["child_name"] or "Your child",
                        "streak_days": link["streak_days"] or 0,
                        **stats,
                    })
    except Exception as e:
        logger.error("family_digest: query failed: %s", e)
        return

    for parent_uid, entry in by_parent.items():
        try:
            await send_family_digest_email(entry["parent_email"], parent_uid, entry["children"])
        except Exception as e:
            logger.error("family_digest: parent=%s failed: %s", parent_uid, e)


# ── Scheduled deletions (Phase 4: consent revocation grace window) ───────────

async def _scheduled_deletion_dispatch() -> None:
    """Hard-delete accounts whose revocation grace window (14 days) has passed."""
    from app.core.database import get_db
    from app.services.account_service import delete_user_account
    from app.services.firebase_admin import delete_firebase_user

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, uid FROM deletion_requests "
                    "WHERE status = 'scheduled' AND requested_at <= now() - interval '14 days'"
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.error("scheduled_deletion: query failed: %s", e)
        return

    for r in rows:
        try:
            delete_user_account(r["uid"])
            await delete_firebase_user(r["uid"])
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE deletion_requests SET status = 'completed', completed_at = now() WHERE id = %s",
                        (r["id"],),
                    )
            logger.info("scheduled_deletion: completed uid=%s", r["uid"])
        except Exception as e:
            logger.error("scheduled_deletion: uid=%s failed: %s", r["uid"], e)


# ── Family lifecycle (Phase 5): age-up, pending expiry, re-consent, retention ─

async def _family_lifecycle_dispatch() -> None:
    """Daily lifecycle sweep. Sections are isolated — one failing doesn't stop the rest."""
    await _lifecycle_age_up()
    await _lifecycle_pending_expiry()
    await _lifecycle_reconsent()
    await _lifecycle_retention()


async def _lifecycle_age_up() -> None:
    """Children who reached adulthood: graduate the family link, end parent
    visibility/controls, and ask them to re-accept the policy as an adult."""
    from app.core.auth import invalidate_status_cache
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.jurisdiction import ADULT_AGE, age_from_birth
    from app.services.consent_service import record_consent_event
    from app.services.email_service import send_family_notice_email

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT uid, email, display_name, birth_year, birth_month, jurisdiction
                      FROM users
                     WHERE age_group_flag IN ('teen', 'child')
                       AND birth_year IS NOT NULL
                       AND birth_year <= EXTRACT(year FROM now())::int - %s + 1
                    """,
                    (ADULT_AGE,),
                )
                candidates = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("lifecycle.age_up: query failed: %s", e)
        return

    for u in candidates:
        if age_from_birth(u["birth_year"], u.get("birth_month")) < ADULT_AGE:
            continue
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    # NULL consent_version → needs_reconsent flag on next login,
                    # so they accept the policy themselves as an adult.
                    cur.execute(
                        "UPDATE users SET age_group_flag = 'adult', paused = false, "
                        "consent_version = NULL WHERE uid = %s",
                        (u["uid"],),
                    )
                    cur.execute(
                        "UPDATE family_links SET status = 'graduated', revoked_at = now() "
                        "WHERE child_uid = %s AND status = 'active' RETURNING parent_uid",
                        (u["uid"],),
                    )
                    link = cur.fetchone()
                    cur.execute("DELETE FROM child_settings WHERE child_uid = %s", (u["uid"],))
                    record_consent_event(
                        u["uid"], "age_up", method="lifecycle",
                        parent_uid=link["parent_uid"] if link else None,
                        jurisdiction=u.get("jurisdiction"), cur=cur,
                    )
                    parent_email = None
                    if link:
                        cur.execute("SELECT email FROM users WHERE uid = %s", (link["parent_uid"],))
                        prow = cur.fetchone()
                        parent_email = prow and prow.get("email")
            invalidate_status_cache(u["uid"])

            name = u.get("display_name") or "Your child"
            if parent_email:
                await send_family_notice_email(
                    parent_email, link["parent_uid"],
                    f"{name} is now an adult on ECALT",
                    [f"<strong>{name}</strong> has reached adulthood, so their ECALT account "
                     "is now fully their own. Your family link, dashboard visibility, and "
                     "parental controls for this account have ended, as required by privacy law."],
                )
            if u.get("email"):
                await send_family_notice_email(
                    u["email"], u["uid"],
                    "Your ECALT account is now fully yours",
                    ["Happy birthday! You're an adult now, so your ECALT account is fully "
                     "your own — your parent can no longer see your activity or manage it.",
                     "Next time you sign in, we'll ask you to accept the privacy policy yourself."],
                    cta_url=settings.FRONTEND_URL, cta_label="Open ECALT",
                )
            logger.info("lifecycle.age_up: graduated uid=%s", u["uid"])
        except Exception as e:
            logger.error("lifecycle.age_up: uid=%s failed: %s", u["uid"], e)


async def _lifecycle_pending_expiry() -> None:
    """COPPA data minimization: consent never arrived → hard-delete after 30 days.
    (Card-tier children awaiting verification have consent_given_at set → excluded.)"""
    from app.core.database import get_db
    from app.services.account_service import delete_user_account
    from app.services.consent_service import record_consent_event
    from app.services.firebase_admin import delete_firebase_user

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT uid, jurisdiction FROM users
                     WHERE account_status = 'parental_consent_pending'
                       AND consent_given_at IS NULL
                       AND created_at <= now() - interval '30 days'
                    """
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("lifecycle.pending_expiry: query failed: %s", e)
        return

    for r in rows:
        try:
            record_consent_event(
                r["uid"], "expired", method="lifecycle",
                jurisdiction=r.get("jurisdiction"),
                details={"trigger": "consent_never_confirmed"},
            )
            delete_user_account(r["uid"])
            await delete_firebase_user(r["uid"])
            logger.info("lifecycle.pending_expiry: deleted uid=%s", r["uid"])
        except Exception as e:
            logger.error("lifecycle.pending_expiry: uid=%s failed: %s", r["uid"], e)


async def _lifecycle_reconsent() -> None:
    """Policy-version bump: notify parents of children on a stale version; pause
    children whose parents haven't re-consented 30 days after the notice."""
    from app.core.auth import invalidate_status_cache
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.jurisdiction import CONSENT_POLICY_VERSION
    from app.services.consent_service import record_consent_event
    from app.services.email_service import send_family_notice_email

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.uid, u.display_name, u.paused,
                           fl.parent_uid, p.email AS parent_email,
                           (SELECT max(created_at) FROM consent_events ce
                             WHERE ce.uid = u.uid AND ce.method = 'reconsent_notice'
                               AND ce.policy_version = %(v)s) AS noticed_at
                      FROM users u
                      JOIN family_links fl ON fl.child_uid = u.uid AND fl.status = 'active'
                      JOIN users p ON p.uid = fl.parent_uid
                     WHERE u.consent_given_at IS NOT NULL
                       AND u.consent_version IS DISTINCT FROM %(v)s
                       AND u.age_group_flag <> 'adult'
                    """,
                    {"v": CONSENT_POLICY_VERSION},
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("lifecycle.reconsent: query failed: %s", e)
        return

    notify: dict[str, dict] = {}
    for r in rows:
        try:
            if r["noticed_at"] is None:
                entry = notify.setdefault(
                    r["parent_uid"], {"email": r["parent_email"], "children": []},
                )
                entry["children"].append(r)
            else:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT (%s::timestamptz <= now() - interval '30 days') AS lapsed",
                            (r["noticed_at"],),
                        )
                        lapsed = cur.fetchone()["lapsed"]
                        if lapsed and not r["paused"]:
                            cur.execute(
                                "UPDATE users SET paused = true WHERE uid = %s", (r["uid"],),
                            )
                            record_consent_event(
                                r["uid"], "expired", method="reconsent_lapsed",
                                parent_uid=r["parent_uid"], cur=cur,
                            )
                if lapsed and not r["paused"]:
                    invalidate_status_cache(r["uid"])
                    logger.info("lifecycle.reconsent: paused uid=%s (lapsed)", r["uid"])
        except Exception as e:
            logger.error("lifecycle.reconsent: uid=%s failed: %s", r["uid"], e)

    for parent_uid, entry in notify.items():
        try:
            names = ", ".join(c.get("display_name") or "your child" for c in entry["children"])
            ok = await send_family_notice_email(
                entry["email"], parent_uid,
                "Action needed: our privacy policy changed",
                [f"We've updated the ECALT privacy policy. Because you consented on behalf of "
                 f"<strong>{names}</strong>, please review and re-accept it within 30 days — "
                 "otherwise their account will be paused until you do."],
                cta_url=f"{settings.FRONTEND_URL}/family", cta_label="Review & re-accept",
            )
            if ok:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        for c in entry["children"]:
                            record_consent_event(
                                c["uid"], "requested", method="reconsent_notice",
                                parent_uid=parent_uid, parent_email=entry["email"], cur=cur,
                            )
        except Exception as e:
            logger.error("lifecycle.reconsent: notify parent=%s failed: %s", parent_uid, e)


async def _lifecycle_retention() -> None:
    """Written retention policy (2025 COPPA amendments): linked children inactive
    for 12 months → parent notice; still inactive 30 days later → schedule the
    standard 14-day grace deletion (parent can cancel from the dashboard).
    A cancelled cycle isn't re-noticed for ~11 months."""
    from app.core.config import settings
    from app.core.database import get_db
    from app.services.consent_service import record_consent_event
    from app.services.email_service import send_family_notice_email

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.uid, u.display_name, fl.parent_uid, p.email AS parent_email,
                           (SELECT max(created_at) FROM consent_events ce
                             WHERE ce.uid = u.uid AND ce.method = 'retention_notice') AS noticed_at,
                           EXISTS (SELECT 1 FROM deletion_requests dr
                                    WHERE dr.uid = u.uid AND dr.status = 'scheduled') AS scheduled
                      FROM users u
                      JOIN family_links fl ON fl.child_uid = u.uid AND fl.status = 'active'
                      JOIN users p ON p.uid = fl.parent_uid
                     WHERE GREATEST(COALESCE(u.last_active_date, u.created_at::date),
                                    u.created_at::date) <= (now() - interval '12 months')::date
                    """
                )
                rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("lifecycle.retention: query failed: %s", e)
        return

    for r in rows:
        if r["scheduled"]:
            continue
        try:
            name = r.get("display_name") or "Your child"
            if r["noticed_at"] is None:
                ok = await send_family_notice_email(
                    r["parent_email"], r["parent_uid"],
                    f"{name}'s ECALT account has been inactive for a year",
                    [f"<strong>{name}</strong> hasn't used ECALT in 12 months. Our retention "
                     "policy for children's data means the account and all its data will be "
                     "deleted in about 30 days unless they sign in again — or you keep or "
                     "delete it from your Family dashboard."],
                    cta_url=f"{settings.FRONTEND_URL}/family", cta_label="Open Family Dashboard",
                )
                if ok:
                    record_consent_event(
                        r["uid"], "requested", method="retention_notice",
                        parent_uid=r["parent_uid"], parent_email=r["parent_email"],
                    )
                continue

            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT (%(t)s::timestamptz <= now() - interval '30 days') AS due, "
                        "       (%(t)s::timestamptz <= now() - interval '60 days') AS stale",
                        {"t": r["noticed_at"]},
                    )
                    win = cur.fetchone()
            # due within the 30–60 day window → schedule; older = a cancelled
            # cycle, leave alone until the next annual notice (>11 months).
            if win["due"] and not win["stale"]:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO deletion_requests (uid, status) VALUES (%s, 'scheduled')",
                            (r["uid"],),
                        )
                await send_family_notice_email(
                    r["parent_email"], r["parent_uid"],
                    f"{name}'s inactive ECALT account will be deleted in 14 days",
                    [f"As announced 30 days ago, <strong>{name}</strong>'s inactive account is "
                     "now scheduled for permanent deletion in 14 days. You can still cancel "
                     "this or download their data from your Family dashboard."],
                    cta_url=f"{settings.FRONTEND_URL}/family", cta_label="Open Family Dashboard",
                )
                logger.info("lifecycle.retention: scheduled deletion uid=%s", r["uid"])
        except Exception as e:
            logger.error("lifecycle.retention: uid=%s failed: %s", r["uid"], e)


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
        (_consent_followup_dispatch, "cron", {"minute": 10},              "consent_followup_dispatch"),
        (_family_digest_dispatch,    "cron", {"day_of_week": "sun",
                                              "hour": 17, "minute": 0},   "family_digest_dispatch"),
        (_scheduled_deletion_dispatch, "cron", {"hour": 3, "minute": 30}, "scheduled_deletion_dispatch"),
        (_family_lifecycle_dispatch,   "cron", {"hour": 4, "minute": 0},  "family_lifecycle_dispatch"),
    ]
    for func, trigger, kwargs, job_id in jobs:
        scheduler.add_job(func, trigger, id=job_id, replace_existing=True, **kwargs)
    return scheduler
