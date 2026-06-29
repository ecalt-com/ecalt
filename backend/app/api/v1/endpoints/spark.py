import logging
import openai as _openai
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from app.models.schemas import SparkRequest, SparkResponse
from app.services.spark_service import consume_spark, generate_spark
from app.services.subscription_service import check_budget, record_usage, get_user_plan
from app.services.provider_service import get_config
from app.core.auth import get_optional_user
from app.core.limiter import limiter
from app.services.content_filter import check_topic_scope

router = APIRouter()
logger = logging.getLogger(__name__)


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

    Rate-limited to **5 sparks per session per hour**. Authenticated users
    are keyed by Firebase uid; guests are keyed by session_id.
    Authenticated users are also gated by their plan token budget.
    Returns `429` when the session limit is reached, `402` when budget is exhausted.
    """
    key = uid or body.session_id
    if not key:
        raise HTTPException(status_code=400, detail="session_id required for unauthenticated requests")

    topic_allowed, topic_reason = check_topic_scope(body.question)
    if not topic_allowed:
        raise HTTPException(status_code=422, detail=topic_reason)

    # Budget check for authenticated users — guests use session window only
    if uid:
        allowed, reason = check_budget(uid, context="ai")
        if not allowed:
            raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    # Session spark window is an anti-abuse guard for guests and free-trial users only.
    # Paid users are already gated by token budget; don't impose an artificial hourly cap.
    on_paid_plan = uid and get_user_plan(uid).get("plan_id") != "free_trial"

    if on_paid_plan:
        used, remaining = 0, -1  # -1 signals "unlimited" to the frontend
    else:
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
        answer, mission, in_tok, out_tok = await generate_spark(body.question.strip(), uid=uid)
    except ValueError as e:
        logger.error("spark parse error [%s]: %s", body.question[:80], e, exc_info=True)
        raise HTTPException(status_code=502, detail=str(e))
    except _openai.RateLimitError:
        logger.warning("openai quota exceeded for spark [%s]", body.question[:80])
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable. Please try again later.")
    except Exception as e:
        logger.error("spark generation failed [%s]: %s", body.question[:80], e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Spark generation failed: {e}")

    if uid:
        record_usage(uid, in_tok, out_tok, get_config("spark")["model"], interaction_type="spark")

    return SparkResponse(
        answer=answer,
        mission=mission,
        sparks_used=used,
        sparks_remaining=remaining,
    )
