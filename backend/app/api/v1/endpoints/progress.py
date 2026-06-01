import json
import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_required_user
from app.core.database import get_db
from app.services.knowledge_service import credit_step_knowledge

router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_step_meta(journey_id: str, step_id: str) -> tuple[str, str, list[str]] | None:
    """Return (step_title, step_type, journey_tags) for a given step, or None.

    Tries the journeys DB table first, then falls back to the in-process
    static journey catalogue so curated journeys are always covered.
    """
    # --- DB journeys (user-generated via /explore) ---
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT steps, tags FROM journeys WHERE id = %s",
                    (journey_id,),
                )
                row = cur.fetchone()
                if row:
                    steps_raw = row["steps"]
                    if isinstance(steps_raw, str):
                        steps_raw = json.loads(steps_raw)
                    for s in (steps_raw or []):
                        if s.get("id") == step_id:
                            tags = list(row["tags"] or [])
                            return s["title"], s.get("type", "concept"), tags
    except Exception:
        pass

    # --- Static / curated journeys ---
    # Lazy import avoids a circular dependency at module load time.
    try:
        from app.api.v1.endpoints.journeys import SAMPLE_JOURNEYS
        for journey in SAMPLE_JOURNEYS:
            if journey.id == journey_id:
                for step in journey.steps:
                    if step.id == step_id:
                        return step.title, step.type, journey.tags
    except Exception:
        pass

    return None


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
    journey_id: str,
    step_id: str,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_required_user),
):
    """Mark a step as complete. Idempotent. Updates daily streak and knowledge graph."""
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

    # Only credit knowledge on a genuinely fresh completion.
    # ON CONFLICT DO NOTHING means row=None for duplicate calls, so we
    # never double-count the same step.
    if row:
        meta = _resolve_step_meta(journey_id, step_id)
        if meta:
            step_title, step_type, tags = meta
            background_tasks.add_task(credit_step_knowledge, uid, step_title, step_type, tags)

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
