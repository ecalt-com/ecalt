"""F1.5: QUIZ_GATE_MODE decides whether a step needs its quiz. Real SQL."""
import json

import pytest

from app.core.config import settings
from tests.schools.identity import bearer

pytestmark = pytest.mark.schools_db


def _world(db):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('u1','u1@x.com') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                    "VALUES ('j1','u1','T','q','d',1,%s::jsonb)",
                    (json.dumps([{"id": "s1", "title": "Orbits", "type": "concept", "description": "d", "estimated_minutes": 5}]),))


def test_required_mode_blocks_completion_without_a_passed_quiz(client, db, monkeypatch):
    monkeypatch.setattr(settings, "QUIZ_GATE_MODE", "required")
    _world(db)
    r = client.post("/api/v1/progress/j1/s1", headers=bearer("u1"))
    assert r.status_code == 412 and r.json()["detail"]["message"] == "quiz_not_passed"


def test_optional_mode_lets_mark_as_read_complete_the_step_and_queues_a_review(client, db, monkeypatch):
    monkeypatch.setattr(settings, "QUIZ_GATE_MODE", "optional")
    _world(db)
    r = client.post("/api/v1/progress/j1/s1", headers=bearer("u1"))
    assert r.status_code == 200 and r.json()["completed"] is True
    with db.cursor() as cur:
        cur.execute("SELECT concept, box FROM review_items WHERE uid = 'u1'")
        assert cur.fetchone() == ("Orbits", 1)
        cur.execute("SELECT props->>'method', count(*) FROM learning_events WHERE event = 'step_complete' GROUP BY 1")
        assert cur.fetchall() == [("read", 1)]
        cur.execute("SELECT count(*) FROM learning_events WHERE event = 'journey_complete'")
        assert cur.fetchone()[0] == 1


def test_optional_mode_still_enforces_step_order(client, db, monkeypatch):
    monkeypatch.setattr(settings, "QUIZ_GATE_MODE", "optional")
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('u1','u1@x.com') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                    "VALUES ('j2','u1','T','q','d',1,%s::jsonb)",
                    (json.dumps([{"id": f"s{i}", "title": f"S{i}", "type": "concept", "description": "d", "estimated_minutes": 5} for i in (1, 2)]),))
    assert client.post("/api/v1/progress/j2/s2", headers=bearer("u1")).status_code == 409


def test_public_config_reports_the_mode(client, monkeypatch):
    for mode, expected in (("required", "required"), ("optional", "optional"), ("anything", "required")):
        monkeypatch.setattr(settings, "QUIZ_GATE_MODE", mode)
        body = client.get("/api/v1/config/public").json()
        assert body["quiz_gate_mode"] == expected
        assert {"code": "hi", "name": "Hindi"} in body["languages"]
