"""
Quiz service — Phase 3.

Generates fingerprint-calibrated quiz questions from conversation/step context,
stores sessions server-side (so correct_answer is never in the client),
and tracks results for adaptive difficulty.
"""
import json
import logging
import math
import re
from uuid import UUID, uuid4

from app.core.database import get_db
from app.services.fingerprint_service import inject_fingerprint
from app.services.provider_service import complete_text, get_config

logger = logging.getLogger(__name__)

_VALID_DIFFICULTIES = {"surface", "exploratory", "deep", "research"}


def pass_threshold(total: int) -> int:
    """Questions that must be correct to pass a quiz set (2 of 3, scales as ⌈⅔n⌉)."""
    return max(1, math.ceil(total * 2 / 3))
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
                    WHERE uid = %s AND skipped = FALSE
                    ORDER BY answered_at DESC LIMIT 3
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


def record_quiz_result(
    uid: str,
    concept: str,
    difficulty: str,
    is_correct: bool,
    hints_used: int,
    journey_id: str | None = None,
    step_id: str | None = None,
    session_id: str | None = None,
) -> None:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quiz_results
                        (uid, concept, difficulty, is_correct, hints_used,
                         journey_id, step_id, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (uid, concept[:200], difficulty, is_correct, hints_used,
                     journey_id, step_id, session_id),
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
                    "SELECT is_correct, hints_used FROM quiz_results WHERE uid = %s AND skipped = FALSE ORDER BY answered_at DESC LIMIT 3",
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


async def generate_quiz_set(
    uid: str,
    concept: str,
    context: str,
    base_depth: str = "exploratory",
    num_questions: int = 3,
    journey_id: str | None = None,
    step_id: str | None = None,
) -> tuple[dict, int, int]:
    """
    Generate a set of distinct quiz questions for a journey step in a single
    LLM call. Each question is stored as its own quiz_sessions row (so the
    per-question hint/submit endpoints work unchanged), tagged with the
    journey/step and a shared quiz_set_id.
    """
    num_questions = max(2, min(int(num_questions), 5))
    difficulty = get_adaptive_difficulty(uid, base_depth)

    # Difficulty is computed once per set — per-question adaptation would
    # oscillate within a single quiz.
    recent_summary = ""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_correct, hints_used FROM quiz_results WHERE uid = %s AND skipped = FALSE ORDER BY answered_at DESC LIMIT 3",
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
        f"OVERRIDE FOR THIS REQUEST: generate exactly {num_questions} DISTINCT questions, "
        f"each covering a different aspect of the concept (no two questions may test the "
        f"same insight). Output a JSON ARRAY of {num_questions} objects, each matching the "
        f"output format specified above. No markdown, no preamble — the array only.\n\n"
        f"Context from learning session:\n{context[:1500]}"
    )

    try:
        raw, in_tok, out_tok, _ = await complete_text(
            interaction_type="quiz",
            system=system,
            user_content=user_content,
            max_tokens=1800,
        )
    except Exception as e:
        logger.error("quiz_set.ai_failed uid=%s concept=%.60s: %s", uid, concept, e)
        raise

    questions = _parse_question_list(raw)
    if not questions:
        logger.error("quiz_set.no_json uid=%s concept=%.60s raw=%.120s", uid, concept, raw)
        raise ValueError("Quiz AI returned no JSON")
    questions = questions[:num_questions]

    quiz_set_id = str(uuid4())
    public_questions = []
    with get_db() as conn:
        with conn.cursor() as cur:
            for q in questions:
                q["difficulty"] = difficulty
                cur.execute(
                    """
                    INSERT INTO quiz_sessions
                        (uid, concept, quiz_data, journey_id, step_id, quiz_set_id)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                    RETURNING id
                    """,
                    (uid, concept[:200], json.dumps(q), journey_id, step_id, quiz_set_id),
                )
                quiz_id = str(cur.fetchone()["id"])
                public_questions.append({
                    "quiz_id":      quiz_id,
                    "concept":      q.get("concept_tested", concept),
                    "difficulty":   difficulty,
                    "intro_phrase": q.get("intro_phrase", ""),
                    "question":     q.get("question", ""),
                    "hint_available": 3,
                })

    return {
        "quiz_set_id": quiz_set_id,
        "questions": public_questions,
        "pass_threshold": pass_threshold(len(public_questions)),
    }, in_tok, out_tok


def _parse_question_list(raw: str) -> list[dict]:
    """Parse the model output into a list of question dicts.

    Accepts a JSON array, or falls back to a single object (wrapped in a list)
    so a model that ignores the array override still produces a working —
    if shorter — quiz.
    """
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(raw[start:end])
            if isinstance(parsed, list):
                return [q for q in parsed if isinstance(q, dict) and q.get("question")]
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(raw[start:end])
            if isinstance(parsed, dict) and parsed.get("question"):
                return [parsed]
        except Exception:
            pass

    return []


# ── Step quiz status (gates step completion) ─────────────────────────────────

def record_quiz_skip(uid: str, journey_id: str, step_id: str) -> None:
    """Record an explicit quiz skip — the step's quiz gate opens without a pass.

    Skips are stored in quiz_results (skipped=TRUE, no session) so there's an
    audit trail, but they are excluded from adaptive-difficulty history.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quiz_results
                        (uid, concept, difficulty, is_correct, hints_used,
                         journey_id, step_id, skipped)
                    VALUES (%s, %s, %s, FALSE, 0, %s, %s, TRUE)
                    """,
                    (uid, "step quiz skipped", "exploratory", journey_id, step_id),
                )
    except Exception as e:
        logger.warning("record_quiz_skip failed uid=%s: %s", uid, e)
        raise


def step_quiz_status(uid: str, journey_id: str, step_id: str) -> dict:
    """Return {passed, skipped, correct, total} for a journey step.

    A step is passed when the user explicitly skipped its quiz, or when any
    quiz set for it has every question answered and at least
    pass_threshold(total) correct.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM quiz_results
                    WHERE uid = %s AND journey_id = %s AND step_id = %s AND skipped = TRUE
                    LIMIT 1
                    """,
                    (uid, journey_id, step_id),
                )
                if cur.fetchone():
                    return {"passed": True, "skipped": True, "correct": 0, "total": 0}
                cur.execute(
                    """
                    SELECT s.quiz_set_id,
                           COUNT(*) FILTER (WHERE r.is_correct)              AS correct,
                           COUNT(r.id)                                       AS answered,
                           (SELECT COUNT(*) FROM quiz_sessions s2
                             WHERE s2.quiz_set_id = s.quiz_set_id)           AS total
                    FROM quiz_results r
                    JOIN quiz_sessions s ON s.id = r.session_id
                    WHERE r.uid = %s AND r.journey_id = %s AND r.step_id = %s
                      AND s.quiz_set_id IS NOT NULL
                    GROUP BY s.quiz_set_id
                    """,
                    (uid, journey_id, step_id),
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.warning("step_quiz_status failed uid=%s: %s", uid, e)
        rows = []

    best = {"passed": False, "skipped": False, "correct": 0, "total": 0}
    for r in rows:
        total = int(r["total"] or 0)
        correct = int(r["correct"] or 0)
        answered = int(r["answered"] or 0)
        passed = total > 0 and answered >= total and correct >= pass_threshold(total)
        if passed:
            return {"passed": True, "skipped": False, "correct": correct, "total": total}
        if correct >= best["correct"]:
            best = {"passed": False, "skipped": False, "correct": correct, "total": total}
    return best


def step_quiz_passed(uid: str, journey_id: str, step_id: str) -> bool:
    return step_quiz_status(uid, journey_id, step_id)["passed"]


_GRADE_SYSTEM = """\
You are a quiz grader for an educational platform.
Given a quiz question, the model answer, and a student's response, decide if the student \
demonstrates genuine understanding of the key concept.

Respond with ONLY valid JSON — no explanation, no markdown:
{"correct": true}  — student captures the core idea, even if worded differently
{"correct": false} — response is wrong, too vague, nonsensical, or not a real attempt"""


def _is_trivially_invalid(answer: str) -> bool:
    """Fewer than 2 real words → not a genuine attempt (catches '.', '!', single chars)."""
    return len(re.findall(r"[a-zA-Z]{2,}", answer)) < 2


async def _llm_grade_answer(question: str, correct_ans: str, user_answer: str) -> bool:
    """Semantically grade a free-text answer via LLM. Returns True if correct."""
    user_content = (
        f"Question: {question}\n"
        f"Model answer: {correct_ans}\n"
        f"Student response: {user_answer}"
    )
    try:
        raw, _, _, _ = await complete_text(
            interaction_type="quiz",
            system=_GRADE_SYSTEM,
            user_content=user_content,
            max_tokens=20,
        )
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            return bool(json.loads(raw[start:end]).get("correct", False))
    except Exception as e:
        logger.warning("quiz grading LLM failed, defaulting incorrect: %s", e)
    return False


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


async def submit_answer(quiz_id: str, uid: str, user_answer: str) -> dict:
    """
    Evaluate a submitted answer via LLM semantic grading, record the result,
    and return the correct answer + explanation.
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
    question    = quiz_data.get("question", "")

    if _is_trivially_invalid(user_answer):
        is_correct = False
    else:
        is_correct = await _llm_grade_answer(question, correct_ans, user_answer)

    _mark_submitted(quiz_id)
    record_quiz_result(
        uid, concept, difficulty, is_correct, hints_used,
        journey_id=session.get("journey_id"),
        step_id=session.get("step_id"),
        session_id=str(session.get("id")) if session.get("id") else None,
    )

    return {
        "is_correct":        is_correct,
        "correct_answer":    correct_ans,
        "answer_explanation": explanation,
        "hints_used":        hints_used,
        "concept":           concept,
        "difficulty":        difficulty,
    }
