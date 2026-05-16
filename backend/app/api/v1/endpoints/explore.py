from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import ExploreRequest, ExploreResponse
from app.services.ai_service import generate_journey
from app.core.auth import get_required_user
from app.core.supabase import get_supabase

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

    Requires authentication. The generated journey is saved to the user's
    account so it appears in their journeys list.

    **Errors**
    - `400` — question is empty or blank
    - `401` — not authenticated
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
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate journey. Please try again.")

    # Persist to Supabase
    try:
        db = get_supabase()
        db.table("journeys").insert({
            "id": journey.id,
            "uid": uid,
            "question": journey.question,
            "title": journey.title,
            "description": journey.description,
            "age_group": journey.age_group,
            "difficulty": journey.difficulty,
            "estimated_hours": journey.estimated_hours,
            "steps": [s.model_dump() for s in journey.steps],
            "tags": journey.tags,
            "icon": journey.icon,
            "is_curated": False,
        }).execute()
    except Exception:
        pass  # Don't fail the request if DB write fails

    return ExploreResponse(journey=journey)
