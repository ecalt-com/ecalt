"""INV-03 + ISO-10..18 (invariant I3): who may reach a school course through the
learner endpoints (SC-107).

Every learner endpoint that takes a journey id is called on course C1 (school
A, assigned to class A1) by people who must not see it. Each call must be a
404 (or the student allowlist's 403), make no model call and write no
step_content.
"""
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db

VISUAL_EVENT = {"eventType": "visual_impression", "vloId": "vlo-1", "sessionId": "s-1", "eventData": {}}

# (id, method, path template, body, allowlisted for students)
LEARNER_ENDPOINTS = [
    ("ISO-10 journey", "GET", "/api/v1/journeys/{j}", None, True),
    ("ISO-11 content", "GET", "/api/v1/journeys/{j}/steps/{s}/content", None, True),
    ("ISO-11 regenerate", "POST", "/api/v1/journeys/{j}/steps/{s}/content/regenerate", None, False),
    ("ISO-12 feedback", "POST", "/api/v1/journeys/{j}/steps/{s}/feedback",
     {"rating": "down", "tag": "too_basic"}, True),
    ("ISO-13 visual", "GET", "/api/v1/journeys/{j}/steps/{s}/visual", None, True),
    ("ISO-13 visual events", "POST", "/api/v1/journeys/{j}/steps/{s}/visual/events", VISUAL_EVENT, True),
    ("ISO-14 quiz", "POST", "/api/v1/quiz",
     {"concept": "c", "context": "ctx", "journey_id": "{j}", "step_id": "{s}"}, True),
    ("ISO-14 quiz status", "GET", "/api/v1/quiz/step-status/{j}/{s}", None, True),
    ("ISO-14 quiz skip", "POST", "/api/v1/quiz/step-skip/{j}/{s}", None, False),
    ("ISO-15 progress", "GET", "/api/v1/progress/{j}", None, True),
    ("ISO-15 complete", "POST", "/api/v1/progress/{j}/{s}", None, True),
    ("ISO-15 uncomplete", "DELETE", "/api/v1/progress/{j}/{s}", None, True),
    ("ISO-16 tutor", "POST", "/api/v1/chat/stream",
     {"message": "hi", "interaction_type": "journey_tutor", "journey_id": "{j}", "step_id": "{s}"}, True),
    ("ISO-17 suggestions", "GET", "/api/v1/journeys/{j}/suggestions", None, False),
    ("ISO-18 like", "POST", "/api/v1/journeys/{j}/like", None, False),
    ("ISO-18 fork", "POST", "/api/v1/journeys/{j}/fork", None, False),
    ("ISO-18 submit", "POST", "/api/v1/journeys/{j}/submit-to-marketplace", None, False),
]

OUTSIDERS = ["S2", "SX", "XS", "OUT", "PRF", "XA", "ADM", "ANON"]


def _fill(value, journey_id, step_id):
    if isinstance(value, str):
        return value.replace("{j}", journey_id).replace("{s}", step_id)
    if isinstance(value, dict):
        return {k: _fill(v, journey_id, step_id) for k, v in value.items()}
    return value


def _call(client, world, persona, method, path, body, journey_id, step_id):
    return client.request(method, _fill(path, journey_id, step_id), json=_fill(body, journey_id, step_id),
                          headers=world.headers(persona))


@pytest.fixture
def ai(monkeypatch):
    """Every model entry point the learner endpoints can reach; none may run."""
    mocks = {
        "app.api.v1.endpoints.journeys.generate_step_content": AsyncMock(side_effect=AssertionError("model call")),
        "app.api.v1.endpoints.journeys.generate_next_level": AsyncMock(side_effect=AssertionError("model call")),
        "app.api.v1.endpoints.quiz.generate_quiz_set": AsyncMock(side_effect=AssertionError("model call")),
        "app.api.v1.endpoints.quiz.generate_quiz": AsyncMock(side_effect=AssertionError("model call")),
        "app.api.v1.endpoints.chat.stream_chat": MagicMock(side_effect=AssertionError("model call")),
    }
    for target, mock in mocks.items():
        monkeypatch.setattr(target, mock)
    return mocks


def _step_content_digest(db) -> str:
    rows = f.fetch(db, "SELECT journey_id, step_id, content, locked FROM step_content ORDER BY journey_id, step_id")
    return hashlib.sha256(repr(rows).encode()).hexdigest()


@pytest.mark.parametrize("persona", OUTSIDERS)
@pytest.mark.parametrize("name,method,path,body,student_ok", LEARNER_ENDPOINTS,
                         ids=[e[0] for e in LEARNER_ENDPOINTS])
def test_outsiders_cannot_reach_a_school_course(client, world, db, ai, persona, name, method, path, body, student_ok):
    step = f.step_ids(db, world.C1)[0]
    before = _step_content_digest(db)

    r = _call(client, world, persona, method, path, body, world.C1, step)

    is_student = persona in ("S2", "SX", "XS")
    if persona == "ANON" and method != "GET" or persona == "ANON" and name.startswith(("ISO-11", "ISO-13", "ISO-14", "ISO-15", "ISO-17")):
        assert r.status_code == 401, r.text
    elif is_student and not student_ok:
        assert r.status_code == 403 and r.json()["detail"]["error"] == "school_student_not_allowed", r.text
    else:
        assert r.status_code == 404, r.text
    assert all(m.call_count == 0 for m in ai.values())
    assert _step_content_digest(db) == before


@pytest.mark.parametrize("persona", ["S", "SA", "T", "T2"])
def test_entitled_people_read_the_published_course(client, world, db, persona):
    step = f.step_ids(db, world.C1)[0]
    r = client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers(persona))
    assert r.status_code == 200 and r.json()["title"] == "Photosynthesis"
    r = client.get(f"/api/v1/journeys/{world.C1}/steps/{step}/content", headers=world.headers(persona))
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "Published body of Step 1"


def test_student_learner_routes_work_on_an_assigned_course(client, world, db, ai):
    step = f.step_ids(db, world.C1)[0]
    h = world.headers("S")
    assert client.get(f"/api/v1/progress/{world.C1}", headers=h).json()["completed_step_ids"] == []
    assert client.get(f"/api/v1/quiz/step-status/{world.C1}/{step}", headers=h).status_code == 200
    assert client.get(f"/api/v1/journeys/{world.C1}/steps/{step}/visual", headers=h).json()["status"] == "pending"
    r = client.post(f"/api/v1/journeys/{world.C1}/steps/{step}/feedback",
                    json={"rating": "down", "tag": "too_basic"}, headers=h)
    assert r.status_code == 200 and r.json() == {"ok": True, "regenerating": False}


@pytest.mark.parametrize("journey_attr", ["N1", "curated"])
def test_students_cannot_open_non_school_journeys(client, world, db, journey_attr):
    journey_id = "journey-dna" if journey_attr == "curated" else world.N1
    for path in (f"/api/v1/journeys/{journey_id}", f"/api/v1/progress/{journey_id}"):
        r = client.get(path, headers=world.headers("S"))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["error"] == "school_student_not_allowed"


def test_student_journey_list_is_only_assigned_courses(client, world):
    r = client.get("/api/v1/journeys", headers=world.headers("S"))
    assert r.status_code == 200
    assert [j["id"] for j in r.json()["journeys"]] == [world.C1]
    r = client.get("/api/v1/journeys", headers=world.headers("S2"))
    assert r.json()["journeys"] == []


def test_school_courses_never_listed_for_staff_or_public(client, world):
    for persona in ("ANON", "OUT", "T"):
        ids = {j["id"] for j in client.get("/api/v1/journeys", headers=world.headers(persona)).json()["journeys"]}
        assert world.C1 not in ids and world.CB not in ids


def test_draft_course_is_hidden_even_when_assigned(client, world, db):
    f.assign(db, world.A1, world.C_DRAFT)
    r = client.get(f"/api/v1/journeys/{world.C_DRAFT}", headers=world.headers("S"))
    assert r.status_code == 404


def test_archived_assignment_and_archived_class_hide_the_course(client, world, db):
    f.fetch(db, "UPDATE course_assignments SET status = 'archived' WHERE journey_id = %s", (world.C1,))
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 404


def test_archived_student_is_blocked(client, world, db):
    f.fetch(db, "UPDATE school_students SET status = 'archived' WHERE uid = %s", (world.S,))
    step = f.step_ids(db, world.C1)[0]
    r = client.get(f"/api/v1/journeys/{world.C1}/steps/{step}/content", headers=world.headers("S"))
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "school_access_suspended"


def test_suspended_school_blocks_students_and_hides_course_from_staff(client, world, db):
    f.fetch(db, "UPDATE schools SET status = 'suspended' WHERE id = %s", (world.school_a["id"],))
    step = f.step_ids(db, world.C1)[0]
    r = client.get(f"/api/v1/journeys/{world.C1}/steps/{step}/content", headers=world.headers("S"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_access_suspended"
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("T")).status_code == 404


def test_student_quiz_requires_an_assigned_step(client, world):
    r = client.post("/api/v1/quiz", json={"concept": "c", "context": "ctx"}, headers=world.headers("S"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_student_not_allowed"


def test_student_chat_is_tutor_only(client, world):
    for body in ({"message": "hi"}, {"message": "hi", "interaction_type": "journey_tutor"}):
        r = client.post("/api/v1/chat/stream", json=body, headers=world.headers("S"))
        assert r.status_code == 403 and r.json()["detail"]["error"] == "school_student_not_allowed"


def test_non_school_journeys_unchanged_for_other_users(client, world, db):
    step = f.step_ids(db, world.N1)[0]
    for persona in ("OUT", "T", "PRF", "ANON"):
        assert client.get(f"/api/v1/journeys/{world.N1}", headers=world.headers(persona)).status_code == 200
    r = client.get(f"/api/v1/journeys/{world.N1}/steps/{step}/content", headers=world.headers("T"))
    assert r.status_code == 200 and r.json()["content"] == "AI body of Step 1"
