from fastapi import APIRouter, Path
from app.models.schemas import SessionStatus
from app.services.spark_service import FREE_SPARK_LIMIT, get_session_status

router = APIRouter()


@router.get(
    "/{session_id}",
    response_model=SessionStatus,
    summary="Get session spark status",
    response_description="Current spark usage for the session — does not consume a spark.",
)
async def session_status(
    session_id: str = Path(..., min_length=1, max_length=128, description="Client session UUID"),
):
    """
    Returns how many free sparks a session has used and how many remain.

    Call this on page load with the stored `session_id` to restore the
    spark counter without consuming a spark. Returns `sparks_used: 0`
    for sessions that have never called the spark endpoint or whose
    60-minute window has expired.
    """
    used, remaining = get_session_status(session_id)
    return SessionStatus(
        session_id=session_id,
        sparks_used=used,
        sparks_remaining=remaining,
        limit=FREE_SPARK_LIMIT,
    )
