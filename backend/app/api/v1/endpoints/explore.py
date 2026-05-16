from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import ExploreRequest, ExploreResponse
from app.services.ai_service import generate_journey
from app.core.auth import get_required_user

router = APIRouter()


@router.post(
    "",
    response_model=ExploreResponse,
    summary="Generate a learning journey",
    response_description="AI-generated Journey based on the submitted question",
)
async def explore(request: ExploreRequest, uid: str = Depends(get_required_user)):
    """
    Submit a curiosity question and receive a fully structured **Journey**.

    Claude (claude-sonnet-4-6) generates a title, description, difficulty,
    estimated duration, and an ordered list of learning steps tailored to
    the requested `age_group`.

    **Errors**
    - `400` — question is empty or blank
    - `502` — Claude API returned an unexpected response
    - `500` — unexpected server error
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        journey = await generate_journey(
            question=request.question.strip(),
            age_group=request.age_group or "all",
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate journey. Please try again.")

    return ExploreResponse(journey=journey)
