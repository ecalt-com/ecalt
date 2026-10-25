import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_active_user, get_acting_uid
from app.core.database import get_db
from app.core.school_auth import is_school_student_uid
from app.services.knowledge_service import credit_step_knowledge
from app.services.quiz_service import step_quiz_passed
from app.services.interest_profile_service import invalidate as invalidate_profile
from app.services.journey_access import assert_can_read_journey

router = APIRouter()
logger = logging.getLogger(__name__)


def _invalidate_recommendation_cache(uid: str) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM journey_recommendations WHERE uid = %s", (uid,))
    except Exception:
        logger.debug("progress: recommendation cache invalidation failed (non-fatal)")


def _journey_steps(journey_id: str) -> tuple[list[dict], list[str]] | None:
    """Return (ordered step dicts, journey tags) for a journey, or None if unknown.

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
                    return list(steps_raw or []), list(row["tags"] or [])
    except Exception:
        pass

    # --- Static / curated journeys ---
    # Lazy import avoids a circular dependency at module load time.
    try:
        from app.api.v1.endpoints.journeys import SAMPLE_JOURNEYS
        for journey in SAMPLE_JOURNEYS:
            if journey.id == journey_id:
                return [s.model_dump() for s in journey.steps], list(journey.tags)
    except Exception:
        pass

    return None


def _resolve_step_meta(
    step_id: str, resolved: tuple[list[dict], list[str]] | None
) -> tuple[str, str, list[str]] | None:
    """Return (step_title, step_type, journey_tags) for a given step, or None."""
    if not resolved:
        return None
    steps, tags = resolved
    for s in steps:
        if s.get("id") == step_id:
            return s["title"], s.get("type", "concept"), tags
    return None


def _check_previous_steps_complete(
    uid: str,
    journey_id: str,
    step_id: str,
    resolved: tuple[list[dict], list[str]] | None,
) -> None:
    """Raise 409 if any step before step_id is not yet completed by this user.

    Permissive when the journey or step can't be resolved (deleted journeys,
    legacy links): the insert proceeds as before. Existing out-of-order rows
    are grandfathered — only new completions are constrained.
    """
    if not resolved:
        return
    step_ids = [s.get("id") for s in resolved[0]]
    if step_id not in step_ids:
        return
    prior_ids = step_ids[: step_ids.index(step_id)]
    if not prior_ids:
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT step_id FROM user_progress WHERE uid = %s AND journey_id = %s",
                (uid, journey_id),
            )
            done = {r["step_id"] for r in cur.fetchall()}

    missing = [s for s in prior_ids if s not in done]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "previous_steps_incomplete",
                "missing_step_ids": missing,
            },
        )


def _check_quiz_passed(
    uid: str,
    journey_id: str,
    step_id: str,
    resolved: tuple[list[dict], list[str]] | None,
) -> None:
    """Raise 412 unless the user has passed the quiz for this step.

    Same permissive fallback as the order check: unresolvable journeys/steps
    are not gated, so legacy links keep working.
    """
    if not resolved:
        return
    if step_id not in [s.get("id") for s in resolved[0]]:
        return
    if not step_quiz_passed(uid, journey_id, step_id):
        raise HTTPException(
            status_code=412,
            detail={"message": "quiz_not_passed"},
        )


class ProgressResponse(BaseModel):
    journey_id: str
    step_id: str
    completed: bool
    completed_at: Optional[str] = None


class JourneyProgressResponse(BaseModel):
    journey_id: str
    completed_step_ids: list[str]
    updated_step_ids: list[str] = []   # finished steps whose content changed since (SC-604)


def _updated_since_completed(journey_id: str, completed: list[dict]) -> list[str]:
    """Of the steps this user finished, those whose content changed afterwards.

    A school course republished from a revised document stamps every changed
    step with `content_updated_at` (see `school_course_service.publish_course`),
    so a student who already finished the old version gets the "updated since
    you finished" badge on exactly those steps. Best-effort: anything
    unparseable simply yields no badge.
    """
    done_at = {r["step_id"]: r["completed_at"] for r in completed if r.get("completed_at")}
    if not done_at:
        return []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT steps FROM journeys WHERE id = %s", (journey_id,))
                row = cur.fetchone()
        steps = (row or {}).get("steps") or []
        if isinstance(steps, str):
            steps = json.loads(steps)
    except Exception:
        return []

    out = []
    for step in steps:
        stamp, finished = step.get("content_updated_at"), done_at.get(step.get("id"))
        if not stamp or not finished:
            continue
        try:
            changed_at = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=timezone.utc)
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        if changed_at > finished:
            out.append(step["id"])
    return out


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
async def get_progress(journey_id: str, ctx: tuple = Depends(get_acting_uid)):
    """Return all completed step IDs for a journey."""
    uid, _ = ctx
    assert_can_read_journey(uid, journey_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT step_id, completed_at FROM user_progress WHERE uid = %s AND journey_id = %s",
                (uid, journey_id),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return JourneyProgressResponse(
        journey_id=journey_id,
        completed_step_ids=[r["step_id"] for r in rows],
        updated_step_ids=_updated_since_completed(journey_id, rows),
    )


@router.post("/{journey_id}/{step_id}", response_model=ProgressResponse)
async def mark_step_complete(
    journey_id: str,
    step_id: str,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_active_user),
):
    """Mark a step as complete. Idempotent. Updates daily streak and knowledge graph.

    Steps must be completed in order (409 with the missing step IDs otherwise)
    and the step's quiz must be passed first (412 quiz_not_passed otherwise).
    """
    assert_can_read_journey(uid, journey_id)
    resolved = _journey_steps(journey_id)
    _check_previous_steps_complete(uid, journey_id, step_id, resolved)
    # On a school course the quiz only gates completion when the teacher made it
    # required for the class (SC-503); ordinary journeys always gate (unchanged).
    if is_school_student_uid(uid):
        from app.services.school_assignment_service import student_quiz_required
        if student_quiz_required(uid, journey_id):
            _check_quiz_passed(uid, journey_id, step_id, resolved)
    else:
        _check_quiz_passed(uid, journey_id, step_id, resolved)

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
    # Fresh step completion — profile and recommendations may now be stale.
    if row:
        invalidate_profile(uid)
        _invalidate_recommendation_cache(uid)

    # Only credit knowledge on a genuinely fresh completion.
    # ON CONFLICT DO NOTHING means row=None for duplicate calls, so we
    # never double-count the same step.
    if row:
        meta = _resolve_step_meta(step_id, resolved)
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
    journey_id: str, step_id: str, uid: str = Depends(get_active_user)
):
    """Unmark a step as complete."""
    assert_can_read_journey(uid, journey_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_progress WHERE uid = %s AND journey_id = %s AND step_id = %s",
                (uid, journey_id, step_id),
            )
    return ProgressResponse(journey_id=journey_id, step_id=step_id, completed=False)
