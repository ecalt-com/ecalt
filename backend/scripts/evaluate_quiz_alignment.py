"""
Alignment evaluator — measures what fraction of quiz questions a learner who
read only the step content could correctly answer.

Usage:
  python scripts/evaluate_quiz_alignment.py
  python scripts/evaluate_quiz_alignment.py --phase 5 --cluster-failures

Writes results to scripts/alignment_<phase>.json and prints a summary.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make app importable from the backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.services.provider_service import complete_text, get_config
from app.services.quiz_service import generate_quiz_set

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """\
You are an educational alignment reviewer. Your only job is to score whether
a quiz question is fair given what the content teaches.

A learner read ONLY the content provided — no textbook, no internet, no prior
knowledge of this topic.

Score this question on two dimensions:

answerable_score (float 0.0–1.0):
  1.0 = Fully and clearly answerable from the content alone
  0.7 = Mostly answerable; content hints at it but is vague
  0.5 = Half answerable; requires one small inference not in content
  0.2 = Barely answerable; mostly requires outside knowledge
  0.0 = Completely unanswerable from this content

gap (string, required if score < 0.8):
  In one sentence: exactly what specific fact, mechanism, or detail does
  the content NOT cover that this question requires?
  Be concrete. Not "more depth needed" — name the specific missing thing.
  e.g. "Content says mitochondria make energy but never explains ATP or
  oxidative phosphorylation, which the question requires."

Return ONLY valid JSON:
{"answerable_score": 0.7, "gap": "..."}"""


async def _judge_question(content: str, question: str, correct_answer: str) -> dict:
    user_msg = (
        f"Step content:\n---\n{content}\n---\n\n"
        f"Quiz question: {question}\n"
        f"Expected answer: {correct_answer}"
    )
    try:
        raw, _, _, _ = await complete_text(
            interaction_type="quiz",
            system=_JUDGE_SYSTEM,
            user_content=user_msg,
            max_tokens=200,
        )
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        logger.warning("judge call failed: %s", e)
    return {"answerable_score": 0.5, "gap": "judge error — defaulting to 0.5"}


def _pull_test_steps(limit: int = 100) -> list[dict]:
    """Pull steps with existing warmed content from the DB."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  s.journey_id, s.step_id, s.content,
                  j.difficulty AS journey_difficulty,
                  j.age_group,
                  j.steps AS journey_steps_json
                FROM step_content s
                JOIN journeys j ON j.id = s.journey_id
                WHERE s.content IS NOT NULL AND length(s.content) > 100
                ORDER BY random()
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


def _extract_step_type(journey_steps_json, step_id: str) -> str:
    try:
        steps = journey_steps_json if isinstance(journey_steps_json, list) else json.loads(journey_steps_json or "[]")
        for s in steps:
            if s.get("id") == step_id:
                return s.get("type", "concept")
    except Exception:
        pass
    return "concept"


def _pull_quiz_sessions(journey_id: str, step_id: str) -> list[dict]:
    """Fetch existing stored quiz questions for a step (avoid regenerating)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT quiz_data FROM quiz_sessions
                    WHERE journey_id = %s AND step_id = %s
                      AND quiz_set_id IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 3
                    """,
                    (journey_id, step_id),
                )
                rows = cur.fetchall()
                return [row["quiz_data"] for row in rows if row["quiz_data"]]
    except Exception:
        return []


def _print_summary(results: list[dict], label: str = "ALIGNMENT") -> None:
    all_q = []
    for r in results:
        for key in ("question_1", "question_2", "question_3"):
            q = r.get(key)
            if q:
                all_q.append({
                    "step_type":          r["step_type"],
                    "journey_difficulty": r["journey_difficulty"],
                    "difficulty":         q.get("difficulty", "exploratory"),
                    "answerable_score":   q.get("answerable_score", 0),
                    "gap":                q.get("gap", ""),
                })

    total = len(all_q)
    if total == 0:
        print("No questions evaluated.")
        return

    passed = sum(1 for q in all_q if q["answerable_score"] >= 0.8)

    print(f"\n=== {label} ===")
    print(f"Steps evaluated:          {len(results)}")
    print(f"Questions evaluated:      {total}")
    print(f"\nOverall answerable ≥0.8:  {passed/total:.0%}  ({passed}/{total})")

    print("\nBy difficulty:")
    for diff in ("surface", "exploratory", "deep", "research"):
        subset = [q for q in all_q if q["difficulty"] == diff]
        if subset:
            p = sum(1 for q in subset if q["answerable_score"] >= 0.8)
            print(f"  {diff:<14}: {p/len(subset):.0%}")

    print("\nBy step type:")
    for st in ("concept", "practice", "challenge", "explore"):
        subset = [q for q in all_q if q["step_type"] == st]
        if subset:
            p = sum(1 for q in subset if q["answerable_score"] >= 0.8)
            print(f"  {st:<12}: {p/len(subset):.0%}")

    failures = [q for q in all_q if q["answerable_score"] < 0.8]
    if failures:
        print(f"\nTop gap patterns ({len(failures)} failures):")
        gaps = [q["gap"] for q in failures if q.get("gap")]
        for i, g in enumerate(gaps[:8], 1):
            print(f"  {i}. {g[:120]}")


async def _diagnose_failures(failures: list[dict]) -> None:
    """Send failure gaps to Claude for pattern diagnosis (Phase 5)."""
    if not failures:
        print("\nNo failures to diagnose.")
        return

    gaps_text = "\n".join(
        f"- [{f['step_type']}/{f['difficulty']}] {f.get('gap', '')}"
        for f in failures
        if f.get("gap")
    )

    diagnosis_prompt = (
        f"Here are {len(failures)} content+quiz pairs where the quiz question "
        f"scored < 0.8 answerability. Each has a gap describing what the content "
        f"doesn't cover.\n\nGaps:\n{gaps_text}\n\n"
        "Identify:\n"
        "1. The 3–5 most common gap PATTERNS (abstract the pattern, not just list gaps)\n"
        "2. For each pattern: is it caused by the CONTENT prompt, the QUIZ prompt, or both?\n"
        "3. For each pattern: write ONE specific rule (1–2 sentences) that would prevent "
        "this failure if added to the responsible prompt.\n"
        "4. Rank patterns by frequency and impact.\n\n"
        "Be concrete. No generic advice like 'be more specific'. Name the exact rule with example wording."
    )

    diagnosis_system = "You are an educational AI prompt engineer. Diagnose prompt failure patterns from quiz alignment data."
    try:
        raw, _, _, _ = await complete_text(
            interaction_type="quiz",
            system=diagnosis_system,
            user_content=diagnosis_prompt,
            max_tokens=1200,
        )
        print("\n=== CLAUDE DIAGNOSIS ===")
        print(raw)
    except Exception as e:
        logger.error("Diagnosis call failed: %s", e)


async def run_evaluation(phase: str = "baseline", cluster_failures: bool = False, limit: int = 100) -> list[dict]:
    logger.info("Pulling test steps from DB (limit=%d)…", limit)
    steps = _pull_test_steps(limit)
    logger.info("Got %d steps with content", len(steps))

    results = []
    for i, step in enumerate(steps, 1):
        journey_id = step["journey_id"]
        step_id    = step["step_id"]
        content    = step["content"]
        step_type  = _extract_step_type(step["journey_steps_json"], step_id)

        logger.info("[%d/%d] %s/%s (%s)", i, len(steps), journey_id[:8], step_id[:8], step_type)

        # Use stored quiz sessions if available (avoids regenerating + spending tokens)
        quiz_data_list = _pull_quiz_sessions(journey_id, step_id)

        # If no stored questions, use a dummy UID to generate fresh ones
        if not quiz_data_list:
            try:
                quiz_set, _, _ = await generate_quiz_set(
                    uid="eval-bot",
                    concept=step_id,
                    context=content,
                    base_depth="exploratory",
                    num_questions=3,
                    journey_id=journey_id,
                    step_id=step_id,
                    step_type=step_type,
                )
                # Fetch the just-stored sessions to get correct_answer
                quiz_data_list = _pull_quiz_sessions(journey_id, step_id)
            except Exception as e:
                logger.warning("  generate failed: %s", e)
                continue

        if not quiz_data_list:
            continue

        record = {
            "step_id":            step_id,
            "journey_id":         journey_id,
            "step_type":          step_type,
            "journey_difficulty": step.get("journey_difficulty", "beginner"),
            "age_group":          step.get("age_group", "adults"),
        }

        for j, qdata in enumerate(quiz_data_list[:3], 1):
            question      = qdata.get("question", "")
            correct_answer = qdata.get("correct_answer", "")
            difficulty    = qdata.get("difficulty", "exploratory")
            if not question:
                continue

            result = await _judge_question(content, question, correct_answer)
            record[f"question_{j}"] = {
                "question":        question,
                "correct_answer":  correct_answer,
                "difficulty":      difficulty,
                "answerable_score": result.get("answerable_score", 0),
                "gap":             result.get("gap", ""),
            }

        scores = [record[f"question_{j}"]["answerable_score"] for j in range(1, 4) if f"question_{j}" in record]
        record["avg_score"] = sum(scores) / len(scores) if scores else 0
        results.append(record)

    out_path = Path(__file__).parent / f"alignment_{phase}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results written to %s", out_path)

    _print_summary(results, label=f"ALIGNMENT — {phase.upper()}")

    if cluster_failures:
        all_failures = []
        for r in results:
            for key in ("question_1", "question_2", "question_3"):
                q = r.get(key)
                if q and q.get("answerable_score", 1) < 0.8:
                    all_failures.append({
                        "step_type":  r["step_type"],
                        "difficulty": q.get("difficulty", ""),
                        "gap":        q.get("gap", ""),
                    })
        await _diagnose_failures(all_failures)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quiz alignment evaluator")
    parser.add_argument("--phase",           default="baseline", help="Label for output file (e.g. baseline, phase1, phase5)")
    parser.add_argument("--cluster-failures", action="store_true", help="Run Claude diagnosis on failures (Phase 5)")
    parser.add_argument("--limit",           type=int, default=100, help="Max steps to evaluate")
    args = parser.parse_args()

    asyncio.run(run_evaluation(
        phase=args.phase,
        cluster_failures=args.cluster_failures,
        limit=args.limit,
    ))
