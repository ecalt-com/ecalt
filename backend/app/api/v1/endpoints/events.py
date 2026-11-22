"""Learning funnel events from the browser (F1.2)."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.core.auth import get_optional_acting_uid
from app.core.limiter import limiter
from app.services.learning_events_service import MAX_BATCH, record_events

router = APIRouter()


class LearningEvent(BaseModel):
    event: str = Field(..., max_length=40)
    journey_id: Optional[str] = Field(None, max_length=100)
    step_id: Optional[str] = Field(None, max_length=100)
    props: Optional[dict[str, Any]] = None


class EventBatch(BaseModel):
    events: list[LearningEvent] = Field(..., max_length=MAX_BATCH)


@router.post("", status_code=204, summary="Record a batch of learning events")
@limiter.limit("60/minute")
def post_events(request: Request, body: EventBatch,
                uid: Optional[str] = Depends(get_optional_acting_uid)):
    """Unknown event names, oversized props, guests and school students are dropped
    silently — telemetry must never break the page."""
    record_events(uid, [e.model_dump() for e in body.events])
    return Response(status_code=204)
