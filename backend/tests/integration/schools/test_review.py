"""F1.3: spaced review. Real SQL."""
import json

import pytest

from app.services import quiz_service, review_service as svc
from tests.schools.identity import bearer

pytestmark = pytest.mark.schools_db


def _world(db, with_questions=2):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('u1','u1@x.com') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                    "VALUES ('j1','u1','Black holes','q','d',1,'[]'::jsonb) ON CONFLICT DO NOTHING")
        for i in range(with_questions):
            q = {"question": f"Q{i}?", "correct_answer": "42", "answer_explanation": "because",
                 "difficulty": "exploratory", "intro_phrase": "hi", "concept_tested": f"c{i}"}
            cur.execute("INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id, quiz_set_id, submitted) "
                        "VALUES ('u1','c',%s::jsonb,'j1','s1', gen_random_uuid(), true) RETURNING id", (json.dumps(q),))
            sid = cur.fetchone()[0]
            cur.execute("INSERT INTO quiz_results (uid, concept, difficulty, is_correct, session_id, journey_id, step_id) "
                        "VALUES ('u1','c','exploratory',%s,%s,'j1','s1')", (i == 1, sid))


def _item(db):
    with db.cursor() as cur:
        cur.execute("SELECT id::text, box, due_at > now(), last_result FROM review_items WHERE uid='u1'")
        return cur.fetchone()


def _make_due(db):
    with db.cursor() as cur:
        cur.execute("UPDATE review_items SET due_at = now() - interval '1 minute'")


def test_box_transitions():
    assert [svc.next_box(b, True) for b in (1, 2, 3, 4, 5)] == [2, 3, 4, 5, 5]
    assert [svc.next_box(b, False) for b in (1, 3, 5)] == [1, 1, 1]


def test_seed_is_idempotent_and_due_tomorrow(db):
    _world(db)
    svc.seed_item("u1", "j1", "s1", "Event horizons")
    svc.seed_item("u1", "j1", "s1", "changed")
    with db.cursor() as cur:
        cur.execute("SELECT count(*), min(concept), bool_and(due_at > now() + interval '20 hours') FROM review_items")
        assert cur.fetchone() == (1, "Event horizons", True)
    assert svc.due_items("u1")["due_count"] == 0


def test_due_items_lists_only_due_ones_oldest_first(db):
    _world(db)
    svc.seed_item("u1", "j1", "s1", "Event horizons")
    svc.seed_item("u1", "j1", "s2", "Other")
    _make_due(db)
    with db.cursor() as cur:
        cur.execute("UPDATE review_items SET due_at = now() - interval '2 days' WHERE step_id = 's2'")
    out = svc.due_items("u1")
    assert out["due_count"] == 2 and [i["step_id"] for i in out["items"]] == ["s2", "s1"]
    assert out["items"][1]["journey_title"] == "Black holes"
    assert svc.due_items("u1", limit=0) == {"due_count": 2, "items": []}


def test_start_prefers_a_missed_question_and_never_touches_the_step_gate(db):
    _world(db)
    svc.seed_item("u1", "j1", "s1", "x")
    _make_due(db)
    item_id = _item(db)[0]
    q = svc.start_item("u1", item_id)
    assert q["question"] == "Q0?" and "correct_answer" not in q       # Q0 was answered wrong
    with db.cursor() as cur:
        cur.execute("SELECT quiz_set_id, submitted FROM quiz_sessions WHERE id = %s", (q["quiz_id"],))
        assert cur.fetchone() == (None, False)
    assert svc.quiz_belongs_to_item("u1", item_id, q["quiz_id"])
    assert not svc.quiz_belongs_to_item("someone", item_id, q["quiz_id"])
    assert svc.start_item("someone", item_id) is None


def test_start_returns_none_without_stored_questions(db):
    _world(db, with_questions=0)
    svc.seed_item("u1", "j1", "s1", "x")
    assert svc.start_item("u1", _item(db)[0]) is None


def test_apply_result_moves_boxes_and_schedules(db):
    _world(db)
    svc.seed_item("u1", "j1", "s1", "x")
    iid = _item(db)[0]
    assert svc.apply_result("u1", iid, True) == {"box": 2, "next_review_in_days": 3}
    assert svc.apply_result("u1", iid, True) == {"box": 3, "next_review_in_days": 7}
    assert svc.apply_result("u1", iid, False) == {"box": 1, "next_review_in_days": 1}
    assert _item(db)[3] == "incorrect"
    assert svc.apply_result("u1", "00000000-0000-0000-0000-000000000000", True) is None
    assert svc.apply_result("someone", iid, True) is None


def test_api_flow_today_start_answer(client, db, monkeypatch):
    _world(db)
    svc.seed_item("u1", "j1", "s1", "Event horizons")
    _make_due(db)

    async def fake_grade(question, correct, answer):
        return "excellent", "nice", None
    monkeypatch.setattr(quiz_service, "_llm_grade_and_explain", fake_grade)

    h = bearer("u1")
    today = client.get("/api/v1/review/today", headers=h).json()
    assert today["due_count"] == 1
    item_id = today["items"][0]["item_id"]
    q = client.post(f"/api/v1/review/{item_id}/start", headers=h).json()
    assert client.post(f"/api/v1/review/{item_id}/answer", headers=h,
                       json={"quiz_id": "00000000-0000-0000-0000-000000000000", "user_answer": "x"}).status_code == 404
    r = client.post(f"/api/v1/review/{item_id}/answer", headers=h, json={"quiz_id": q["quiz_id"], "user_answer": "The answer is forty two."})
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is True and body["box"] == 2 and body["correct_answer"] == "42"
    assert client.get("/api/v1/review/today", headers=h).json()["due_count"] == 0
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM learning_events WHERE event = 'review_answer'")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT streak_days FROM users WHERE uid = 'u1'")
        assert (cur.fetchone()[0] or 0) >= 1
    # answered twice is refused
    assert client.post(f"/api/v1/review/{item_id}/answer", headers=h,
                       json={"quiz_id": q["quiz_id"], "user_answer": "The answer is forty two."}).status_code == 400


def test_completing_a_step_seeds_a_review_item(client, db):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('u2','u2@x.com') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                    "VALUES ('jj','u2','T','q','d',1, %s::jsonb)",
                    (json.dumps([{"id": "s1", "title": "Orbits", "type": "concept", "description": "d",
                                  "estimated_minutes": 5}]),))
        cur.execute("INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id, quiz_set_id, submitted) "
                    "VALUES ('u2','c','{}'::jsonb,'jj','s1', gen_random_uuid(), true)")
    r = client.post("/api/v1/quiz/step-skip/jj/s1", headers=bearer("u2"))
    assert r.status_code == 200
    r = client.post("/api/v1/progress/jj/s1", headers=bearer("u2"))
    assert r.status_code == 200, r.text
    with db.cursor() as cur:
        cur.execute("SELECT concept, box FROM review_items WHERE uid = 'u2'")
        assert cur.fetchone() == ("Orbits", 1)


def _pref(db, uid, email_enabled=True):
    with db.cursor() as cur:
        cur.execute("INSERT INTO notification_preferences (uid, email_enabled, preferred_channel) "
                    "VALUES (%s, %s, 'email') ON CONFLICT (uid) DO UPDATE SET email_enabled = EXCLUDED.email_enabled",
                    (uid, email_enabled))


def test_review_due_nudge_queues_once_for_opted_in_learners_with_due_items(db):
    import asyncio
    from app.services import scheduler as sch
    _world(db)
    svc.seed_item("u1", "j1", "s1", "Event horizons")
    _make_due(db)
    asyncio.run(sch._review_due_nudge())            # no preferences row: not opted in
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM notification_queue")
        assert cur.fetchone()[0] == 0
    _pref(db, "u1")
    asyncio.run(sch._review_due_nudge())
    asyncio.run(sch._review_due_nudge())            # already queued: no duplicate
    with db.cursor() as cur:
        cur.execute("SELECT notification_type, payload->>'concept', (payload->>'due_count')::int FROM notification_queue")
        assert cur.fetchall() == [("review_due", "Event horizons", 1)]
    _pref(db, "u1", email_enabled=False)
    with db.cursor() as cur:
        cur.execute("DELETE FROM notification_queue")
    asyncio.run(sch._review_due_nudge())
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM notification_queue")
        assert cur.fetchone()[0] == 0


def test_nothing_is_queued_when_nothing_is_due(db):
    import asyncio
    from app.services import scheduler as sch
    _world(db)
    _pref(db, "u1")
    svc.seed_item("u1", "j1", "s1", "x")            # due tomorrow
    asyncio.run(sch._review_due_nudge())
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM notification_queue")
        assert cur.fetchone()[0] == 0
