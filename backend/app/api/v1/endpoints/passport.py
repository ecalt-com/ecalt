from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import get_required_user
from app.core.database import get_db

router = APIRouter()


class PassportJourney(BaseModel):
    id: str
    title: str
    icon: str
    category: str
    completed_steps: int
    total_steps: int
    completed_at: str
    fully_completed: bool


class PassportResponse(BaseModel):
    journeys: list[PassportJourney]
    total_completed: int
    total_in_progress: int
    categories: list[str]
    estimated_hours: float


@router.get("", response_model=PassportResponse)
async def get_passport(uid: str = Depends(get_required_user)):
    """Return the authenticated user's full capability passport."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # All progress rows for this user
            cur.execute(
                """
                SELECT journey_id, step_id, completed_at
                FROM user_progress
                WHERE uid = %s
                ORDER BY completed_at DESC
                """,
                (uid,),
            )
            progress_rows = cur.fetchall()

            if not progress_rows:
                return PassportResponse(
                    journeys=[], total_completed=0, total_in_progress=0,
                    categories=[], estimated_hours=0.0,
                )

            # Group progress by journey
            by_journey: dict[str, dict] = {}
            for r in progress_rows:
                jid = r["journey_id"]
                if jid not in by_journey:
                    by_journey[jid] = {"steps": [], "latest": r["completed_at"]}
                by_journey[jid]["steps"].append(r["step_id"])

            # Fetch journey metadata for all touched journeys
            journey_ids = list(by_journey.keys())
            cur.execute(
                "SELECT id, title, icon, tags, steps FROM journeys WHERE id = ANY(%s)",
                (journey_ids,),
            )
            journey_rows = cur.fetchall()

    passport_journeys: list[PassportJourney] = []
    for j in journey_rows:
        completed_steps = len(by_journey[j["id"]]["steps"])
        total_steps = len(j.get("steps") or [])
        tags = j.get("tags") or []
        category = tags[0] if tags else "general"
        latest = by_journey[j["id"]]["latest"]
        passport_journeys.append(PassportJourney(
            id=j["id"],
            title=j["title"],
            icon=j["icon"],
            category=category,
            completed_steps=completed_steps,
            total_steps=total_steps,
            completed_at=str(latest),
            fully_completed=completed_steps >= total_steps and total_steps > 0,
        ))

    # Also handle journeys that are in progress but not in DB (curated ones)
    fully_done = [j for j in passport_journeys if j.fully_completed]
    in_progress = [j for j in passport_journeys if not j.fully_completed]
    categories = list({j.category for j in fully_done})

    return PassportResponse(
        journeys=passport_journeys,
        total_completed=len(fully_done),
        total_in_progress=len(in_progress),
        categories=categories,
        estimated_hours=round(len(fully_done) * 2.5, 1),
    )
