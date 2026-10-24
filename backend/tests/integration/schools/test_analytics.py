"""Teacher analytics (plans/school-courses M7, §10): student drill-down
(SC-701), struggling flags (SC-702), CSV export (SC-704) and the usage overview
(SC-706). The world seeds school A, course C1 (2 steps) assigned to class A1,
student S (Asha K) enrolled in A1."""
from datetime import date

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _drill(w, class_id, uid):
    return f"/api/v1/schools/{w.school_a['id']}/classes/{class_id}/students/{uid}/progress"


# ── SC-701: student drill-down ────────────────────────────────────────────────

def test_drilldown_shape(client, world):
    r = client.get(_drill(world, world.A1["id"], world.S), headers=world.headers("T"))
    assert r.status_code == 200
    d = r.json()
    assert d["student"]["uid"] == world.S and d["student"]["display_name"] == "Asha K"
    assert len(d["courses"]) == 1
    c = d["courses"][0]
    assert c["journey_id"] == world.C1 and c["total_steps"] == 2
    assert c["done_steps"] == 0 and c["completed"] is False and c["flags"] == []
    assert len(c["steps"]) == 2
    assert all(s["completed"] is False and s["quiz_attempts"] == 0 for s in c["steps"])


def test_drilldown_reflects_completion_and_quiz(client, world, db):
    steps = f.step_ids(db, world.C1)
    assert client.post(f"/api/v1/progress/{world.C1}/{steps[0]}", headers=world.headers("S")).status_code == 200
    for correct, hints in [(True, 1), (False, 1), (False, 1)]:
        f.fetch(db, "INSERT INTO quiz_results (uid, concept, difficulty, is_correct, hints_used, journey_id, step_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (world.S, "concept", "easy", correct, hints, world.C1, steps[0]))
    d = client.get(_drill(world, world.A1["id"], world.S), headers=world.headers("T")).json()
    c = d["courses"][0]
    assert c["done_steps"] == 1 and c["percent"] == 50
    s0 = next(s for s in c["steps"] if s["step_id"] == steps[0])
    assert s0["completed"] is True
    assert s0["quiz_attempts"] == 3 and s0["quiz_correct"] == 1 and s0["hints_used"] == 3
    assert c["quiz_accuracy"] == 33  # 1 of 3
    assert "low_quiz_accuracy" in c["flags"]


def test_drilldown_404_for_student_not_in_class(client, world):
    # S2 is enrolled in A2, not A1.
    r = client.get(_drill(world, world.A1["id"], world.S2), headers=world.headers("SA"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "student_not_found"


def test_drilldown_overdue_flag(client, world, db):
    journey_id = f.make_published_course(db, world.school_a)
    assert client.post(f"/api/v1/schools/{world.school_a['id']}/classes/{world.A1['id']}/courses",
                       json={"journey_id": journey_id, "due_at": "2020-01-01T00:00:00Z"},
                       headers=world.headers("T")).status_code == 201
    d = client.get(_drill(world, world.A1["id"], world.S), headers=world.headers("T")).json()
    c = next(c for c in d["courses"] if c["journey_id"] == journey_id)
    assert c["overdue"] is True and "overdue" in c["flags"]


# ── SC-704: CSV export (SEC-12) ──────────────────────────────────────────────

def test_csv_export(client, world):
    r = client.get(f"/api/v1/schools/{world.school_a['id']}/classes/{world.A1['id']}/progress/export",
                   headers=world.headers("T"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert body.startswith("Student,Grade,Photosynthesis")
    assert "Asha K" in body


# ── SC-706: usage overview (admins) ──────────────────────────────────────────

def test_usage_is_admin_only(client, world):
    assert client.get(f"/api/v1/schools/{world.school_a['id']}/usage", headers=world.headers("T")).status_code == 403


# ── SC-703: tutor transcript visibility (D4) ─────────────────────────────────

def _transcripts_url(w, class_id, uid):
    return f"/api/v1/schools/{w.school_a['id']}/classes/{class_id}/students/{uid}/transcripts"


def _set_transcript_access(db, school, on: bool):
    f.fetch(db, "UPDATE schools SET settings = settings || %s::jsonb WHERE id = %s",
            (f'{{"teacher_transcript_access": {str(on).lower()}}}', school["id"]))


def _seed_conversation(db, uid):
    conv = f.fetch(db, "INSERT INTO conversations (uid, title) VALUES (%s, %s) RETURNING id::text AS id",
                   (uid, "Tutor chat"))[0]["id"]
    for role, content in [("user", "help with step 1"), ("assistant", "Sure — here's a hint.")]:
        f.fetch(db, "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s,%s,%s)",
                (conv, role, content))
    return conv


def test_transcripts_list_and_read_when_enabled(client, world, db):
    _set_transcript_access(db, world.school_a, True)
    conv = _seed_conversation(db, world.S)
    r = client.get(_transcripts_url(world, world.A1["id"], world.S), headers=world.headers("T"))
    assert r.status_code == 200
    assert any(c["id"] == conv and c["message_count"] == 2 for c in r.json()["conversations"])
    rr = client.get(f"{_transcripts_url(world, world.A1['id'], world.S)}/{conv}", headers=world.headers("T"))
    assert rr.status_code == 200
    assert [m["role"] for m in rr.json()["messages"]] == ["user", "assistant"]
    # The view is audited (D4).
    audit = f.fetch(db, "SELECT target_id FROM school_audit_log "
                        "WHERE school_id = %s AND action = 'student.transcript_viewed'", (world.school_a["id"],))
    assert audit and audit[0]["target_id"] == world.S


def test_transcripts_403_when_school_disables(client, world, db):
    _set_transcript_access(db, world.school_a, False)
    r = client.get(_transcripts_url(world, world.A1["id"], world.S), headers=world.headers("T"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "transcript_access_disabled"


def test_transcript_read_404_for_another_students_conversation(client, world, db):
    _set_transcript_access(db, world.school_a, True)
    other = _seed_conversation(db, world.S2)  # S2 is not in A1
    r = client.get(f"{_transcripts_url(world, world.A1['id'], world.S)}/{other}", headers=world.headers("T"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "conversation_not_found"


def test_student_home_discloses_transcript_access(client, world, db):
    _set_transcript_access(db, world.school_a, True)
    on = client.get("/api/v1/school-student/home", headers=world.headers("S"))
    assert on.status_code == 200 and on.json()["transcripts_visible_to_teacher"] is True
    _set_transcript_access(db, world.school_a, False)
    off = client.get("/api/v1/school-student/home", headers=world.headers("S"))
    assert off.json()["transcripts_visible_to_teacher"] is False


def test_usage_overview(client, world, db):
    f.fetch(db, "UPDATE schools SET monthly_ai_budget_cents = 1000 WHERE id = %s", (world.school_a["id"],))
    period = date.today().replace(day=1)
    f.fetch(db, "INSERT INTO school_usage (school_id, period_start, cost_cents, input_tokens, output_tokens) "
                "VALUES (%s,%s,%s,%s,%s)", (world.school_a["id"], period, 250, 100, 50))
    r = client.get(f"/api/v1/schools/{world.school_a['id']}/usage", headers=world.headers("SA"))
    assert r.status_code == 200
    d = r.json()
    assert d["budget_cents"] == 1000 and d["spent_cents"] == 250 and d["percent"] == 25
    assert d["caps"] == {"student_daily_tutor_messages": 30, "student_daily_quiz_sets": 20}
    assert len(d["history"]) == 1 and d["history"][0]["cost_cents"] == 250
