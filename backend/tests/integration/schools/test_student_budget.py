"""School-funded student AI budget (REVIEW.md H1, TRACKER SC-504 slice).

A school student has no subscription, so their AI use must be funded and capped
by their school — never the individual free-trial plan. These lock in:
  - students are not subject to free_trial (the tutor/quiz work);
  - the school monthly pool and per-student daily caps block when spent;
  - usage accrues to school_usage and the per-student daily counters.
"""
from datetime import date

import psycopg2.extras
import pytest

from app.services import subscription_service as sub
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db

_MONTH = date.today().replace(day=1)


def _school_usage(db, school_id) -> float:
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT cost_cents FROM school_usage WHERE school_id = %s AND period_start = %s",
                    (school_id, _MONTH))
        row = cur.fetchone()
    return float(row["cost_cents"]) if row else 0.0


def _daily(db, uid) -> tuple[int, int]:
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT tutor_messages, quiz_sets FROM school_student_daily_usage "
            "WHERE student_uid = %s AND day = (now() AT TIME ZONE 'UTC')::date", (uid,))
        row = cur.fetchone()
    return (int(row["tutor_messages"]), int(row["quiz_sets"])) if row else (0, 0)


def test_student_is_school_funded_not_free_trial(world):
    # School A has a budget (factory default) and no spend yet.
    assert sub.check_budget(world.S, context="chat") == (True, "ok")
    assert sub.check_budget(world.S, context="ai") == (True, "ok")


def test_student_blocked_when_school_has_no_budget(db):
    school = f.make_school(db, name="No Budget", budget_cents=0)
    stu = f.make_student(db, school)
    assert sub.check_budget(stu, context="chat") == (False, "school_budget_exhausted")
    assert sub.check_budget(stu, context="ai") == (False, "school_budget_exhausted")


def test_student_blocked_when_monthly_pool_spent(db):
    school = f.make_school(db, name="Small Budget", budget_cents=50)
    stu = f.make_student(db, school)
    assert sub.check_budget(stu, context="chat")[0] is True
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO school_usage (school_id, period_start, cost_cents) VALUES (%s, %s, %s)",
            (school["id"], _MONTH, 50),
        )
    sub.invalidate_student_school()
    assert sub.check_budget(stu, context="chat") == (False, "school_budget_exhausted")


def test_record_usage_accrues_to_school_and_daily_counter(db):
    school = f.make_school(db, name="Accrual", budget_cents=100_000)
    stu = f.make_student(db, school)
    sub.record_usage(stu, 1000, 1000, "gpt-4o-mini", interaction_type="journey_tutor")
    sub.record_usage(stu, 500, 500, "gpt-4o-mini", interaction_type="quiz")
    assert _school_usage(db, school["id"]) > 0
    assert _daily(db, stu) == (1, 1)


def test_student_daily_tutor_cap_is_independent_of_quiz(db):
    school = f.make_school(db, name="Capped", budget_cents=100_000,
                           settings={"student_daily_tutor_messages": 1, "student_daily_quiz_sets": 5})
    stu = f.make_student(db, school)
    sub.record_usage(stu, 10, 10, "gpt-4o-mini", interaction_type="journey_tutor")
    sub.invalidate_student_school()
    # Tutor cap (1) reached; quiz cap (5) still has room.
    assert sub.check_budget(stu, context="chat") == (False, "school_daily_limit_reached")
    assert sub.check_budget(stu, context="ai") == (True, "ok")


def test_budget_error_detail_shapes():
    school = sub.budget_error_detail("school_budget_exhausted")
    assert school["error"] == "school_budget_exhausted" and "message" in school and "upgrade_url" not in school
    daily = sub.budget_error_detail("school_daily_limit_reached")
    assert "message" in daily and "upgrade_url" not in daily
    # Ordinary users still get an upgrade link.
    assert sub.budget_error_detail("budget_exhausted")["upgrade_url"] == "/pricing"
