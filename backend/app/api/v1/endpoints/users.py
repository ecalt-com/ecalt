import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import get_required_user
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    onboarding_done: bool = False
    streak_days: int = 0
    whatsapp_opted_in: bool = False
    has_notification_prefs: bool = False
    account_status: str = "active"
    consent_given_at: Optional[datetime] = None
    needs_birth_year: bool = False


class UserUpsertRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    birth_year: Optional[int] = None
    parent_email: Optional[str] = None


@router.post("", response_model=UserProfile, summary="Upsert user on sign-in")
async def upsert_user(body: UserUpsertRequest, uid: str = Depends(get_required_user)):
    """Called once after Google sign-in. Enforces COPPA age gate when birth_year is provided."""
    current_year = date.today().year

    if body.birth_year is not None:
        age = current_year - body.birth_year

        # COPPA absolute requirement: under-13 data must never be collected.
        if age < 13:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "under_13",
                    "message": (
                        "ECALT is for learners aged 13 and over. "
                        "Please ask a parent or guardian to create an account."
                    ),
                },
            )

        if age <= 17:
            if not body.parent_email:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "parent_email_required",
                        "message": "Parental consent is required for users aged 13–17.",
                    },
                )
            # Insert with pending status — account locked until parent confirms.
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (uid, email, display_name, photo_url,
                                          birth_year, age_group_flag, account_status)
                        VALUES (%s, %s, %s, %s, %s, 'teen', 'parental_consent_pending')
                        ON CONFLICT (uid) DO UPDATE
                            SET email        = EXCLUDED.email,
                                display_name = EXCLUDED.display_name,
                                photo_url    = EXCLUDED.photo_url
                        RETURNING *
                        """,
                        (uid, body.email, body.display_name, body.photo_url, body.birth_year),
                    )
                    row = cur.fetchone()

            # Create / replace consent token
            token = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM parental_consent WHERE uid = %s", (uid,))
                    cur.execute(
                        """
                        INSERT INTO parental_consent (token, uid, parent_email, expires_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (token, uid, body.parent_email, expires_at),
                    )

            # Fire-and-forget consent email
            from app.services.email_service import send_parental_consent_email
            asyncio.ensure_future(send_parental_consent_email(body.parent_email, uid, token))

            return UserProfile(**dict(row))

        # age >= 18: standard flow — record consent timestamp
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (uid, email, display_name, photo_url,
                                      birth_year, age_group_flag, account_status,
                                      consent_given_at, consent_version)
                    VALUES (%s, %s, %s, %s, %s, 'adult', 'active', now(), '1.0')
                    ON CONFLICT (uid) DO UPDATE
                        SET email        = EXCLUDED.email,
                            display_name = EXCLUDED.display_name,
                            photo_url    = EXCLUDED.photo_url
                    RETURNING *
                    """,
                    (uid, body.email, body.display_name, body.photo_url, body.birth_year),
                )
                row = cur.fetchone()
        return UserProfile(**dict(row))

    # No birth_year (re-login or legacy client): update profile only
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (uid, email, display_name, photo_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE
                    SET email        = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        photo_url    = EXCLUDED.photo_url
                RETURNING *
                """,
                (uid, body.email, body.display_name, body.photo_url),
            )
            row = cur.fetchone()
    needs = dict(row).get('birth_year') is None
    return UserProfile(**{**dict(row), 'needs_birth_year': needs})


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
def get_me(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*,
                       COALESCE(np.whatsapp_opted_in, FALSE) AS whatsapp_opted_in,
                       (np.uid IS NOT NULL)                  AS has_notification_prefs
                  FROM users u
             LEFT JOIN notification_preferences np ON np.uid = u.uid
                 WHERE u.uid = %s
                """,
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        return UserProfile(uid=uid)
    return UserProfile(**dict(row))


@router.patch("/me/onboarding", response_model=UserProfile, summary="Mark onboarding complete")
def complete_onboarding(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET onboarding_done = TRUE WHERE uid = %s RETURNING *",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**dict(row))


class InterestsRequest(BaseModel):
    topics: list[str]
    age_group: str = "all"


@router.patch("/me/interests", summary="Save user interest topics")
def save_interests(body: InterestsRequest, uid: str = Depends(get_required_user)):
    topics = [t.lower()[:50] for t in body.topics[:12]]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_interests (uid, topics, age_group)
                VALUES (%s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    topics = EXCLUDED.topics,
                    age_group = EXCLUDED.age_group,
                    last_updated = now()
                """,
                (uid, topics, body.age_group),
            )
    # Invalidate daily spark cache
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_sparks WHERE uid = %s", (uid,))
    return {"saved": True}


# ── COPPA parental consent confirmation (no auth) ─────────────────────────────

@router.get("/consent/confirm", summary="Confirm parental consent via email token")
def consent_confirm(token: str = Query(..., description="UUID token from consent email")):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid, expires_at, status FROM parental_consent WHERE token = %s",
                (token,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_token", "message": "This confirmation link is invalid."},
        )

    if row["status"] == "confirmed":
        return {"status": "already_confirmed", "message": "This account is already active."}

    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail={"error": "token_expired", "message": "This confirmation link has expired. Please ask your child to sign up again."},
        )

    uid = row["uid"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE parental_consent SET status = 'confirmed', confirmed_at = now() WHERE token = %s",
                (token,),
            )
            cur.execute(
                "UPDATE users SET account_status = 'active', consent_given_at = now() WHERE uid = %s",
                (uid,),
            )

    return {"status": "confirmed", "message": "Account approved. Your child can now log in to ECALT."}


# ── GDPR: consent record ──────────────────────────────────────────────────────

@router.get("/me/consent", summary="Get consent record (GDPR transparency)")
def get_consent(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT account_status, consent_given_at, consent_version, birth_year FROM users WHERE uid = %s",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    d = dict(row)
    if d.get("consent_given_at") and hasattr(d["consent_given_at"], "isoformat"):
        d["consent_given_at"] = d["consent_given_at"].isoformat()
    return d


# ── GDPR: data portability ────────────────────────────────────────────────────

@router.get("/me/export", summary="Export all personal data (GDPR Art. 20)")
def export_account(uid: str = Depends(get_required_user)):
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

    return JSONResponse(
        content={
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
        },
        headers={"Content-Disposition": "attachment; filename=ecalt-data-export.json"},
    )


# ── GDPR: right to erasure ────────────────────────────────────────────────────

@router.delete("/me", status_code=204, summary="Delete account and all personal data (GDPR Art. 17)")
def delete_account(uid: str = Depends(get_required_user)):
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
            cur.execute("DELETE FROM subscriptions WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM notification_preferences WHERE uid = %s", (uid,))
            cur.execute("DELETE FROM users WHERE uid = %s", (uid,))
            cur.execute(
                "INSERT INTO deletion_requests (uid, status, completed_at) VALUES (%s, 'completed', now())",
                (uid,),
            )
