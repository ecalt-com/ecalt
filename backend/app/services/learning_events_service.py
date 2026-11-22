"""Learning funnel events (F1.2): where do learners stop?

Counts of what happens at each step of a journey, from the browser (opened,
scrolled, quiz seen, time on step) and the server (step and journey completed).
Never recorded for school students. Props are small and carry no free text.
"""
import json
import logging
from typing import Optional

from app.core.database import get_db
from app.core.school_auth import is_school_student_uid

logger = logging.getLogger(__name__)

ALLOWED_EVENTS = frozenset({
    "step_open", "step_scroll_50", "step_scroll_90", "step_time",
    "quiz_view", "quiz_ready", "quiz_answer", "quiz_skip",
    "step_complete", "journey_complete", "review_answer", "notification_click",
})
MAX_BATCH = 20
MAX_PROPS_BYTES = 2048
MAX_ID_LEN = 100
RETENTION_DAYS = 180


def clean_event(raw: dict) -> Optional[tuple]:
    """(event, journey_id, step_id, props_json) or None when it isn't acceptable."""
    event = raw.get("event")
    if event not in ALLOWED_EVENTS:
        return None
    ids = []
    for key in ("journey_id", "step_id"):
        value = raw.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_ID_LEN):
            return None
        ids.append(value)
    props = raw.get("props") or {}
    if not isinstance(props, dict):
        return None
    encoded = json.dumps(props, separators=(",", ":"))
    if len(encoded.encode()) > MAX_PROPS_BYTES:
        return None
    return event, ids[0], ids[1], encoded


def record_events(uid: Optional[str], events: list[dict]) -> int:
    """Insert the acceptable events; returns how many were stored."""
    if not uid or is_school_student_uid(uid):
        return 0
    rows = [(uid, *c) for c in (clean_event(e) for e in events[:MAX_BATCH]) if c]
    if not rows:
        return 0
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO learning_events (uid, event, journey_id, step_id, props) "
                "VALUES (%s, %s, %s, %s, %s::jsonb)", rows)
    return len(rows)


def record_event(uid: Optional[str], event: str, journey_id: Optional[str] = None,
                 step_id: Optional[str] = None, props: Optional[dict] = None) -> None:
    """Best-effort single event from server code; never raises."""
    try:
        record_events(uid, [{"event": event, "journey_id": journey_id, "step_id": step_id, "props": props}])
    except Exception:
        logger.warning("learning event %s not recorded", event, exc_info=True)


def prune_old_events() -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM learning_events WHERE at < now() - make_interval(days => %s)",
                        (RETENTION_DAYS,))
            return cur.rowcount


def funnel(days: int = 30) -> dict:
    """Admin report: per-step-position drop-off and quiz readiness."""
    days = max(1, min(int(days), 365))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ev AS (
                  SELECT e.uid, e.journey_id, e.step_id, e.event, e.props,
                         COALESCE((SELECT i - 1 FROM journeys j, jsonb_array_elements(j.steps)
                                   WITH ORDINALITY x(st, i)
                                   WHERE j.id = e.journey_id AND st->>'id' = e.step_id LIMIT 1), -1) AS pos
                    FROM learning_events e
                   WHERE e.at > now() - make_interval(days => %s) AND e.step_id IS NOT NULL)
                SELECT pos AS step_index,
                       COUNT(DISTINCT (uid, journey_id)) FILTER (WHERE event = 'step_open')      AS opened,
                       COUNT(DISTINCT (uid, journey_id)) FILTER (WHERE event = 'step_scroll_90') AS read,
                       COUNT(DISTINCT (uid, journey_id)) FILTER (WHERE event = 'quiz_view')      AS quiz_seen,
                       COUNT(DISTINCT (uid, journey_id)) FILTER (WHERE event = 'quiz_answer')    AS answered,
                       COUNT(DISTINCT (uid, journey_id)) FILTER (WHERE event = 'step_complete')  AS completed
                  FROM ev WHERE pos >= 0 GROUP BY pos ORDER BY pos
                """, (days,))
            by_step = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) AS quizzes,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY (props->>'ms')::float) AS median_ms,
                       percentile_cont(0.95) WITHIN GROUP (ORDER BY (props->>'ms')::float) AS p95_ms
                  FROM learning_events
                 WHERE event = 'quiz_ready' AND at > now() - make_interval(days => %s)
                   AND props ? 'ms'
                """, (days,))
            quiz = dict(cur.fetchone())
            cur.execute(
                """
                SELECT COUNT(DISTINCT uid) AS learners,
                       COUNT(*) FILTER (WHERE event = 'journey_complete') AS journeys_completed,
                       COUNT(*) FILTER (WHERE event = 'notification_click') AS notification_clicks,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY (props->>'seconds')::float)
                         FILTER (WHERE event = 'step_time' AND props ? 'seconds') AS median_step_seconds
                  FROM learning_events WHERE at > now() - make_interval(days => %s)
                """, (days,))
            totals = dict(cur.fetchone())
    return {"days": days, "by_step": by_step, "quiz_generation": quiz, "totals": totals}
