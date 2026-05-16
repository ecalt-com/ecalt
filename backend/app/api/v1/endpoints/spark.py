from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from app.models.schemas import SparkRequest, SparkResponse
from app.services.spark_service import consume_spark, generate_spark
from app.core.auth import get_optional_user
from app.core.limiter import limiter

router = APIRouter()


@router.post(
    "",
    response_model=SparkResponse,
    summary="Ask a curiosity question (free spark)",
    response_description="Short AI answer + proposed mission. Max 5 per session.",
)
@limiter.limit("30/minute")
async def spark(request: Request, body: SparkRequest, uid: Optional[str] = Depends(get_optional_user)):
    """
    The free-tier curiosity engine.

    Uses **Claude Haiku** (minimal cost) to return a 2-3 sentence answer
    and a proposed 4-5 step learning mission.

    Rate-limited to **5 sparks per session per hour**. Authenticated users
    are keyed by Firebase uid; guests are keyed by session_id.
    Returns `429` when the limit is reached.
    """
    key = uid or body.session_id
    if not key:
        raise HTTPException(status_code=400, detail="session_id required for unauthenticated requests")

    allowed, used, remaining = consume_spark(key)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "You've used all 5 free sparks for this session.",
                "sparks_used": used,
                "sparks_remaining": 0,
                "action": "enroll",
            },
        )

    try:
        answer, mission = await generate_spark(body.question.strip())
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Spark generation failed — please try again.")

    return SparkResponse(
        answer=answer,
        mission=mission,
        sparks_used=used,
        sparks_remaining=remaining,
    )
