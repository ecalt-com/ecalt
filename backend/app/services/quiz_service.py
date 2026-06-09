"""
Quiz service — Phase 3.

Generates fingerprint-calibrated quiz questions from conversation/step context,
stores sessions server-side (so correct_answer is never in the client),
and tracks results for adaptive difficulty.
"""
import json
import logging
from uuid import UUID

from app.core.database import get_db
from app.services.fingerprint_service import inject_fingerprint
from app.services.provider_service import complete_text, get_config

logger = logging.getLogger(__name__)

_VALID_DIFFICULTIES = {"surface", "exploratory", "deep", "research"}
_ESCALATE_MAP = {"surface": "exploratory", "exploratory": "deep", "deep": "research", "research": "research"}
_HOLD_MAP     = {"surface": "surface", "exploratory": "surface", "deep": "exploratory", "research": "deep"}


# ── Adaptive difficulty ───────────────────────────────────────────────────────

def get_adaptive_difficulty(uid: str, base_depth: str) -> str:
    """
    Adjust difficulty based on the last 3 quiz results.
    - All correct + no hints → escalate one level
    - 2+ incorrect          → drop one level
    - Otherwise             → keep base_depth
    """
    if base_depth not in _VALID_DIFFICULTIES:
        base_depth = "exploratory"
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT is_correct, hints_used FROM quiz_results
                    WHERE uid = %s ORDER BY answered_at DESC LIMIT 3
                    """,
                    (uid,),
                )
                rows = cur.fetchall()
        if not rows:
            return base_depth
        all_correct   = all(r["is_correct"] for r in rows)
        no_hints      = all(r["hints_used"] == 0 for r in rows)
        incorrect_cnt = sum(1 for r in rows if not r["is_correct"])
        if all_correct and no_hints:
            return _ESCALATE_MAP[base_depth]
        if incorrect_cnt >= 2:
            return _HOLD_MAP[base_depth]
    except Exception as e:
        logger.debug("get_adaptive_difficulty error uid=%s: %s", uid, e)
    return base_depth


def record_quiz_result(uid: str, concept: str, difficulty: str, is_correct: bool, hints_used: int) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quiz_results (uid, concept, difficulty, is_correct, hints_used)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (uid, concept[:200], difficulty, is_correct, hints_used),
                )
    except Exception as e:
        logger.warning("record_quiz_result failed uid=%s: %s", uid, e)


# ── Session management ────────────────────────────────────────────────────────

def _get_session(quiz_id: str, uid: str) -> dict | None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM quiz_sessions WHERE id = %s AND uid = %s",
                    (quiz_id, uid),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        return None


def _update_hints_given(quiz_id: str, hints_given: int) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE quiz_sessions SET hints_given = %s WHERE id = %s",
                    (hints_given, quiz_id),
                )
    except Exception:
        pass


def _mark_submitted(quiz_id: str) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE quiz_sessions SET submitted = TRUE WHERE id = %s",
                    (quiz_id,),
                )
    except Exception:
        pass


# ── Generation ────────────────────────────────────────────────────────────────

async def generate_quiz(
    uid: str,
    concept: str,
    context: str,
    base_depth: str = "exploratory",
) -> tuple[dict, int, int]:
    """
    Generate a quiz question for a concept. Stores session server-side.
    Returns public quiz data (no correct_answer).
    """
    difficulty = get_adaptive_difficulty(uid, base_depth)

    # Fetch recent results summary for adaptive prompt context
    recent_summary = ""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_correct, hints_used FROM quiz_results WHERE uid = %s ORDER BY answered_at DESC LIMIT 3",
                    (uid,),
                )
                rows = cur.fetchall()
        if rows:
            correct = sum(1 for r in rows if r["is_correct"])
            avg_hints = sum(r["hints_used"] for r in rows) / len(rows)
            recent_summary = f"Recent performance: {correct}/{len(rows)} correct, avg hints used: {avg_hints:.1f}."
    except Exception:
        pass

    cfg = get_config("quiz")
    system = inject_fingerprint(uid, cfg["style_prompt"])
    user_content = (
        f"Concept: {concept}\n"
        f"question_depth: {difficulty}\n"
        f"{recent_summary}\n\n"
        f"Context from learning session:\n{context[:1500]}"
    )

    try:
        raw, in_tok, out_tok, _ = await complete_text(
            interaction_type="quiz",
            system=system,
            user_content=user_content,
            max_tokens=700,
        )
    except Exception as e:
        logger.error("quiz.ai_failed uid=%s concept=%.60s: %s", uid, concept, e)
        raise

    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        logger.error("quiz.no_json uid=%s concept=%.60s raw=%.120s", uid, concept, raw)
        raise ValueError("Quiz AI returned no JSON")

    quiz_data = json.loads(raw[start:end])
    quiz_data["difficulty"] = difficulty

    # Store full quiz (including correct_answer) server-side
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quiz_sessions (uid, concept, quiz_data)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
                """,
                (uid, concept[:200], json.dumps(quiz_data)),
            )
            quiz_id = str(cur.fetchone()["id"])

    # Return public slice — correct_answer stays server-side
    return {
        "quiz_id":     quiz_id,
        "concept":     quiz_data.get("concept_tested", concept),
        "difficulty":  difficulty,
        "intro_phrase": quiz_data.get("intro_phrase", ""),
        "question":    quiz_data.get("question", ""),
        "hint_available": 3,
    }, in_tok, out_tok


def get_hint(quiz_id: str, uid: str) -> dict:
    """Return the next hint for a quiz session."""
    session = _get_session(quiz_id, uid)
    if not session:
        raise ValueError("Quiz session not found")
    if session["submitted"]:
        raise ValueError("Quiz already submitted")

    hints_given = session["hints_given"]
    if hints_given >= 3:
        raise ValueError("All hints already used")

    quiz_data  = session["quiz_data"]
    hints_given += 1
    hint_key   = f"hint_{hints_given}"
    hint_text  = quiz_data.get(hint_key, "")

    _update_hints_given(quiz_id, hints_given)

    return {
        "hint_num":  hints_given,
        "hint_text": hint_text,
        "hints_remaining": 3 - hints_given,
    }


def submit_answer(quiz_id: str, uid: str, user_answer: str) -> dict:
    """
    Evaluate a submitted answer, record the result, and return
    the correct answer + explanation.
    """
    session = _get_session(quiz_id, uid)
    if not session:
        raise ValueError("Quiz session not found")
    if session["submitted"]:
        raise ValueError("Quiz already submitted")

    quiz_data   = session["quiz_data"]
    hints_used  = session["hints_given"]
    correct_ans = quiz_data.get("correct_answer", "")
    explanation = quiz_data.get("answer_explanation", "")
    difficulty  = quiz_data.get("difficulty", "exploratory")
    concept     = session["concept"]

    # Simple correctness check: normalise both and compare
    # (AI-generated answers evaluated by normalised substring match)
    norm_user    = user_answer.strip().lower()
    norm_correct = correct_ans.strip().lower()
    is_correct   = (norm_user in norm_correct) or (norm_correct in norm_user) or (norm_user == norm_correct)

    _mark_submitted(quiz_id)
    record_quiz_result(uid, concept, difficulty, is_correct, hints_used)

    return {
        "is_correct":        is_correct,
        "correct_answer":    correct_ans,
        "answer_explanation": explanation,
        "hints_used":        hints_used,
        "concept":           concept,
        "difficulty":        difficulty,
    }
