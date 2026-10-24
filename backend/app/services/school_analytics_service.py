"""Teacher analytics for schools (plans/school-courses M7, §10).

Read-only views over data other parts of the app already write:

- **Student drill-down** (SC-701): per assigned course, a student's step
  completion plus quiz attempts / accuracy / hints from ``quiz_results``, with
  "struggling" flags (SC-702).
- **CSV export** (SC-704): the class progress matrix as a spreadsheet, with
  formula-injection escaping (SEC-12).
- **Usage overview** (SC-706, admins): the school's monthly AI budget and spend
  plus today's per-student usage against the daily caps.

Tutor-transcript visibility (SC-703, decision D4) and the weekly digest (SC-705)
are separate tickets.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import SchoolCtx, load_class
from app.services.school_service import effective_settings


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


# ── SC-702: struggling flags (pure logic, unit-tested) ───────────────────────

def struggle_flags(stats: dict) -> list[str]:
    """Which "needs attention" flags a student's work on one course raises.

    ``stats`` carries only numbers so this stays a pure function:
    ``overdue`` (bool), ``attempts`` (quiz questions answered), ``accuracy``
    (0..1 or None), ``hints`` (total hints used), ``quizzed_steps`` (steps with
    ≥1 attempt), ``stalled`` (started, not done, idle a while)."""
    flags: list[str] = []
    if stats.get("overdue"):
        flags.append("overdue")
    accuracy = stats.get("accuracy")
    if stats.get("attempts", 0) >= 3 and accuracy is not None and accuracy < 0.5:
        flags.append("low_quiz_accuracy")
    quizzed = stats.get("quizzed_steps", 0)
    if quizzed >= 2 and stats.get("hints", 0) / quizzed >= 2:
        flags.append("heavy_hints")
    if stats.get("stalled"):
        flags.append("stalled")
    return flags


# ── SC-701: student drill-down ────────────────────────────────────────────────

def student_drilldown(ctx: SchoolCtx, class_id: str, student_uid: str) -> dict:
    """One student's progress across the class's assigned courses: per-step
    completion + quiz attempts/accuracy/hints, course totals, and flags."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cls = load_class(ctx, class_id, cur=cur)
            cur.execute(
                """
                SELECT s.uid, s.display_name, s.avatar, s.grade
                  FROM class_enrollments e
                  JOIN school_students s ON s.uid = e.student_uid AND s.status = 'active'
                 WHERE e.class_id = %s AND e.student_uid = %s AND e.removed_at IS NULL
                """,
                (cls["id"], student_uid),
            )
            student = cur.fetchone()
            if not student:
                raise HTTPException(status_code=404, detail={
                    "error": "student_not_found",
                    "message": "This student isn't in this class.",
                })
            cur.execute(
                """
                SELECT a.id, a.journey_id, a.due_at, j.title, j.icon,
                       COALESCE(j.steps, '[]'::jsonb) AS steps
                  FROM course_assignments a
                  JOIN journeys j ON j.id = a.journey_id
                 WHERE a.class_id = %s AND a.school_id = %s AND a.status = 'active'
                 ORDER BY a.assigned_at DESC
                """,
                (cls["id"], ctx.school_id),
            )
            assignments = cur.fetchall()
            journey_ids = [a["journey_id"] for a in assignments]
            progress: dict[tuple, datetime] = {}
            quiz: dict[tuple, dict] = {}
            if journey_ids:
                cur.execute(
                    "SELECT journey_id, step_id, completed_at FROM user_progress "
                    "WHERE uid = %s AND journey_id = ANY(%s)",
                    (student_uid, journey_ids),
                )
                for r in cur.fetchall():
                    progress[(r["journey_id"], r["step_id"])] = r["completed_at"]
                cur.execute(
                    """
                    SELECT journey_id, step_id,
                           COUNT(*) FILTER (WHERE NOT skipped) AS attempts,
                           COUNT(*) FILTER (WHERE is_correct)  AS correct,
                           COALESCE(SUM(hints_used), 0)        AS hints,
                           MAX(answered_at)                     AS last_answered
                      FROM quiz_results
                     WHERE uid = %s AND journey_id = ANY(%s)
                     GROUP BY journey_id, step_id
                    """,
                    (student_uid, journey_ids),
                )
                for r in cur.fetchall():
                    quiz[(r["journey_id"], r["step_id"])] = r

    now = datetime.now(timezone.utc)
    courses = []
    for a in assignments:
        steps_meta = a["steps"] or []
        total = len(steps_meta)
        done = 0
        last_active: Optional[datetime] = None
        attempts_sum = correct_sum = hints_sum = quizzed_steps = 0
        step_rows = []
        for st in steps_meta:
            sid = st.get("id")
            comp_at = progress.get((a["journey_id"], sid))
            q = quiz.get((a["journey_id"], sid))
            if comp_at is not None:
                done += 1
            attempts = int(q["attempts"]) if q else 0
            correct = int(q["correct"]) if q else 0
            hints = int(q["hints"]) if q else 0
            last_answered = q["last_answered"] if q else None
            for t in (comp_at, last_answered):
                if t and (last_active is None or t > last_active):
                    last_active = t
            if attempts:
                attempts_sum += attempts
                correct_sum += correct
                hints_sum += hints
                quizzed_steps += 1
            step_rows.append({
                "step_id": sid,
                "title": st.get("title"),
                "completed": comp_at is not None,
                "completed_at": _iso(comp_at),
                "quiz_attempts": attempts,
                "quiz_correct": correct,
                "hints_used": hints,
                "last_answered": _iso(last_answered),
            })
        completed = total > 0 and done >= total
        overdue = bool(a["due_at"] and not completed and a["due_at"] < now)
        accuracy = (correct_sum / attempts_sum) if attempts_sum else None
        stalled = bool(done > 0 and not completed and last_active
                       and (now - last_active) > timedelta(days=7))
        flags = struggle_flags({
            "overdue": overdue, "attempts": attempts_sum, "accuracy": accuracy,
            "hints": hints_sum, "quizzed_steps": quizzed_steps, "stalled": stalled,
        })
        courses.append({
            "assignment_id": str(a["id"]),
            "journey_id": a["journey_id"],
            "title": a["title"],
            "icon": a["icon"],
            "total_steps": total,
            "done_steps": done,
            "percent": round(done / total * 100) if total else 0,
            "completed": completed,
            "overdue": overdue,
            "due_at": _iso(a["due_at"]),
            "last_active": _iso(last_active),
            "quiz_accuracy": round(accuracy * 100) if accuracy is not None else None,
            "flags": flags,
            "steps": step_rows,
        })

    return {
        "student": {
            "uid": student["uid"],
            "display_name": student["display_name"],
            "avatar": student["avatar"],
            "grade": student["grade"],
        },
        "courses": courses,
    }


# ── SC-704: CSV export (formula-injection safe) ──────────────────────────────

def csv_escape(value) -> str:
    """One CSV field, escaped for both CSV syntax and spreadsheet formula
    injection (SEC-12): a leading =, +, -, @ or tab/CR is neutralised with a
    leading apostrophe; separators/quotes/newlines force quoting."""
    s = "" if value is None else str(value)
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    if any(c in s for c in (",", '"', "\n", "\r")):
        s = '"' + s.replace('"', '""') + '"'
    return s


def class_progress_csv(ctx: SchoolCtx, class_id: str) -> str:
    """The class progress matrix as RFC-4180 CSV (CRLF rows)."""
    from app.services.school_assignment_service import class_progress_matrix
    data = class_progress_matrix(ctx, class_id)
    courses = data["courses"]
    header = ["Student", "Grade"] + [c["title"] for c in courses]
    rows = [[s["display_name"], s["grade"]] + [
        (lambda cell: f"{cell['done']}/{cell['total']}" if cell else "")(s["cells"].get(c["journey_id"]))
        for c in courses
    ] for s in data["students"]]
    lines = [",".join(csv_escape(x) for x in header)]
    lines += [",".join(csv_escape(x) for x in row) for row in rows]
    return "\r\n".join(lines) + "\r\n"


# ── SC-706: school usage overview (admins) ───────────────────────────────────

def school_usage_overview(ctx: SchoolCtx) -> dict:
    """The school's AI budget + spend this month, recent monthly history, and
    today's per-student usage against the daily caps. Per-class/per-course spend
    is not tracked yet (usage isn't attributed to a journey), so it is omitted."""
    today = date.today()
    period_start = today.replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT monthly_ai_budget_cents, settings FROM schools WHERE id = %s", (ctx.school_id,))
            srow = cur.fetchone()
            budget = float(srow["monthly_ai_budget_cents"] or 0) if srow else 0.0
            settings = effective_settings(srow["settings"] if srow else {})
            cur.execute(
                "SELECT cost_cents FROM school_usage WHERE school_id = %s AND period_start = %s",
                (ctx.school_id, period_start),
            )
            u = cur.fetchone()
            spent = float(u["cost_cents"]) if u else 0.0
            cur.execute(
                "SELECT period_start, cost_cents, input_tokens, output_tokens FROM school_usage "
                "WHERE school_id = %s ORDER BY period_start DESC LIMIT 6",
                (ctx.school_id,),
            )
            history = [{
                "period_start": r["period_start"].isoformat(),
                "cost_cents": float(r["cost_cents"]),
                "input_tokens": int(r["input_tokens"]),
                "output_tokens": int(r["output_tokens"]),
            } for r in cur.fetchall()]
            cur.execute(
                """
                SELECT d.student_uid, s.display_name, d.tutor_messages, d.quiz_sets
                  FROM school_student_daily_usage d
                  LEFT JOIN school_students s ON s.uid = d.student_uid
                 WHERE d.school_id = %s AND d.day = %s
                   AND (d.tutor_messages > 0 OR d.quiz_sets > 0)
                 ORDER BY (d.tutor_messages + d.quiz_sets) DESC
                 LIMIT 20
                """,
                (ctx.school_id, today),
            )
            today_usage = [{
                "student_uid": r["student_uid"],
                "display_name": r["display_name"],
                "tutor_messages": int(r["tutor_messages"]),
                "quiz_sets": int(r["quiz_sets"]),
            } for r in cur.fetchall()]

    return {
        "period_start": period_start.isoformat(),
        "budget_cents": budget,
        "spent_cents": spent,
        "percent": round(spent / budget * 100) if budget else 0,
        "caps": {
            "student_daily_tutor_messages": settings["student_daily_tutor_messages"],
            "student_daily_quiz_sets": settings["student_daily_quiz_sets"],
        },
        "today": today_usage,
        "history": history,
    }
