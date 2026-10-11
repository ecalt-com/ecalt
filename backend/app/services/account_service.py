"""Account deletion cascade (GDPR Art. 17), shared by the self-serve
DELETE /users/me endpoint and parent-initiated child deletion (Phase 1).

Consent proof survives: consent_events rows are pseudonymized, never deleted
(the append-only trigger permits exactly that UPDATE). The caller is
responsible for purging the Firebase Auth credential afterwards.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import get_db
from app.services.consent_service import pseudonymize_uid, record_consent_event

logger = logging.getLogger(__name__)


def build_user_export(uid: str) -> dict:
    """Full personal-data export (GDPR Art. 20), shared by self-serve export
    and parent-initiated child export (COPPA parental review right)."""
    def _iso(val):
        return val.isoformat() if hasattr(val, "isoformat") else val

    def _row(r):
        return {k: _iso(v) for k, v in dict(r).items()}

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid, email, display_name, photo_url, onboarding_done, streak_days, "
                "account_status, consent_given_at, consent_version, created_at, "
                "birth_year, birth_month, jurisdiction, age_group_flag, role, paused, profession "
                "FROM users WHERE uid = %s",
                (uid,),
            )
            user_row = cur.fetchone()

            cur.execute("SELECT * FROM journeys WHERE uid = %s", (uid,))
            journeys = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM user_progress WHERE uid = %s", (uid,))
            progress = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT id, title, started_at, last_active FROM conversations WHERE uid = %s", (uid,))
            conv_rows = cur.fetchall()
            conversations = []
            for conv in conv_rows:
                cur.execute(
                    "SELECT role, content, model_used, created_at FROM conversation_messages WHERE conversation_id = %s ORDER BY id",
                    (conv["id"],),
                )
                conversations.append({**_row(conv), "messages": [_row(m) for m in cur.fetchall()]})

            cur.execute("SELECT * FROM knowledge_nodes WHERE uid = %s ORDER BY strength DESC", (uid,))
            knowledge_nodes = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM domain_mastery WHERE uid = %s", (uid,))
            domain_mastery = [_row(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT id, verification_hash, capability_narrative, domains, constellation_data, generated_at "
                "FROM mind_signatures WHERE uid = %s ORDER BY generated_at DESC",
                (uid,),
            )
            mind_signatures = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM user_interests WHERE uid = %s", (uid,))
            interests_row = cur.fetchone()

            cur.execute("SELECT coupon_code, credit_applied_cents, bonus_messages_applied, redeemed_at FROM coupon_redemptions WHERE uid = %s", (uid,))
            coupon_redemptions = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT period_start, input_tokens, output_tokens, estimated_cost_cents, message_count FROM token_usage WHERE uid = %s", (uid,))
            token_usage = [_row(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT action, method, policy_version, jurisdiction, created_at "
                "FROM consent_events WHERE uid = %s ORDER BY created_at",
                (uid,),
            )
            consent_events = [_row(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT concept, journey_id, step_id, is_correct, difficulty, hints_used, "
                "skipped, answered_at FROM quiz_results WHERE uid = %s ORDER BY answered_at",
                (uid,),
            )
            quiz_results = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM step_feedback WHERE uid = %s", (uid,))
            step_feedback = [_row(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM notification_preferences WHERE uid = %s", (uid,))
            notification_row = cur.fetchone()

            cur.execute("SELECT * FROM child_settings WHERE child_uid = %s", (uid,))
            child_settings_row = cur.fetchone()

            cur.execute(
                "SELECT parent_uid, child_uid, status, created_at, revoked_at "
                "FROM family_links WHERE child_uid = %s OR parent_uid = %s",
                (uid, uid),
            )
            family_links = [_row(r) for r in cur.fetchall()]

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": _row(user_row) if user_row else {},
        "journeys": journeys,
        "progress": progress,
        "conversations": conversations,
        "knowledge_nodes": knowledge_nodes,
        "domain_mastery": domain_mastery,
        "mind_signatures": mind_signatures,
        "interests": _row(interests_row) if interests_row else {},
        "coupon_redemptions": coupon_redemptions,
        "token_usage": token_usage,
        "consent_events": consent_events,
        "quiz_results": quiz_results,
        "step_feedback": step_feedback,
        "notification_preferences": _row(notification_row) if notification_row else {},
        "parental_controls": _row(child_settings_row) if child_settings_row else {},
        "family_links": family_links,
    }


def delete_user_account(uid: str, consent_event: Optional[dict[str, Any]] = None) -> None:
    """Cancel billing and hard-delete all personal data for a uid.

    consent_event: kwargs for record_consent_event (must include 'action'),
    written inside the deletion transaction so the audit row and the erasure
    commit — or roll back — together. It is pseudonymized with the rest.
    """
    # Cancel active Stripe subscription (non-fatal)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT stripe_subscription_id FROM subscriptions WHERE uid = %s AND status IN ('active', 'trialing')",
                    (uid,),
                )
                sub_row = cur.fetchone()
        if sub_row and sub_row.get("stripe_subscription_id"):
            import stripe
            from app.core.config import settings as _settings
            stripe.api_key = _settings.STRIPE_SECRET_KEY
            stripe.Subscription.cancel(sub_row["stripe_subscription_id"])
    except Exception as e:
        logger.warning("stripe cancel failed during deletion uid=%s: %s", uid, e)

    # Cascade delete — order respects FK dependencies. Tables whose FK to
    # users/journeys is NO ACTION (journey_likes, visual_events, journeys.
    # forked_from_id) must be cleared first or the whole erasure rolls back.
    with get_db() as conn:
        with conn.cursor() as cur:
            if consent_event:
                ev = dict(consent_event)
                record_consent_event(uid, ev.pop("action"), cur=cur, **ev)
            cur.execute(
                "DELETE FROM conversation_messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE uid = %s)",
                (uid,),
            )
            cur.execute("DELETE FROM conversations WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM user_progress WHERE uid = %s", (uid,))
            # Quiz data: results + quality log reference quiz_sessions.
            cur.execute(
                "DELETE FROM quiz_quality_log WHERE uid = %s OR quiz_session_id IN "
                "(SELECT id FROM quiz_sessions WHERE uid = %s)",
                (uid, uid),
            )
            cur.execute(
                "DELETE FROM quiz_results WHERE uid = %s OR session_id IN "
                "(SELECT id FROM quiz_sessions WHERE uid = %s)",
                (uid, uid),
            )
            cur.execute("DELETE FROM quiz_sessions WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM step_feedback WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM cognitive_fingerprints WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM visual_events WHERE uid = %s", (uid,))
            # Likes the user gave, and likes/forks pointing at the user's journeys.
            cur.execute("DELETE FROM journey_likes WHERE uid = %s", (uid,))
            cur.execute(
                "DELETE FROM journey_likes WHERE journey_id IN (SELECT id FROM journeys WHERE uid = %s)",
                (uid,),
            )
            cur.execute(
                "UPDATE journeys SET forked_from_id = NULL WHERE forked_from_id IN "
                "(SELECT id FROM journeys WHERE uid = %s)",
                (uid,),
            )
            cur.execute(
                "DELETE FROM step_content WHERE journey_id IN (SELECT id FROM journeys WHERE uid = %s)",
                (uid,),
            )
            cur.execute("DELETE FROM journeys WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM knowledge_nodes WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM domain_mastery WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM mind_signatures WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM daily_sparks WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM user_interests WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM token_usage WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM coupon_redemptions WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM spark_usage WHERE key = %s", (uid,))
            cur.execute("DELETE FROM parental_consent WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM consent_followups WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM family_links WHERE child_uid = %s OR parent_uid = %s", (uid, uid))
            cur.execute("DELETE FROM child_settings WHERE child_uid = %s", (uid,))
            cur.execute("DELETE FROM parent_pins WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM profile_claims WHERE uid = %s OR parent_uid = %s", (uid, uid))
            # auth_identities is removed by firebase_admin.purge_login, which
            # callers run after this cascade (it needs the mapping to find the login).
            # Consent proof must survive erasure (COPPA/GDPR): pseudonymize
            # instead of deleting — the only UPDATE the append-only trigger allows.
            cur.execute(
                "UPDATE consent_events SET uid = %s WHERE uid = %s",
                (pseudonymize_uid(uid), uid),
            )
            cur.execute("DELETE FROM subscriptions WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM notification_preferences WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM users WHERE uid = %s", (uid,))
            # Close any pending grace-window deletion so the scheduler doesn't
            # re-run erasure for an account that no longer exists.
            cur.execute(
                "UPDATE deletion_requests SET status = 'completed', completed_at = now() "
                "WHERE uid = %s AND status = 'scheduled'",
                (uid,),
            )
            cur.execute(
                "INSERT INTO deletion_requests (uid, status, completed_at) VALUES (%s, 'completed', now())",
                (uid,),
            )
