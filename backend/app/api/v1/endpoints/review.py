"""Spaced review endpoints (F1.3)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.services.language_service import quiz_language, use_language
from app.core.auth import get_active_user
from app.services import review_service as svc
from app.services.learning_events_service import record_event
from app.services.quiz_service import submit_answer

router = APIRouter()
logger = logging.getLogger(__name__)


class ReviewAnswer(BaseModel):
    quiz_id: str
    user_answer: str = Field(..., min_length=1, max_length=2000)


@router.get("/today", summary="Items due for review today")
def review_today(limit: int = Query(svc.DEFAULT_LIMIT, ge=0, le=20), uid: str = Depends(get_active_user)):
    return svc.due_items(uid, limit)


@router.post("/{item_id}/start", summary="The question for one review item")
def review_start(item_id: str, uid: str = Depends(get_active_user)):
    question = svc.start_item(uid, item_id)
    if not question:
        raise HTTPException(status_code=404, detail={"error": "no_question", "message": "Nothing to review here."})
    return question


@router.post("/{item_id}/answer", summary="Answer a review question")
async def review_answer(item_id: str, body: ReviewAnswer, uid: str = Depends(get_active_user)):
    if not await run_in_threadpool(svc.quiz_belongs_to_item, uid, item_id, body.quiz_id):
        raise HTTPException(status_code=404, detail={"error": "no_question", "message": "That question isn't part of this review."})
    try:
        with use_language(await run_in_threadpool(quiz_language, body.quiz_id, uid)):
            graded = await submit_answer(body.quiz_id, uid, body.user_answer.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    schedule = await run_in_threadpool(svc.apply_result, uid, item_id, bool(graded["is_correct"]))
    if schedule is None:
        raise HTTPException(status_code=404, detail={"error": "no_question", "message": "Review item not found."})
    from app.api.v1.endpoints.progress import _update_streak
    await run_in_threadpool(_update_streak, uid)  # a finished review counts toward the streak
    record_event(uid, "review_answer", props={"correct": bool(graded["is_correct"]), "box": schedule["box"]})
    return {**graded, **schedule}
