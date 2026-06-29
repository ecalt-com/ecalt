import json
import logging
import openai as _openai
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from app.models.schemas import ExploreRequest, ExploreResponse, Journey, JourneyStep
from app.services.ai_service import generate_journey, warm_journey_steps, _build_learning_context
from app.core.auth import get_required_user
from app.core.database import get_db
from app.services.subscription_service import check_budget, record_usage
from app.services.provider_service import get_config
from app.services.interest_profile_service import invalidate as invalidate_profile
from app.services.content_filter import check_topic_scope

router = APIRouter()
logger = logging.getLogger(__name__)


def _invalidate_recommendation_cache(uid: str) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM journey_recommendations WHERE uid = %s", (uid,))
    except Exception:
        logger.debug("explore: recommendation cache invalidation failed (non-fatal)")


def _get_learner_profile(uid: str, request: ExploreRequest) -> dict | None:
    profile: dict = {}
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT profession FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                if row and row.get("profession"):
                    profile["profession"] = row["profession"]
    except Exception:
        pass
    if request.learner_purpose:
        profile["purpose"] = request.learner_purpose
    if request.topic_expertise:
        profile["topic_expertise"] = request.topic_expertise
    return profile or None


# ── Preview: generate + cache, do NOT persist to journeys ────────────────────

@router.post(
    "/preview",
    summary="Generate a journey preview (not persisted)",
    response_description="Preview token + AI-generated Journey",
)
async def explore_preview(
    request: ExploreRequest,
    uid: str = Depends(get_required_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    topic_allowed, topic_reason = check_topic_scope(request.question)
    if not topic_allowed:
        raise HTTPException(status_code=422, detail=topic_reason)

    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    learner_profile  = _get_learner_profile(uid, request)
    learning_context = _build_learning_context(uid)

    try:
        journey, in_tok, out_tok = await generate_journey(
            question=request.question.strip(),
            age_group=request.age_group or "all",
            uid=uid,
            learner_profile=learner_profile,
            learning_context=learning_context or None,
            refinement_context=request.refinement_context or None,
        )
    except ValueError as e:
        logger.warning("explore preview upstream error", extra={"question": request.question[:120], "error": str(e)})
        raise HTTPException(status_code=502, detail=str(e))
    except _openai.RateLimitError:
        logger.warning("openai quota exceeded for explore preview", extra={"question": request.question[:120]})
        raise HTTPException(status_code=402, detail={"error": "quota_exceeded", "upgrade_url": "/pricing"})
    except Exception:
        logger.exception("explore preview generation failed", extra={"question": request.question[:120]})
        raise HTTPException(status_code=500, detail="Failed to generate journey. Please try again.")

    record_usage(uid, in_tok, out_tok, get_config("journey")["model"], interaction_type="journey")

    # Clean up expired previews (lightweight, no worker needed)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM journey_previews WHERE expires_at < now()")
    except Exception:
        pass

    journey_json = json.dumps({
        "id":               journey.id,
        "question":         journey.question,
        "title":            journey.title,
        "description":      journey.description,
        "age_group":        journey.age_group,
        "difficulty":       journey.difficulty,
        "estimated_hours":  journey.estimated_hours,
        "icon":             journey.icon,
        "tags":             journey.tags,
        "steps":            [s.model_dump() for s in journey.steps],
        "created_at":       journey.created_at,
        "learner_purpose":  request.learner_purpose,
        "topic_expertise":  request.topic_expertise,
    })

    preview_token = None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journey_previews (uid, question, journey_json, age_group)
                    VALUES (%s, %s, %s::jsonb, %s)
                    RETURNING preview_token
                    """,
                    (uid, journey.question, journey_json, journey.age_group),
                )
                preview_token = str(cur.fetchone()["preview_token"])
    except Exception:
        logger.exception("failed to store journey preview")
        raise HTTPException(status_code=500, detail="Preview storage failed")

    return {"preview_token": preview_token, "journey": journey}


# ── Confirm: read cache, persist to journeys, warm steps ─────────────────────

class ConfirmRequest(BaseModel):
    preview_token: str


@router.post(
    "/confirm",
    response_model=ExploreResponse,
    summary="Confirm a previewed journey and persist it",
)
async def explore_confirm(
    request: ConfirmRequest,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_required_user),
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT journey_json, question, age_group
                    FROM journey_previews
                    WHERE preview_token = %s::uuid AND uid = %s AND expires_at > now()
                    """,
                    (request.preview_token, uid),
                )
                row = cur.fetchone()
    except Exception:
        logger.exception("journey confirm db fetch failed")
        raise HTTPException(status_code=500, detail="Confirm failed")

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Preview not found or expired. Please generate a new journey.",
        )

    data      = row["journey_json"] if isinstance(row["journey_json"], dict) else json.loads(row["journey_json"])
    age_group = row["age_group"]

    steps = [
        JourneyStep(
            id=s["id"],
            title=s["title"],
            description=s["description"],
            type=s["type"],
            estimated_minutes=int(s["estimated_minutes"]),
        )
        for s in data["steps"]
    ]
    journey = Journey(
        id=data["id"],
        question=data["question"],
        title=data["title"],
        description=data["description"],
        age_group=data["age_group"],
        difficulty=data["difficulty"],
        estimated_hours=float(data["estimated_hours"]),
        steps=steps,
        tags=data.get("tags", []),
        icon=data.get("icon", "📚"),
        created_at=data["created_at"],
    )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journeys
                        (id, uid, question, title, description, age_group, difficulty,
                         estimated_hours, steps, tags, icon, is_curated,
                         learner_purpose, topic_expertise)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, FALSE, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        journey.id, uid, journey.question, journey.title,
                        journey.description, journey.age_group, journey.difficulty,
                        journey.estimated_hours,
                        json.dumps([s.model_dump() for s in journey.steps]),
                        journey.tags, journey.icon,
                        data.get("learner_purpose"),
                        data.get("topic_expertise"),
                    ),
                )
                # Delete the used preview token
                cur.execute(
                    "DELETE FROM journey_previews WHERE preview_token = %s::uuid",
                    (request.preview_token,),
                )
    except Exception:
        logger.exception("failed to persist confirmed journey")
        raise HTTPException(status_code=500, detail="Failed to save journey")

    invalidate_profile(uid)
    _invalidate_recommendation_cache(uid)

    background_tasks.add_task(
        warm_journey_steps,
        journey.id,
        journey.steps,
        journey.title,
        journey.question,
        age_group,
        uid,
    )

    return ExploreResponse(journey=journey)


# ── Legacy: direct generate + persist (kept for backwards compat) ─────────────

@router.post(
    "",
    response_model=ExploreResponse,
    summary="Generate a learning journey (legacy — use /preview + /confirm)",
    response_description="AI-generated Journey based on the submitted question",
)
async def explore(
    request: ExploreRequest,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_required_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    topic_allowed, topic_reason = check_topic_scope(request.question)
    if not topic_allowed:
        raise HTTPException(status_code=422, detail=topic_reason)

    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    learner_profile  = _get_learner_profile(uid, request)
    learning_context = _build_learning_context(uid)

    try:
        journey, in_tok, out_tok = await generate_journey(
            question=request.question.strip(),
            age_group=request.age_group or "all",
            uid=uid,
            learner_profile=learner_profile,
            learning_context=learning_context or None,
            refinement_context=request.refinement_context or None,
        )
    except ValueError as e:
        logger.warning("explore upstream error", extra={"question": request.question[:120], "error": str(e)})
        raise HTTPException(status_code=502, detail=str(e))
    except _openai.RateLimitError:
        logger.warning("openai quota exceeded for explore", extra={"question": request.question[:120]})
        raise HTTPException(status_code=402, detail={"error": "quota_exceeded", "upgrade_url": "/pricing"})
    except Exception:
        logger.exception("explore generation failed", extra={"question": request.question[:120]})
        raise HTTPException(status_code=500, detail="Failed to generate journey. Please try again.")

    record_usage(uid, in_tok, out_tok, get_config("journey")["model"], interaction_type="journey")
    invalidate_profile(uid)
    _invalidate_recommendation_cache(uid)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journeys
                        (id, uid, question, title, description, age_group, difficulty,
                         estimated_hours, steps, tags, icon, is_curated,
                         learner_purpose, topic_expertise)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, FALSE, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        journey.id, uid, journey.question, journey.title,
                        journey.description, journey.age_group, journey.difficulty,
                        journey.estimated_hours,
                        json.dumps([s.model_dump() for s in journey.steps]),
                        journey.tags, journey.icon,
                        request.learner_purpose,
                        request.topic_expertise,
                    ),
                )
    except Exception:
        logger.exception("failed to persist journey to db", extra={"journey_id": journey.id})

    background_tasks.add_task(
        warm_journey_steps,
        journey.id,
        journey.steps,
        journey.title,
        journey.question,
        journey.age_group,
        uid,
    )

    return ExploreResponse(journey=journey)
