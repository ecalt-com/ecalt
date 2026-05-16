import json
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models.schemas import ExploreRequest, ExploreResponse
from app.services.ai_service import generate_journey, warm_journey_steps
from app.core.auth import get_required_user
from app.core.database import get_db

router = APIRouter()


@router.post(
    "",
    response_model=ExploreResponse,
    summary="Generate a learning journey",
    response_description="AI-generated Journey based on the submitted question",
)
async def explore(
    request: ExploreRequest,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_required_user),
):
    """
    Submit a curiosity question and receive a fully structured Journey.
    Requires authentication. The generated journey is saved to the user's account.
    Step content is pre-warmed in the background so the first expand is instant.
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

    # Persist to DB (non-fatal if it fails)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journeys
                        (id, uid, question, title, description, age_group, difficulty,
                         estimated_hours, steps, tags, icon, is_curated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, FALSE)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        journey.id, uid, journey.question, journey.title,
                        journey.description, journey.age_group, journey.difficulty,
                        journey.estimated_hours,
                        json.dumps([s.model_dump() for s in journey.steps]),
                        journey.tags,
                        journey.icon,
                    ),
                )
    except Exception:
        pass

    # Pre-warm step content in the background so users don't wait on first expand
    background_tasks.add_task(
        warm_journey_steps,
        journey.id,
        journey.steps,
        journey.title,
        journey.question,
    )

    return ExploreResponse(journey=journey)
