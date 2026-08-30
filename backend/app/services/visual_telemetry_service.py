"""Visual Intelligence Layer — Phase 4: telemetry (spec section 22-23).

Append-only event log + a simple effectiveness rollup. No PII beyond the
uid the rest of the app already scopes everything by — event_data is a
free-form dict the frontend controls, so callers must not put learner text
answers or anything else sensitive in it (spec section 22: "Do not collect
unnecessary sensitive learner information in visual telemetry").
"""
import json

from app.core.database import get_db
from app.models.visual_schemas import VisualEvent
from app.services import visual_registry_service

EVENT_TYPES = (
    "visual_impression", "visual_started", "visual_completed",
    "visual_replayed", "visual_skipped", "visual_interaction", "visual_error",
)


def record_event(event: VisualEvent) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO visual_events
                    (uid, journey_id, step_id, vlo_id, session_id, event_type, event_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    event.userId, event.courseId, event.lessonId, event.vloId,
                    event.sessionId, event.eventType, json.dumps(event.eventData),
                ),
            )


def vlo_effectiveness_snapshot(vlo_id: str) -> dict:
    """Spec section 23's provisional formula, computed from raw event counts.
    Configurable, not a hardcoded permanent formula -- this is a starting
    point for Phase 4, meant to be tuned once real data exists."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, count(*) AS n
                FROM visual_events
                WHERE vlo_id = %s
                GROUP BY event_type
                """,
                (vlo_id,),
            )
            counts = {r["event_type"]: r["n"] for r in cur.fetchall()}

    impressions = counts.get("visual_impression", 0)
    completions = counts.get("visual_completed", 0)
    interactions = counts.get("visual_interaction", 0)
    replays = counts.get("visual_replayed", 0)
    skips = counts.get("visual_skipped", 0)

    if impressions == 0:
        return {"impressions": 0, "score": None}

    completion_rate = completions / impressions
    interaction_rate = interactions / impressions
    replay_rate = replays / impressions
    skip_rate = skips / impressions

    # quiz_improvement is not wired yet (needs a join against quiz_results
    # scoped to steps with vs. without a visual) -- left at 0 until that
    # analysis exists, so this score is completion/interaction/replay/skip
    # only for now.
    score = 0.20 * completion_rate + 0.15 * interaction_rate + 0.15 * replay_rate - 0.15 * skip_rate

    return {
        "impressions": impressions,
        "completion_rate": completion_rate,
        "interaction_rate": interaction_rate,
        "replay_rate": replay_rate,
        "skip_rate": skip_rate,
        "score": round(score, 4),
    }


def refresh_effectiveness_score(vlo_id: str) -> dict:
    snapshot = vlo_effectiveness_snapshot(vlo_id)
    if snapshot["score"] is not None:
        visual_registry_service.set_effectiveness_score(vlo_id, snapshot["score"])
    return snapshot
