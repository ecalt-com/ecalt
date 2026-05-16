from fastapi import APIRouter, HTTPException
from app.models.schemas import SparkRequest, SparkResponse
from app.services.spark_service import consume_spark, generate_spark

router = APIRouter()


@router.post(
    "/",
    response_model=SparkResponse,
    summary="Ask a curiosity question (free spark)",
    response_description="Short AI answer + proposed mission. Max 5 per session.",
)
async def spark(request: SparkRequest):
    """
    The free-tier curiosity engine.

    Uses **Claude Haiku** (minimal cost) to return a 2-3 sentence answer
    and a proposed 4-5 step learning mission.

    Rate-limited to **5 sparks per session per hour**. Returns `429` when the
    limit is reached — prompt the user to enroll for unlimited access.
    """
    allowed, used, remaining = consume_spark(request.session_id)

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
        answer, mission = await generate_spark(request.question.strip())
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
