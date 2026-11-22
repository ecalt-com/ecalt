"""F1.1: an unanswered quiz set is reused instead of regenerated. Real SQL."""
import json

import pytest

from app.services.quiz_service import find_reusable_quiz_set

pytestmark = pytest.mark.schools_db


def _set(db, uid, set_id, n=3, journey="j1", step="s1", submitted=(), age_hours=0, hints=0):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES (%s, %s) ON CONFLICT DO NOTHING", (uid, f"{uid}@x.com"))
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours) VALUES (%s, %s, 't', 'q', 'd', 1) ON CONFLICT DO NOTHING", (journey, uid))
        for i in range(n):
            q = {"question": f"Q{i}?", "difficulty": "exploratory", "intro_phrase": "hi", "concept_tested": f"c{i}"}
            cur.execute(
                "INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id, quiz_set_id, submitted, "
                "hints_given, created_at) VALUES (%s,'c',%s::jsonb,%s,%s,%s,%s,%s, now() - make_interval(hours => %s) "
                "+ make_interval(secs => %s))",
                (uid, json.dumps(q), journey, step, set_id, i in submitted, hints if i == 0 else 0, age_hours, i))


def test_reuses_the_same_questions_in_order(db):
    _set(db, "u1", "11111111-1111-1111-1111-111111111111", hints=2)
    got = find_reusable_quiz_set("u1", "j1", "s1")
    assert got["reused"] is True
    assert [q["question"] for q in got["questions"]] == ["Q0?", "Q1?", "Q2?"]
    assert got["questions"][0]["hint_available"] == 1 and got["questions"][1]["hint_available"] == 3
    assert got["pass_threshold"] == 2


def test_picks_the_newest_unanswered_set(db):
    _set(db, "u1", "11111111-1111-1111-1111-111111111111", age_hours=5)
    _set(db, "u1", "22222222-2222-2222-2222-222222222222", age_hours=1)
    assert find_reusable_quiz_set("u1", "j1", "s1")["quiz_set_id"] == "22222222-2222-2222-2222-222222222222"


def test_a_set_with_any_answer_is_consumed(db):
    _set(db, "u1", "11111111-1111-1111-1111-111111111111", submitted=(1,))
    assert find_reusable_quiz_set("u1", "j1", "s1") is None


def test_old_sets_other_steps_and_other_users_are_not_reused(db):
    _set(db, "u1", "11111111-1111-1111-1111-111111111111", age_hours=30)
    assert find_reusable_quiz_set("u1", "j1", "s1") is None
    _set(db, "u1", "22222222-2222-2222-2222-222222222222", step="s2")
    assert find_reusable_quiz_set("u1", "j1", "s1") is None
    assert find_reusable_quiz_set("someone-else", "j1", "s2") is None
