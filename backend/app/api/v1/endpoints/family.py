"""Family management (parental accounts plan, Phase 1).

Two ways a parent becomes linked to a child:
- Path A: the parent creates a managed child account here (POST /children) —
  consent is granted up front by the authenticated adult.
- Path B: a teen self-signed-up and named a parent email; the parent approves
  the request while signed in (POST /link-requests/{token}/approve), which both
  activates the child and creates the family link.

The anonymous POST /users/consent/confirm remains as a fallback until the
frontend consent page requires sign-in; it activates the child but creates no
link (no dashboard). Deprecate it in Phase 2.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import (
    get_active_user,
    get_required_user,
    invalidate_status_cache,
    verify_parent_of,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.jurisdiction import (
    ADULT_AGE,
    CONSENT_POLICY_VERSION,
    age_from_birth,
    is_hard_blocked,
    required_verification_tier,
)
from app.services.consent_service import (
    hash_ip,
    record_consent_event,
    schedule_email_plus_followup,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_adult_parent(uid: str) -> dict:
    """The caller must be an active adult account. Returns their users row."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid, email, display_name, age_group_flag, account_status, jurisdiction "
                "FROM users WHERE uid = %s",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail={
            "error": "no_account",
            "message": "Complete your own sign-up before managing a family.",
        })
    d = dict(row)
    if d.get("account_status") != "active" or d.get("age_group_flag") != "adult":
        raise HTTPException(status_code=403, detail={
            "error": "adult_account_required",
            "message": "Only an active adult account can manage a family.",
        })
    return d


# ── Path A: parent-created managed child ─────────────────────────────────────

class CreateChildRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    birth_year: int
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    email: str = Field(..., min_length=3, max_length=254,
                       description="Child's login email (can be a parent-managed alias)")
    password: str = Field(..., min_length=8, max_length=128)
    country: Optional[str] = Field(None, min_length=2, max_length=2)


@router.post("/children", status_code=201, summary="Create a managed child account")
async def create_child(body: CreateChildRequest, request: Request,
                       uid: str = Depends(get_active_user)):
    parent = _require_adult_parent(uid)

    if "@" not in body.email:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_email", "message": "Enter a valid email address for the child.",
        })

    age = age_from_birth(body.birth_year, body.birth_month)
    if age >= ADULT_AGE:
        raise HTTPException(status_code=400, detail={
            "error": "not_a_minor",
            "message": "Managed accounts are for children under 18. Adults sign up themselves.",
        })
    if age < 3:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_birth_year", "message": "Please check the birth year.",
        })
    if is_hard_blocked(age) and not settings.ENABLE_MANAGED_CHILDREN:
        raise HTTPException(status_code=403, detail={
            "error": "under_13_not_available",
            "message": "Accounts for children under 13 aren't available yet — they require "
                       "our verified-consent flow, which is coming soon.",
        })

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM family_links WHERE parent_uid = %s AND status = 'active'",
                (uid,),
            )
            row = cur.fetchone()
    if row and (row.get("n") or 0) >= settings.MAX_CHILDREN_PER_PARENT:
        raise HTTPException(status_code=400, detail={
            "error": "family_full",
            "message": f"A family supports up to {settings.MAX_CHILDREN_PER_PARENT} children.",
        })

    # The Firebase credential is the source of the child uid. Created first;
    # rolled back below if the DB write fails so no orphan credential remains.
    from app.services.firebase_admin import create_firebase_user, delete_firebase_user
    child_uid, err = await create_firebase_user(body.email, body.password, body.display_name)
    if not child_uid:
        if err == "EMAIL_EXISTS":
            raise HTTPException(status_code=409, detail={
                "error": "email_exists", "message": "An account with this email already exists.",
            })
        if err == "not_configured":
            raise HTTPException(status_code=503, detail={
                "error": "not_configured",
                "message": "Child account creation is temporarily unavailable.",
            })
        logger.error("firebase child creation failed for parent=%s: %s", uid, err)
        raise HTTPException(status_code=502, detail={
            "error": "credential_creation_failed",
            "message": "Could not create the child's login. Please try again.",
        })

    jurisdiction = (body.country.strip().upper() if body.country else None) or parent.get("jurisdiction")
    ip = hash_ip(request.client.host if request.client else None)
    age_group = "child" if is_hard_blocked(age) else "teen"
    chat_enabled = not is_hard_blocked(age)  # AI chat stays off for under-13s by default
    tier = required_verification_tier(jurisdiction, age)
    # 'card' tier: consent is recorded now, but the account activates only after
    # the parent completes card verification from the dashboard.
    account_status = "active" if tier == "email_plus" else "parental_consent_pending"

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (uid, email, display_name, birth_year, birth_month,
                                      jurisdiction, age_group_flag, account_status,
                                      consent_given_at, consent_version, role)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, 'learner')
                    """,
                    (child_uid, body.email, body.display_name, body.birth_year,
                     body.birth_month, jurisdiction, age_group, account_status,
                     CONSENT_POLICY_VERSION),
                )
                cur.execute(
                    "INSERT INTO family_links (parent_uid, child_uid) VALUES (%s, %s)",
                    (uid, child_uid),
                )
                cur.execute(
                    "INSERT INTO child_settings (child_uid, managed, chat_enabled, verification_tier) "
                    "VALUES (%s, true, %s, %s)",
                    (child_uid, chat_enabled, tier),
                )
                cur.execute("UPDATE users SET role = 'parent' WHERE uid = %s", (uid,))
                record_consent_event(
                    child_uid, "granted",
                    parent_uid=uid, parent_email=parent.get("email"),
                    method="parent_created", jurisdiction=jurisdiction,
                    ip_hash=ip, details={"age_at_creation": age}, cur=cur,
                )
                if tier == "email_plus":
                    schedule_email_plus_followup(
                        child_uid, uid, parent["email"], body.display_name, cur=cur,
                    )
    except HTTPException:
        raise
    except Exception:
        asyncio.ensure_future(delete_firebase_user(child_uid))
        logger.exception("child account DB write failed; rolling back credential %s", child_uid)
        raise HTTPException(status_code=500, detail={
            "error": "creation_failed", "message": "Could not create the account. Please try again.",
        })

    from app.services.email_service import send_child_account_created_email
    asyncio.ensure_future(
        send_child_account_created_email(parent["email"], body.display_name, body.email, uid)
    )

    return {
        "child_uid": child_uid,
        "display_name": body.display_name,
        "email": body.email,
        "age_group": age_group,
        "chat_enabled": chat_enabled,
        "managed": True,
        "verification_tier": tier,
        "verification_required": tier != "email_plus",
        "account_status": account_status,
    }


# ── Children list ─────────────────────────────────────────────────────────────

@router.get("/children", summary="List the caller's linked children")
def list_children(uid: str = Depends(get_active_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fl.child_uid, fl.created_at AS linked_at,
                       u.display_name, u.email, u.account_status, u.age_group_flag,
                       u.birth_year, u.birth_month, u.paused, u.streak_days,
                       cs.managed, cs.chat_enabled, cs.content_age_band,
                       cs.weekly_digest_enabled, cs.transcript_visibility,
                       cs.verification_tier, cs.verification_status, cs.verified_at
                  FROM family_links fl
                  JOIN users u ON u.uid = fl.child_uid
             LEFT JOIN child_settings cs ON cs.child_uid = fl.child_uid
                 WHERE fl.parent_uid = %s AND fl.status = 'active'
              ORDER BY fl.created_at
                """,
                (uid,),
            )
            rows = cur.fetchall()

    def _iso(v):
        return v.isoformat() if hasattr(v, "isoformat") else v

    return {"children": [{k: _iso(v) for k, v in dict(r).items()} for r in rows]}


# ── Path B: authenticated approval of a child-initiated consent request ──────

async def _decide_link_request(token: str, approved: bool, request: Request, uid: str) -> dict:
    # async so ensure_future (approval receipt email) has a running event loop.
    parent = _require_adult_parent(uid)

    from app.api.v1.endpoints.users import _load_consent_token
    row = _load_consent_token(token)
    if row["status"] == "confirmed":
        return {"status": "already_confirmed", "message": "This account is already active."}
    if row["status"] == "refused":
        return {"status": "refused", "message": "Consent was already declined for this account."}

    child_uid = row["uid"]
    if child_uid == uid:
        raise HTTPException(status_code=403, detail={
            "error": "self_approval", "message": "You cannot approve your own consent request.",
        })

    ip = hash_ip(request.client.host if request.client else None)
    jurisdiction = row.get("jurisdiction")

    if approved:
        # Jurisdiction tier: 'card' regions record consent + the link now, but
        # the child activates only after card verification from the dashboard.
        tier = "email_plus"
        if row.get("birth_year") is not None:
            child_age = age_from_birth(row["birth_year"], row.get("birth_month"))
            tier = required_verification_tier(jurisdiction, child_age)
        activate = tier == "email_plus"

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE parental_consent SET status = 'confirmed', confirmed_at = now() WHERE token = %s",
                    (token,),
                )
                if activate:
                    cur.execute(
                        "UPDATE users SET account_status = 'active', consent_given_at = now(), consent_version = %s WHERE uid = %s",
                        (CONSENT_POLICY_VERSION, child_uid),
                    )
                else:
                    cur.execute(
                        "UPDATE users SET consent_given_at = now(), consent_version = %s WHERE uid = %s",
                        (CONSENT_POLICY_VERSION, child_uid),
                    )
                cur.execute(
                    """
                    INSERT INTO family_links (parent_uid, child_uid) VALUES (%s, %s)
                    ON CONFLICT (child_uid) WHERE status = 'active' DO NOTHING
                    """,
                    (uid, child_uid),
                )
                cur.execute(
                    "INSERT INTO child_settings (child_uid, managed, verification_tier) VALUES (%s, false, %s) "
                    "ON CONFLICT (child_uid) DO UPDATE SET verification_tier = EXCLUDED.verification_tier",
                    (child_uid, tier),
                )
                cur.execute("UPDATE users SET role = 'parent' WHERE uid = %s", (uid,))
                record_consent_event(
                    child_uid, "granted",
                    parent_uid=uid, parent_email=parent.get("email"),
                    method="email_link_authenticated",
                    jurisdiction=jurisdiction,
                    ip_hash=ip,
                    details={"consent_request_email": row.get("parent_email")},
                    cur=cur,
                )
                if activate:
                    schedule_email_plus_followup(
                        child_uid, uid, parent["email"], row.get("display_name"), cur=cur,
                    )
        invalidate_status_cache(child_uid)

        if not activate:
            return {
                "status": "verification_required",
                "child_uid": child_uid,
                "child_name": row.get("display_name"),
                "verification_tier": tier,
                "message": "Consent recorded. Complete card verification from your "
                           "Family dashboard to activate the account.",
            }

        from app.services.email_service import send_link_approved_email
        asyncio.ensure_future(
            send_link_approved_email(parent["email"], row.get("display_name") or "your child", uid)
        )
        return {
            "status": "confirmed",
            "child_uid": child_uid,
            "child_name": row.get("display_name"),
            "message": "Account approved and linked to your family.",
        }

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE parental_consent SET status = 'refused' WHERE token = %s",
                (token,),
            )
            record_consent_event(
                child_uid, "refused",
                parent_uid=uid, parent_email=parent.get("email"),
                method="email_link_authenticated",
                jurisdiction=jurisdiction,
                ip_hash=ip,
                details={"consent_request_email": row.get("parent_email")},
                cur=cur,
            )
    return {"status": "refused", "message": "Understood — the account will not be activated."}


@router.post("/link-requests/{token}/approve", summary="Approve a child's consent request (authenticated)")
async def approve_link_request(token: str, request: Request, uid: str = Depends(get_active_user)):
    return await _decide_link_request(token, True, request, uid)


@router.post("/link-requests/{token}/decline", summary="Decline a child's consent request (authenticated)")
async def decline_link_request(token: str, request: Request, uid: str = Depends(get_active_user)):
    return await _decide_link_request(token, False, request, uid)


# ── Card micro-verification (Stripe SetupIntent via hosted Checkout) ─────────
# A successful card setup is the adult signal — nothing is charged and no
# payment method is retained (no Stripe customer is attached to the session).

@router.post("/children/{child_uid}/verify/card", summary="Start card verification for a child")
def start_card_verification(child_uid: str, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail={
            "error": "not_configured", "message": "Card verification is temporarily unavailable.",
        })

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            mode="setup",
            payment_method_types=["card"],
            client_reference_id=uid,
            metadata={"purpose": "consent_verification", "child_uid": child_uid},
            success_url=f"{settings.FRONTEND_URL}/family?verify_session={{CHECKOUT_SESSION_ID}}&child={child_uid}",
            cancel_url=f"{settings.FRONTEND_URL}/family",
        )
    except Exception as e:
        logger.error("card verification session failed parent=%s child=%s: %s", uid, child_uid, e)
        raise HTTPException(status_code=502, detail={
            "error": "stripe_error", "message": "Could not start verification. Please try again.",
        })

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE child_settings SET verification_status = 'pending' WHERE child_uid = %s",
                (child_uid,),
            )
    return {"checkout_url": session.url}


class CardVerifyConfirmRequest(BaseModel):
    session_id: str


@router.post("/children/{child_uid}/verify/card/confirm", summary="Confirm card verification after redirect")
def confirm_card_verification(child_uid: str, body: CardVerifyConfirmRequest,
                              request: Request, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    parent = _require_adult_parent(uid)
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail={
            "error": "not_configured", "message": "Card verification is temporarily unavailable.",
        })

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(body.session_id)
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_session", "message": "Verification session not found.",
        })

    if (session.client_reference_id != uid
            or (session.metadata or {}).get("child_uid") != child_uid
            or (session.metadata or {}).get("purpose") != "consent_verification"):
        raise HTTPException(status_code=403, detail={
            "error": "session_mismatch", "message": "This verification session is not yours.",
        })
    if session.status != "complete":
        raise HTTPException(status_code=400, detail={
            "error": "verification_incomplete", "message": "Verification was not completed.",
        })

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT jurisdiction FROM users WHERE uid = %s", (child_uid,))
            jrow = cur.fetchone()
            cur.execute(
                "UPDATE child_settings SET verification_status = 'verified', verified_at = now() WHERE child_uid = %s",
                (child_uid,),
            )
            cur.execute(
                "UPDATE users SET account_status = 'active', "
                "consent_given_at = COALESCE(consent_given_at, now()), consent_version = %s "
                "WHERE uid = %s",
                (CONSENT_POLICY_VERSION, child_uid),
            )
            record_consent_event(
                child_uid, "verified",
                parent_uid=uid, parent_email=parent.get("email"),
                method="card",
                jurisdiction=dict(jrow).get("jurisdiction") if jrow else None,
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"stripe_session": body.session_id},
                cur=cur,
            )
    invalidate_status_cache(child_uid)
    return {"status": "verified", "child_uid": child_uid,
            "message": "Verification complete — the account is now active."}


# ── Parent dashboard: per-child visibility (Phase 3) ─────────────────────────

def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _rows(cur):
    return [{k: _iso(v) for k, v in dict(r).items()} for r in cur.fetchall()]


def _transcripts_allowed(child_row: dict, settings_row: Optional[dict]) -> bool:
    """Full transcripts: managed under-13s (COPPA parental review right) or an
    explicit family setting. Teens keep summary-level privacy by default —
    whatever this returns is also disclosed to the child (see /my-family)."""
    s = settings_row or {}
    if s.get("transcript_visibility") == "full":
        return True
    return bool(s.get("managed")) and child_row.get("age_group_flag") == "child"


@router.get("/children/{child_uid}/overview", summary="Learning overview for a child")
def child_overview(child_uid: str, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT display_name, streak_days, last_active_date, created_at, "
                "account_status, age_group_flag, paused FROM users WHERE uid = %s",
                (child_uid,),
            )
            child = cur.fetchone()
            if not child:
                raise HTTPException(status_code=404, detail="Child account not found")

            cur.execute(
                """
                SELECT j.id, j.title, j.icon, j.created_at,
                       jsonb_array_length(j.steps) AS total_steps,
                       count(up.id)                AS completed_steps,
                       max(up.completed_at)        AS last_progress_at
                  FROM journeys j
             LEFT JOIN user_progress up ON up.journey_id = j.id AND up.uid = j.uid
                 WHERE j.uid = %s
              GROUP BY j.id
              ORDER BY GREATEST(coalesce(max(up.completed_at), j.created_at), j.created_at) DESC
                 LIMIT 10
                """,
                (child_uid,),
            )
            journeys = _rows(cur)

            cur.execute(
                "SELECT domain, mastery_level, concept_count FROM domain_mastery "
                "WHERE uid = %s ORDER BY mastery_level DESC LIMIT 8",
                (child_uid,),
            )
            domains = _rows(cur)

            cur.execute(
                """
                SELECT count(*)                                                    AS total,
                       count(*) FILTER (WHERE is_correct)                          AS correct,
                       count(*) FILTER (WHERE answered_at >= now() - interval '7 days') AS last_7_days
                  FROM quiz_results WHERE uid = %s AND NOT skipped
                """,
                (child_uid,),
            )
            quiz = dict(cur.fetchone() or {})

            cur.execute(
                "SELECT count(*) AS journeys, "
                "(SELECT count(*) FROM user_progress WHERE uid = %s)   AS steps_completed, "
                "(SELECT count(*) FROM knowledge_nodes WHERE uid = %s) AS knowledge_nodes, "
                "(SELECT count(*) FROM conversations WHERE uid = %s)   AS conversations "
                "FROM journeys WHERE uid = %s",
                (child_uid, child_uid, child_uid, child_uid),
            )
            totals = dict(cur.fetchone() or {})

    return {
        "child": {k: _iso(v) for k, v in dict(child).items()},
        "totals": totals,
        "quiz": quiz,
        "top_domains": domains,
        "recent_journeys": journeys,
    }


@router.get("/children/{child_uid}/activity", summary="Recent activity timeline for a child")
def child_activity(child_uid: str, days: int = Query(30, ge=1, le=90),
                   uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT age_group_flag FROM users WHERE uid = %s", (child_uid,),
            )
            child = cur.fetchone()
            if not child:
                raise HTTPException(status_code=404, detail="Child account not found")
            cur.execute(
                "SELECT managed, transcript_visibility FROM child_settings WHERE child_uid = %s",
                (child_uid,),
            )
            settings_row = cur.fetchone()

            cur.execute(
                """
                SELECT up.completed_at, up.step_id, j.id AS journey_id, j.title AS journey_title
                  FROM user_progress up
                  JOIN journeys j ON j.id = up.journey_id
                 WHERE up.uid = %s AND up.completed_at >= now() - make_interval(days => %s)
              ORDER BY up.completed_at DESC LIMIT 100
                """,
                (child_uid, days),
            )
            steps = _rows(cur)

            cur.execute(
                "SELECT id, title, question, created_at FROM journeys "
                "WHERE uid = %s AND created_at >= now() - make_interval(days => %s) "
                "ORDER BY created_at DESC LIMIT 50",
                (child_uid, days),
            )
            new_journeys = _rows(cur)

            cur.execute(
                "SELECT concept, is_correct, difficulty, answered_at FROM quiz_results "
                "WHERE uid = %s AND NOT skipped AND answered_at >= now() - make_interval(days => %s) "
                "ORDER BY answered_at DESC LIMIT 100",
                (child_uid, days),
            )
            quizzes = _rows(cur)

            # Conversation titles only — transcripts are gated separately and the
            # gate is disclosed to the child.
            cur.execute(
                """
                SELECT c.id, c.title, c.started_at, c.last_active,
                       (SELECT count(*) FROM conversation_messages cm
                         WHERE cm.conversation_id = c.id) AS message_count
                  FROM conversations c
                 WHERE c.uid = %s AND c.last_active >= now() - make_interval(days => %s)
              ORDER BY c.last_active DESC LIMIT 50
                """,
                (child_uid, days),
            )
            conversations = _rows(cur)

    return {
        "days": days,
        "steps_completed": steps,
        "journeys_started": new_journeys,
        "quiz_answers": quizzes,
        "conversations": conversations,
        "transcripts_available": _transcripts_allowed(dict(child), dict(settings_row) if settings_row else None),
    }


@router.get("/children/{child_uid}/conversations/{conversation_id}",
            summary="Full conversation transcript (gated)")
def child_conversation_transcript(child_uid: str, conversation_id: str,
                                  uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT age_group_flag FROM users WHERE uid = %s", (child_uid,),
            )
            child = cur.fetchone()
            cur.execute(
                "SELECT managed, transcript_visibility FROM child_settings WHERE child_uid = %s",
                (child_uid,),
            )
            settings_row = cur.fetchone()
            if not child or not _transcripts_allowed(dict(child), dict(settings_row) if settings_row else None):
                raise HTTPException(status_code=403, detail={
                    "error": "transcripts_not_enabled",
                    "message": "Transcript access isn't enabled for this account. "
                               "Teens see conversation topics only, unless the family setting allows more.",
                })
            cur.execute(
                "SELECT id, title, started_at FROM conversations WHERE id = %s AND uid = %s",
                (conversation_id, child_uid),
            )
            conv = cur.fetchone()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            cur.execute(
                "SELECT role, content, created_at FROM conversation_messages "
                "WHERE conversation_id = %s ORDER BY id",
                (conversation_id,),
            )
            messages = _rows(cur)
    return {**{k: _iso(v) for k, v in dict(conv).items()}, "messages": messages}


# ── Teen transparency: what the child's parent can see (child-facing) ────────

@router.get("/my-family", summary="The caller's family link, as seen by the child")
def my_family(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fl.parent_uid, u_p.display_name AS parent_name,
                       u_c.age_group_flag,
                       cs.managed, cs.transcript_visibility
                  FROM family_links fl
                  JOIN users u_p ON u_p.uid = fl.parent_uid
                  JOIN users u_c ON u_c.uid = fl.child_uid
             LEFT JOIN child_settings cs ON cs.child_uid = fl.child_uid
                 WHERE fl.child_uid = %s AND fl.status = 'active'
                """,
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        return {"linked": False}
    d = dict(row)
    transcripts = _transcripts_allowed(d, d)
    return {
        "linked": True,
        "parent_name": d.get("parent_name"),
        "managed": bool(d.get("managed")),
        "parent_can_see": {
            "topics_and_journeys": True,
            "progress_and_streaks": True,
            "quiz_scores": True,
            "conversation_titles": True,
            "full_conversations": transcripts,
        },
    }


# ── Consent record (parent transparency) ──────────────────────────────────────

@router.get("/children/{child_uid}/consent", summary="Full consent record for a child")
def child_consent_record(child_uid: str, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)

    def _iso(v):
        return v.isoformat() if hasattr(v, "isoformat") else v

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT account_status, consent_given_at, consent_version, jurisdiction "
                "FROM users WHERE uid = %s",
                (child_uid,),
            )
            user_row = cur.fetchone()
            cur.execute(
                "SELECT verification_tier, verification_status, verified_at "
                "FROM child_settings WHERE child_uid = %s",
                (child_uid,),
            )
            settings_row = cur.fetchone()
            cur.execute(
                "SELECT action, method, policy_version, jurisdiction, created_at "
                "FROM consent_events WHERE uid = %s ORDER BY created_at",
                (child_uid,),
            )
            events = cur.fetchall()

    return {
        "consent": {k: _iso(v) for k, v in dict(user_row).items()} if user_row else {},
        "verification": {k: _iso(v) for k, v in dict(settings_row).items()} if settings_row else {},
        "current_policy_version": CONSENT_POLICY_VERSION,
        "events": [{k: _iso(v) for k, v in dict(e).items()} for e in events],
    }


# ── Parental controls (Phase 4) ───────────────────────────────────────────────

class ChildSettingsPatch(BaseModel):
    paused: Optional[bool] = None
    chat_enabled: Optional[bool] = None
    content_age_band: Optional[str] = Field(None, pattern="^(kids|teens|adults|all)$")
    transcript_visibility: Optional[str] = Field(None, pattern="^(summaries|full)$")
    weekly_digest_enabled: Optional[bool] = None


@router.patch("/children/{child_uid}/settings", summary="Update a child's parental controls")
def update_child_settings(child_uid: str, body: ChildSettingsPatch,
                          uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail={
            "error": "no_changes", "message": "Nothing to update.",
        })

    paused = fields.pop("paused", None)
    with get_db() as conn:
        with conn.cursor() as cur:
            if paused is not None:
                cur.execute("UPDATE users SET paused = %s WHERE uid = %s", (paused, child_uid))
            if fields:
                cols = ", ".join(f"{k} = %({k})s" for k in fields)
                cur.execute(
                    f"""
                    INSERT INTO child_settings (child_uid, {', '.join(fields)})
                    VALUES (%(child_uid)s, {', '.join(f'%({k})s' for k in fields)})
                    ON CONFLICT (child_uid) DO UPDATE SET {cols}, updated_at = now()
                    """,
                    {"child_uid": child_uid, **fields},
                )
            cur.execute(
                """
                SELECT u.paused, cs.chat_enabled, cs.content_age_band,
                       cs.transcript_visibility, cs.weekly_digest_enabled
                  FROM users u
             LEFT JOIN child_settings cs ON cs.child_uid = u.uid
                 WHERE u.uid = %s
                """,
                (child_uid,),
            )
            row = cur.fetchone()
    if paused is not None:
        invalidate_status_cache(child_uid)
    return {"child_uid": child_uid, "settings": dict(row) if row else {}}


# ── Consent revocation: pause now, delete after a 14-day grace window ─────────

REVOCATION_GRACE_DAYS = 14


@router.post("/children/{child_uid}/revoke-consent", summary="Withdraw consent (pauses now, deletes in 14 days)")
async def revoke_consent(child_uid: str, request: Request, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    parent = _require_adult_parent(uid)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM deletion_requests WHERE uid = %s AND status = 'scheduled'",
                (child_uid,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "already_scheduled",
                    "message": "Consent is already withdrawn and deletion is scheduled.",
                })
            cur.execute("SELECT display_name, jurisdiction FROM users WHERE uid = %s", (child_uid,))
            child = cur.fetchone()
            if not child:
                raise HTTPException(status_code=404, detail="Child account not found")
            cur.execute("UPDATE users SET paused = true WHERE uid = %s", (child_uid,))
            cur.execute(
                "INSERT INTO deletion_requests (uid, status) VALUES (%s, 'scheduled')",
                (child_uid,),
            )
            record_consent_event(
                child_uid, "revoked",
                parent_uid=uid, parent_email=parent.get("email"),
                method="parent_dashboard",
                jurisdiction=dict(child).get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"grace_days": REVOCATION_GRACE_DAYS}, cur=cur,
            )
    invalidate_status_cache(child_uid)

    from app.services.email_service import send_revocation_scheduled_email
    asyncio.ensure_future(send_revocation_scheduled_email(
        parent["email"], dict(child).get("display_name") or "your child",
        REVOCATION_GRACE_DAYS, uid,
    ))
    return {
        "status": "revoked",
        "message": f"The account is paused now and will be permanently deleted in "
                   f"{REVOCATION_GRACE_DAYS} days. You can undo this from the dashboard.",
    }


@router.post("/children/{child_uid}/revoke-consent/cancel", summary="Undo a pending consent revocation")
def cancel_revocation(child_uid: str, request: Request, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    parent = _require_adult_parent(uid)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM deletion_requests WHERE uid = %s AND status = 'scheduled' RETURNING id",
                (child_uid,),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail={
                    "error": "nothing_scheduled",
                    "message": "There is no pending deletion for this account.",
                })
            cur.execute("SELECT jurisdiction FROM users WHERE uid = %s", (child_uid,))
            jrow = cur.fetchone()
            cur.execute("UPDATE users SET paused = false WHERE uid = %s", (child_uid,))
            record_consent_event(
                child_uid, "reconsent",
                parent_uid=uid, parent_email=parent.get("email"),
                method="parent_dashboard",
                jurisdiction=dict(jrow).get("jurisdiction") if jrow else None,
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"trigger": "revocation_cancelled"}, cur=cur,
            )
    invalidate_status_cache(child_uid)
    return {"status": "restored", "message": "Deletion cancelled — the account is active again."}


# ── Re-consent for a child after a policy-version bump (Phase 5) ─────────────

@router.post("/children/{child_uid}/reconsent", summary="Re-accept the current policy for a child")
def child_reconsent(child_uid: str, request: Request, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    parent = _require_adult_parent(uid)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consent_version, jurisdiction FROM users WHERE uid = %s", (child_uid,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Child account not found")
            if row.get("consent_version") == CONSENT_POLICY_VERSION:
                return {"status": "current", "policy_version": CONSENT_POLICY_VERSION}
            cur.execute(
                "UPDATE users SET consent_version = %s, consent_given_at = now() WHERE uid = %s",
                (CONSENT_POLICY_VERSION, child_uid),
            )
            record_consent_event(
                child_uid, "reconsent",
                parent_uid=uid, parent_email=parent.get("email"),
                method="parent_dashboard",
                jurisdiction=row.get("jurisdiction"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                details={"from_version": row.get("consent_version")}, cur=cur,
            )
    return {"status": "reconsented", "policy_version": CONSENT_POLICY_VERSION,
            "note": "If the account was paused for a lapsed re-consent, unpause it from settings."}


# ── Child data export (COPPA parental review right) ───────────────────────────

@router.get("/children/{child_uid}/export", summary="Export all of a child's personal data")
def export_child(child_uid: str, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    from fastapi.responses import JSONResponse
    from app.services.account_service import build_user_export
    return JSONResponse(
        content=build_user_export(child_uid),
        headers={"Content-Disposition": "attachment; filename=ecalt-child-data-export.json"},
    )


# ── Child deletion (COPPA parental deletion right) ────────────────────────────

@router.delete("/children/{child_uid}", status_code=204, summary="Delete a child's account and all data")
async def delete_child(child_uid: str, request: Request, uid: str = Depends(get_active_user)):
    verify_parent_of(uid, child_uid)
    parent = _require_adult_parent(uid)

    # Record the revocation while the uid is still live; the cascade below
    # pseudonymizes it along with the rest of the child's consent history.
    record_consent_event(
        child_uid, "revoked",
        parent_uid=uid, parent_email=parent.get("email"),
        method="parent_dashboard",
        ip_hash=hash_ip(request.client.host if request.client else None),
        details={"trigger": "parent_deleted_child"},
    )

    from app.services.account_service import delete_user_account
    delete_user_account(child_uid)

    from app.services.firebase_admin import delete_firebase_user
    await delete_firebase_user(child_uid)
    invalidate_status_cache(child_uid)
