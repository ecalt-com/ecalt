"""Account deletion cascade (GDPR Art. 17), shared by the self-serve
DELETE /users/me endpoint and parent-initiated child deletion (Phase 1).

Consent proof survives: consent_events rows are pseudonymized, never deleted
(the append-only trigger permits exactly that UPDATE). The caller is
responsible for purging the Firebase Auth credential afterwards.
"""
import logging
from datetime import datetime, timezone

from app.core.database import get_db
from app.services.consent_service import pseudonymize_uid

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
                "account_status, consent_given_at, consent_version, created_at FROM users WHERE uid = %s",
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
    }


def delete_user_account(uid: str) -> None:
    """Cancel billing and hard-delete all personal data for a uid."""
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

    # Cascade delete — order respects FK dependencies
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversation_messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE uid = %s)",
                (uid,),
            )
            cur.execute("DELETE FROM conversations WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM user_progress WHERE uid = %s", (uid,))
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
            cur.execute("DELETE FROM family_links WHERE child_uid = %s OR parent_uid = %s", (uid, uid))
            cur.execute("DELETE FROM child_settings WHERE child_uid = %s", (uid,))
            # Consent proof must survive erasure (COPPA/GDPR): pseudonymize
            # instead of deleting — the only UPDATE the append-only trigger allows.
            cur.execute(
                "UPDATE consent_events SET uid = %s WHERE uid = %s",
                (pseudonymize_uid(uid), uid),
            )
            cur.execute("DELETE FROM subscriptions WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM notification_preferences WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM users WHERE uid = %s", (uid,))
            cur.execute(
                "INSERT INTO deletion_requests (uid, status, completed_at) VALUES (%s, 'completed', now())",
                (uid,),
            )
