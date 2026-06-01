import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.auth import get_required_user
from app.services.quiz_service import generate_quiz, get_hint, submit_answer
from app.services.subscription_service import check_budget, record_usage
from app.services.provider_service import get_config

router = APIRouter()
logger = logging.getLogger(__name__)


class QuizGenerateRequest(BaseModel):
    concept: str
    context: str           # conversation or step content excerpt
    base_depth: str = "exploratory"  # surface | exploratory | deep | research


class QuizSubmitRequest(BaseModel):
    user_answer: str


@router.post("", summary="Generate a fingerprint-calibrated quiz question")
async def generate_quiz_endpoint(
    body: QuizGenerateRequest,
    uid: str = Depends(get_required_user),
):
    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    if not body.concept.strip():
        raise HTTPException(status_code=400, detail="concept cannot be empty")
    if not body.context.strip():
        raise HTTPException(status_code=400, detail="context cannot be empty")

    try:
        quiz = await generate_quiz(
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
    record_usage(uid, 0, 0, cfg["model"], interaction_type="quiz")
    return quiz


@router.post("/{quiz_id}/hint", summary="Get the next progressive hint")
async def get_hint_endpoint(quiz_id: str, uid: str = Depends(get_required_user)):
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
    uid: str = Depends(get_required_user),
):
    if not body.user_answer.strip():
        raise HTTPException(status_code=400, detail="user_answer cannot be empty")
    try:
        return submit_answer(quiz_id, uid, body.user_answer.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("submit_answer failed quiz_id=%s uid=%s", quiz_id, uid)
        raise HTTPException(status_code=500, detail="Failed to submit answer")
