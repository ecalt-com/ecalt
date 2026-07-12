import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from typing import Optional

from app.core.auth import get_active_user
from app.services.quiz_service import (
    generate_quiz,
    generate_quiz_set,
    get_hint,
    record_quiz_skip,
    step_quiz_status,
    submit_answer,
)
from app.services.subscription_service import check_budget, record_usage
from app.services.provider_service import get_config

router = APIRouter()
logger = logging.getLogger(__name__)


class QuizGenerateRequest(BaseModel):
    concept: str
    context: str           # conversation or step content excerpt
    base_depth: str = "exploratory"  # surface | exploratory | deep | research
    # Quiz-set fields — provide journey_id + step_id (and optionally
    # num_questions) to get a multi-question set that gates step completion.
    journey_id: Optional[str] = None
    step_id: Optional[str] = None
    num_questions: Optional[int] = None
    step_type: str = "concept"  # concept | practice | challenge | explore


class QuizSubmitRequest(BaseModel):
    user_answer: str = Field(..., min_length=1, max_length=2000)


@router.post("", summary="Generate a fingerprint-calibrated quiz (single question or step quiz set)")
async def generate_quiz_endpoint(
    body: QuizGenerateRequest,
    uid: str = Depends(get_active_user),
):
    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    if not body.concept.strip():
        raise HTTPException(status_code=400, detail="concept cannot be empty")
    if not body.context.strip():
        raise HTTPException(status_code=400, detail="context cannot be empty")

    is_set = bool(body.journey_id and body.step_id) or body.num_questions is not None

    try:
        if is_set:
            quiz, in_tok, out_tok = await generate_quiz_set(
                uid=uid,
                concept=body.concept.strip(),
                context=body.context.strip(),
                base_depth=body.base_depth,
                num_questions=body.num_questions or 3,
                journey_id=body.journey_id,
                step_id=body.step_id,
                step_type=body.step_type,
            )
        else:
            quiz, in_tok, out_tok = await generate_quiz(
                uid=uid,
                concept=body.concept.strip(),
                context=body.context.strip(),
                base_depth=body.base_depth,
            )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("quiz generation failed uid=%s concept=%s", uid, body.concept[:80])
        raise HTTPException(status_code=500, detail="Failed to generate quiz")

    cfg = get_config("quiz")
    record_usage(uid, in_tok, out_tok, cfg["model"], interaction_type="quiz")
    return quiz


@router.get(
    "/step-status/{journey_id}/{step_id}",
    summary="Whether the user has passed the quiz for a journey step",
)
async def step_status_endpoint(
    journey_id: str,
    step_id: str,
    uid: str = Depends(get_active_user),
):
    return step_quiz_status(uid, journey_id, step_id)


@router.post(
    "/step-skip/{journey_id}/{step_id}",
    summary="Skip the quiz for a journey step (opens the step's quiz gate)",
)
async def skip_step_quiz_endpoint(
    journey_id: str,
    step_id: str,
    uid: str = Depends(get_active_user),
):
    try:
        record_quiz_skip(uid, journey_id, step_id)
    except Exception:
        logger.exception("quiz skip failed uid=%s journey=%s step=%s", uid, journey_id, step_id)
        raise HTTPException(status_code=500, detail="Failed to skip quiz")
    return {"skipped": True, "journey_id": journey_id, "step_id": step_id}


@router.post("/{quiz_id}/hint", summary="Get the next progressive hint")
async def get_hint_endpoint(quiz_id: str, uid: str = Depends(get_active_user)):
    try:
        return get_hint(quiz_id, uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("get_hint failed quiz_id=%s uid=%s", quiz_id, uid)
        raise HTTPException(status_code=500, detail="Failed to retrieve hint")


@router.post("/{quiz_id}/submit", summary="Submit an answer and get feedback")
async def submit_answer_endpoint(
    quiz_id: str,
    body: QuizSubmitRequest,
    uid: str = Depends(get_active_user),
):
    if not body.user_answer.strip():
        raise HTTPException(status_code=400, detail="user_answer cannot be empty")
    try:
        return await submit_answer(quiz_id, uid, body.user_answer.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("submit_answer failed quiz_id=%s uid=%s", quiz_id, uid)
        raise HTTPException(status_code=500, detail="Failed to submit answer")
