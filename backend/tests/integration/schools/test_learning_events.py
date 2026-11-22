"""F1.2: learning funnel events. Real SQL."""
import json

import pytest

from app.services import learning_events_service as svc
from tests.schools.identity import bearer

pytestmark = pytest.mark.schools_db


def _user(db, uid):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES (%s, %s) ON CONFLICT DO NOTHING", (uid, f"{uid}@x.com"))


def _journey(db, uid, steps):
    with db.cursor() as cur:
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                    "VALUES ('j1', %s, 't', 'q', 'd', 1, %s::jsonb)", (uid, json.dumps([{"id": s} for s in steps])))


def _count(db):
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM learning_events")
        return cur.fetchone()[0]


def test_only_allowlisted_small_events_are_stored(db):
    _user(db, "u1")
    stored = svc.record_events("u1", [
        {"event": "step_open", "journey_id": "j1", "step_id": "s1"},
        {"event": "made_up_event"},
        {"event": "step_time", "props": {"x": "y" * 3000}},
        {"event": "quiz_view", "journey_id": "j" * 101},
        {"event": "quiz_ready", "props": {"ms": 900}},
    ])
    assert stored == 2 and _count(db) == 2


def test_guests_and_school_students_are_never_recorded(db):
    assert svc.record_events(None, [{"event": "step_open"}]) == 0
    assert svc.record_events("stu_abc", [{"event": "step_open"}]) == 0
    assert _count(db) == 0


def test_batch_is_capped(db):
    _user(db, "u1")
    assert svc.record_events("u1", [{"event": "step_open"}] * 50) == svc.MAX_BATCH


def test_api_accepts_a_batch_and_drops_junk_silently(client, db):
    _user(db, "u1")
    r = client.post("/api/v1/events", headers=bearer("u1"),
                    json={"events": [{"event": "step_open", "journey_id": "j1", "step_id": "s1"}, {"event": "nope"}]})
    assert r.status_code == 204 and _count(db) == 1
    assert client.post("/api/v1/events", json={"events": [{"event": "step_open"}]}).status_code == 204   # guest
    assert _count(db) == 1
    too_many = {"events": [{"event": "step_open"}] * 21}
    assert client.post("/api/v1/events", headers=bearer("u1"), json=too_many).status_code == 422


def test_funnel_counts_learners_per_step_position(db):
    for u in ("a", "b"):
        _user(db, u)
    _journey(db, "a", ["s1", "s2"])
    for u, evs in {"a": ["step_open", "step_scroll_90", "quiz_view", "quiz_answer", "step_complete"],
                   "b": ["step_open", "step_scroll_90", "quiz_view"]}.items():
        svc.record_events(u, [{"event": e, "journey_id": "j1", "step_id": "s1"} for e in evs])
    svc.record_events("a", [{"event": "quiz_ready", "props": {"ms": 1200}},
                            {"event": "step_open", "journey_id": "j1", "step_id": "s2"}])
    out = svc.funnel(30)
    first = out["by_step"][0]
    assert first["step_index"] == 0 and (first["opened"], first["read"], first["quiz_seen"],
                                         first["answered"], first["completed"]) == (2, 2, 2, 1, 1)
    assert out["by_step"][1]["opened"] == 1 and out["by_step"][1]["completed"] == 0
    assert out["quiz_generation"]["median_ms"] == 1200
    assert out["totals"]["learners"] == 2


def test_deleting_the_user_removes_their_events(db):
    _user(db, "u1")
    svc.record_events("u1", [{"event": "step_open"}])
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE uid = 'u1'")
    assert _count(db) == 0
