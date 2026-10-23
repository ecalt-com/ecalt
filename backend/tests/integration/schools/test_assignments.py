"""Course assignments, the student home, and settings enforcement
(plans/school-courses M5 §9, SC-501..503).

The world seeds school A with course C1 (published) assigned to class A1, and
student S enrolled in A1. C_DRAFT is an unpublished course of A.
"""
import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _courses_url(w, class_id):
    return f"/api/v1/schools/{w.school_a['id']}/classes/{class_id}/courses"


def _a1_c1_assignment(w, db) -> str:
    return f.fetch(db, "SELECT id::text AS id FROM course_assignments "
                       "WHERE class_id = %s AND journey_id = %s AND status = 'active'",
                   (w.A1["id"], w.C1))[0]["id"]


# ── SC-501: assign / validate ────────────────────────────────────────────────

def test_assign_a_published_course_to_a_class(client, world, db):
    journey_id = f.make_published_course(db, world.school_a)
    r = client.post(_courses_url(world, world.A2["id"]),
                    json={"journey_id": journey_id}, headers=world.headers("SA"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["journey_id"] == journey_id
    assert body["settings"] == {"tutor_enabled": True, "quiz_required": False}
    rows = f.fetch(db, "SELECT status FROM course_assignments WHERE class_id = %s AND journey_id = %s",
                   (world.A2["id"], journey_id))
    assert rows == [{"status": "active"}]


def test_cannot_assign_a_draft_course(client, world):
    r = client.post(_courses_url(world, world.A1["id"]),
                    json={"journey_id": world.C_DRAFT}, headers=world.headers("SA"))
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "course_not_published"


def test_cannot_assign_an_unknown_course(client, world):
    import uuid
    r = client.post(_courses_url(world, world.A1["id"]),
                    json={"journey_id": str(uuid.uuid4())}, headers=world.headers("SA"))
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "course_not_found"


def test_cannot_assign_the_same_course_twice(client, world):
    # C1 is already assigned to A1 by the world fixture.
    r = client.post(_courses_url(world, world.A1["id"]),
                    json={"journey_id": world.C1}, headers=world.headers("SA"))
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "already_assigned"


def test_assign_with_due_date_and_settings(client, world, db):
    journey_id = f.make_published_course(db, world.school_a)
    r = client.post(_courses_url(world, world.A2["id"]),
                    json={"journey_id": journey_id, "due_at": "2026-12-01T00:00:00Z",
                          "tutor_enabled": False, "quiz_required": True},
                    headers=world.headers("SA"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["settings"] == {"tutor_enabled": False, "quiz_required": True}
    assert body["due_at"].startswith("2026-12-01")


# ── SC-501: list with progress summary ───────────────────────────────────────

def test_list_assignments_shows_course_and_progress(client, world, db):
    r = client.get(_courses_url(world, world.A1["id"]), headers=world.headers("T"))
    assert r.status_code == 200, r.text
    items = r.json()["assignments"]
    assert len(items) == 1
    a = items[0]
    assert a["journey_id"] == world.C1 and a["title"] == "Photosynthesis"
    assert a["total_steps"] == 2
    # one student (S) enrolled, nothing done yet
    assert a["progress"] == {"enrolled": 1, "started": 0, "completed": 0, "avg_percent": 0}


def test_progress_summary_reflects_completion(client, world, db):
    step = f.step_ids(db, world.C1)[0]
    assert client.post(f"/api/v1/progress/{world.C1}/{step}", headers=world.headers("S")).status_code == 200
    a = client.get(_courses_url(world, world.A1["id"]), headers=world.headers("T")).json()["assignments"][0]
    # 1 of 2 steps done by the only enrollee → 50%
    assert a["progress"] == {"enrolled": 1, "started": 1, "completed": 0, "avg_percent": 50}


# ── SC-501: update / unassign ────────────────────────────────────────────────

def test_update_assignment_changes_settings(client, world, db):
    aid = _a1_c1_assignment(world, db)
    r = client.patch(f"{_courses_url(world, world.A1['id'])}/{aid}",
                     json={"tutor_enabled": False}, headers=world.headers("T"))
    assert r.status_code == 200, r.text
    assert r.json()["settings"] == {"tutor_enabled": False, "quiz_required": False}


def test_unassign_archives_and_revokes_student_access(client, world, db):
    aid = _a1_c1_assignment(world, db)
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 200
    r = client.delete(f"{_courses_url(world, world.A1['id'])}/{aid}", headers=world.headers("T"))
    assert r.status_code == 204, r.text
    assert f.fetch(db, "SELECT status FROM course_assignments WHERE id = %s", (aid,)) == [{"status": "archived"}]
    # student loses access to the course
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 404
    assert client.get(_courses_url(world, world.A1["id"]), headers=world.headers("T")).json()["assignments"] == []


def test_teacher_not_on_the_class_cannot_assign(client, world, db):
    journey_id = f.make_published_course(db, world.school_a)
    r = client.post(_courses_url(world, world.A1["id"]),
                    json={"journey_id": journey_id}, headers=world.headers("T2"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_role_required"


# ── SC-502: student home ──────────────────────────────────────────────────────

def test_student_home_lists_assigned_courses(client, world):
    r = client.get("/api/v1/school-student/home", headers=world.headers("S"))
    assert r.status_code == 200, r.text
    classes = r.json()["classes"]
    assert len(classes) == 1
    cls = classes[0]
    assert cls["class_name"] == "6A" and cls["teacher_name"] == world.T
    assert len(cls["courses"]) == 1
    course = cls["courses"][0]
    assert course["journey_id"] == world.C1 and course["title"] == "Photosynthesis"
    assert course["total_steps"] == 2 and course["done_steps"] == 0
    assert course["percent"] == 0 and course["completed"] is False


def test_student_home_reflects_progress(client, world, db):
    step = f.step_ids(db, world.C1)[0]
    client.post(f"/api/v1/progress/{world.C1}/{step}", headers=world.headers("S"))
    course = client.get("/api/v1/school-student/home",
                        headers=world.headers("S")).json()["classes"][0]["courses"][0]
    assert course["done_steps"] == 1 and course["percent"] == 50


def test_student_home_shows_class_without_courses(client, world):
    # S2 is in A2, which has no assignment — the class shows with no cards.
    r = client.get("/api/v1/school-student/home", headers=world.headers("S2"))
    classes = r.json()["classes"]
    assert len(classes) == 1 and classes[0]["courses"] == []


def test_student_home_empty_for_non_students(client, world):
    assert client.get("/api/v1/school-student/home", headers=world.headers("OUT")).json() == {"classes": []}


# ── SC-503: settings enforcement ──────────────────────────────────────────────

@pytest.fixture
def chat_stub(monkeypatch):
    """Let the tutor request through the budget/model layer so the test is
    about the tutor on/off gate alone."""
    async def _stream(**kwargs):
        yield "data: hi\n\n"
    monkeypatch.setattr("app.api.v1.endpoints.chat.stream_chat", _stream)
    monkeypatch.setattr("app.api.v1.endpoints.chat.check_budget", lambda uid, context="chat": (True, "ok"))
    monkeypatch.setattr("app.api.v1.endpoints.chat.ensure_chat_allowed", lambda uid: None)


def _tutor(client, world, journey_id):
    return client.post("/api/v1/chat/stream",
                       json={"message": "hi", "interaction_type": "journey_tutor", "journey_id": journey_id},
                       headers=world.headers("S"))


def test_tutor_blocked_when_assignment_disables_it(client, world, db, chat_stub):
    f.fetch(db, "UPDATE course_assignments SET settings = '{\"tutor_enabled\": false}'::jsonb "
                "WHERE journey_id = %s", (world.C1,))
    r = _tutor(client, world, world.C1)
    assert r.status_code == 403 and r.json()["detail"]["error"] == "tutor_disabled"


def test_tutor_allowed_by_default(client, world, db, chat_stub):
    r = _tutor(client, world, world.C1)
    assert r.status_code == 200, r.text


def test_quiz_not_required_by_default_lets_step_complete(client, world, db):
    step = f.step_ids(db, world.C1)[0]
    r = client.post(f"/api/v1/progress/{world.C1}/{step}", headers=world.headers("S"))
    assert r.status_code == 200, r.text


def test_journey_payload_reports_tutor_setting_to_students(client, world, db):
    r = client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S"))
    assert r.status_code == 200 and r.json()["tutor_enabled"] is True
    f.fetch(db, "UPDATE course_assignments SET settings = '{\"tutor_enabled\": false}'::jsonb "
                "WHERE journey_id = %s", (world.C1,))
    r = client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S"))
    assert r.json()["tutor_enabled"] is False


def test_journey_payload_tutor_setting_null_for_staff(client, world):
    r = client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("T"))
    assert r.status_code == 200 and r.json()["tutor_enabled"] is None


def test_quiz_required_gates_step_completion(client, world, db):
    f.fetch(db, "UPDATE course_assignments SET settings = '{\"quiz_required\": true}'::jsonb "
                "WHERE journey_id = %s", (world.C1,))
    step = f.step_ids(db, world.C1)[0]
    r = client.post(f"/api/v1/progress/{world.C1}/{step}", headers=world.headers("S"))
    assert r.status_code == 412
    assert r.json()["detail"]["message"] == "quiz_not_passed"
