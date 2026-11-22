"""Spaced review (F1.3): bring learners back to what they've already studied.

A step becomes a review item when it is completed. Each item lives in a Leitner
box; a correct review moves it up (reviewed less often), a miss sends it back to
box 1. Questions are the ones the learner already saw for that step, copied into
a fresh quiz session without a set id, so a review never touches a step's quiz
gate and costs no model call.
"""
import json
import logging
from typing import Optional

from app.core.database import get_db

logger = logging.getLogger(__name__)

INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
MAX_BOX = 5
DEFAULT_LIMIT = 5


def next_box(box: int, correct: bool) -> int:
    return min(MAX_BOX, box + 1) if correct else 1


def seed_item(uid: str, journey_id: str, step_id: str, concept: str) -> None:
    """Add a step to the learner's review queue, due tomorrow. Re-completing a
    step never resets an item that is already in progress."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO review_items (uid, journey_id, step_id, concept, box, due_at)
                    VALUES (%s, %s, %s, %s, 1, now() + make_interval(days => %s))
                    ON CONFLICT (uid, journey_id, step_id) DO NOTHING
                    """,
                    (uid, journey_id, step_id, (concept or "this step")[:200], INTERVAL_DAYS[1]),
                )
    except Exception:
        logger.warning("review item not seeded uid=%s step=%s", uid, step_id, exc_info=True)


def due_items(uid: str, limit: int = DEFAULT_LIMIT) -> dict:
    """The learner's due items (oldest due first) and how many are due in all."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM review_items WHERE uid = %s AND due_at <= now()", (uid,))
            total = int(cur.fetchone()["n"])
            items = []
            if limit > 0:
                cur.execute(
                    """
                    SELECT r.id::text AS item_id, r.journey_id, r.step_id, r.concept, r.box,
                           (SELECT j.title FROM journeys j WHERE j.id = r.journey_id) AS journey_title
                      FROM review_items r
                     WHERE r.uid = %s AND r.due_at <= now()
                     ORDER BY r.due_at, r.created_at
                     LIMIT %s
                    """,
                    (uid, limit),
                )
                items = [dict(r) for r in cur.fetchall()]
    return {"due_count": total, "items": items}


def _public(row: dict, quiz_id: str) -> dict:
    q = row["quiz_data"] if isinstance(row["quiz_data"], dict) else json.loads(row["quiz_data"])
    return {
        "quiz_id": quiz_id,
        "concept": q.get("concept_tested", row["concept"]),
        "difficulty": q.get("difficulty", "exploratory"),
        "intro_phrase": q.get("intro_phrase", ""),
        "question": q.get("question", ""),
        "hint_available": 3,
    }


def start_item(uid: str, item_id: str) -> Optional[dict]:
    """A review question for an item: one the learner already saw for that step,
    preferring one they got wrong. Returns None when the item doesn't exist or
    nothing was stored (the caller may skip it)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT journey_id, step_id FROM review_items WHERE id = %s AND uid = %s", (item_id, uid))
            item = cur.fetchone()
            if not item:
                return None
            cur.execute(
                """
                SELECT s.concept, s.quiz_data
                  FROM quiz_sessions s
                 WHERE s.uid = %s AND s.journey_id = %s AND s.step_id = %s
                 ORDER BY EXISTS (SELECT 1 FROM quiz_results r WHERE r.session_id = s.id AND NOT r.is_correct) DESC,
                          random()
                 LIMIT 1
                """,
                (uid, item["journey_id"], item["step_id"]),
            )
            src = cur.fetchone()
            if not src:
                return None
            q = src["quiz_data"] if isinstance(src["quiz_data"], dict) else json.loads(src["quiz_data"])
            cur.execute(
                "INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id) "
                "VALUES (%s, %s, %s::jsonb, %s, %s) RETURNING id",
                (uid, src["concept"], json.dumps(q), item["journey_id"], item["step_id"]),
            )
            quiz_id = str(cur.fetchone()["id"])
    return _public(src, quiz_id)


def quiz_belongs_to_item(uid: str, item_id: str, quiz_id: str) -> bool:
    """The quiz session was created for this learner's item (same step)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM review_items r JOIN quiz_sessions s
                  ON s.uid = r.uid AND s.journey_id = r.journey_id AND s.step_id = r.step_id
                 WHERE r.id = %s AND r.uid = %s AND s.id = %s AND s.quiz_set_id IS NULL
                """,
                (item_id, uid, quiz_id),
            )
            return cur.fetchone() is not None


def apply_result(uid: str, item_id: str, correct: bool) -> Optional[dict]:
    """Move the item between boxes and schedule its next review."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT box FROM review_items WHERE id = %s AND uid = %s FOR UPDATE", (item_id, uid))
            row = cur.fetchone()
            if not row:
                return None
            box = next_box(int(row["box"]), correct)
            days = INTERVAL_DAYS[box]
            cur.execute(
                "UPDATE review_items SET box = %s, due_at = now() + make_interval(days => %s), "
                "last_result = %s, last_reviewed_at = now() WHERE id = %s",
                (box, days, "correct" if correct else "incorrect", item_id),
            )
    return {"box": box, "next_review_in_days": days}
