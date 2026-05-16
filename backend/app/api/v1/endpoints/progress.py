import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_required_user
from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


class ProgressResponse(BaseModel):
    journey_id: str
    step_id: str
    completed: bool
    completed_at: Optional[str] = None


class JourneyProgressResponse(BaseModel):
    journey_id: str
    completed_step_ids: list[str]


def _update_streak(uid: str) -> None:
    """Increment streak if a new day, reset if gap, no-op if same day. Best-effort."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users SET
                        streak_days = CASE
                            WHEN last_active_date = CURRENT_DATE          THEN streak_days
                            WHEN last_active_date = CURRENT_DATE - 1      THEN streak_days + 1
                            ELSE 1
                        END,
                        last_active_date = CURRENT_DATE
                    WHERE uid = %s
                    """,
                    (uid,),
                )
    except Exception:
        logger.debug("Streak update skipped — column may not exist yet")


@router.get("/{journey_id}", response_model=JourneyProgressResponse)
async def get_progress(journey_id: str, uid: str = Depends(get_required_user)):
    """Return all completed step IDs for a journey."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT step_id FROM user_progress WHERE uid = %s AND journey_id = %s",
                (uid, journey_id),
            )
            rows = cur.fetchall()
    return JourneyProgressResponse(
        journey_id=journey_id,
        completed_step_ids=[r["step_id"] for r in rows],
    )


@router.post("/{journey_id}/{step_id}", response_model=ProgressResponse)
async def mark_step_complete(
    journey_id: str, step_id: str, uid: str = Depends(get_required_user)
):
    """Mark a step as complete. Idempotent. Updates daily streak."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_progress (uid, journey_id, step_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (uid, journey_id, step_id) DO NOTHING
                RETURNING completed_at
                """,
                (uid, journey_id, step_id),
            )
            row = cur.fetchone()

    _update_streak(uid)

    return ProgressResponse(
        journey_id=journey_id,
        step_id=step_id,
        completed=True,
        completed_at=str(row["completed_at"]) if row and row.get("completed_at") else None,
    )


@router.delete("/{journey_id}/{step_id}", response_model=ProgressResponse)
async def mark_step_incomplete(
    journey_id: str, step_id: str, uid: str = Depends(get_required_user)
):
    """Unmark a step as complete."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_progress WHERE uid = %s AND journey_id = %s AND step_id = %s",
                (uid, journey_id, step_id),
            )
    return ProgressResponse(journey_id=journey_id, step_id=step_id, completed=False)
