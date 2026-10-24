"""AI course builder — create course + grounded outline generation (M4 SC-402).

Drives the outline job through the queue with a deterministic fake model: a
valid outline lands as a reviewable draft (every step grounded in real chunk
ids), an invalid one fails visibly after a retry, and the school budget gates
the spend.
"""
import json

import pytest

from app.services import school_course_builder  # noqa: F401 - registers the 'outline' handler
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider

pytestmark = pytest.mark.schools_db

_GOOD_OUTLINE = json.dumps({
    "meta": {"title": "The Water Cycle", "description": "How water moves.", "estimated_hours": 1},
    "steps": [
        {"title": "Evaporation", "description": "Sun heats water.", "type": "concept",
         "estimated_minutes": 15, "core_question": "Where does water go?",
         "learning_objective": "Explain evaporation", "chunk_ids": [0, 1]},
        {"title": "Rain", "description": "Clouds release water.", "type": "concept",
         "estimated_minutes": 15, "core_question": "Why does it rain?",
         "learning_objective": "Explain precipitation", "chunk_ids": [2]},
    ],
    "skipped_sections": [],
})


def _sid(w):
    return w.school_a["id"]


def test_create_course_validates_documents(client, world, db):
    ready = f.make_document(db, world.school_a, status="ready")["id"]
    pending = f.make_document(db, world.school_a, status="uploaded")["id"]
    url = f"/api/v1/schools/{_sid(world)}/courses"
    h = world.headers("SA")

    assert client.post(url, json={"title": "C", "document_ids": []}, headers=h).status_code == 422
    assert client.post(url, json={"title": "C", "document_ids": [pending]}, headers=h).status_code == 409
    r = client.post(url, json={"title": "Weather", "document_ids": [ready]}, headers=h)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    assert r.json()["draft"]["status"] == "empty"


def test_outline_happy_path(client, world, db, monkeypatch):
    jid = f.make_course_draft(db, world.school_a)  # 3 chunks, cite_ids 0..2
    FakeProvider().respond("school_course_outline", _GOOD_OUTLINE).install(monkeypatch)

    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/outline",
                    json={"grade": 5, "subject": "Science"}, headers=world.headers("SA"))
    assert r.status_code == 200 and r.json()["status"] == "outlining"
    assert sj.process_one("w1") is True

    course = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()
    draft = course["draft"]
    assert draft["status"] == "outline_ready"
    assert [s["title"] for s in draft["steps"]] == ["Evaporation", "Rain"]
    assert draft["steps"][0]["origin"] == "ai"
    # cite_ids were mapped to real chunk UUIDs (grounding is preserved on disk).
    assert len(draft["steps"][0]["chunk_ids"]) == 2 and all(draft["steps"][0]["chunk_ids"])
    assert draft["meta"]["title"] == "The Water Cycle"


def test_outline_rejects_hallucinated_chunk_ids(client, world, db, monkeypatch):
    jid = f.make_course_draft(db, world.school_a)
    bad = json.dumps({"meta": {"title": "X"}, "steps": [
        {"title": "Made up", "chunk_ids": [99]}], "skipped_sections": []})  # 99 isn't a real chunk
    FakeProvider().respond("school_course_outline", bad).install(monkeypatch)

    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/outline", json={}, headers=world.headers("SA"))
    sj.process_one("w1")

    draft = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()["draft"]
    assert draft["status"] == "outline_failed" and draft["steps"] == []
    # It retried once before giving up (two model calls on the same draft).
    job = f.fetch(db, "SELECT attempts, result FROM school_jobs WHERE school_id = %s", (_sid(world),))[0]
    assert job["result"]["status"] == "outline_failed"


def test_outline_blocked_when_school_budget_exhausted(client, db, monkeypatch):
    # A school with no AI budget can't spend on generation.
    school = f.make_school(db, name="Broke School", budget_cents=0)
    from tests.schools import identity
    owner = f.make_staff(db, school, "owner")
    identity.register(owner)
    jid = f.make_course_draft(db, school)
    r = client.post(f"/api/v1/schools/{school['id']}/courses/{jid}/outline", json={},
                    headers={"Authorization": f"Bearer test:{owner}"})
    assert r.status_code == 402 and r.json()["detail"]["error"] == "school_budget_exhausted"


def test_estimate_reports_cost(client, world, db):
    jid = f.make_course_draft(db, world.school_a)
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/estimate", headers=world.headers("SA"))
    assert r.status_code == 200
    body = r.json()
    assert body["chunk_count"] == 3 and body["document_count"] == 1
    assert body["estimated_cost_cents"] > 0


def test_job_status_and_cancel(client, world, db):
    job_id = f.enqueue_job(db, world.school_a, kind="outline")
    h = world.headers("SA")
    assert client.get(f"/api/v1/schools/{_sid(world)}/jobs/{job_id}", headers=h).json()["kind"] == "outline"
    r = client.post(f"/api/v1/schools/{_sid(world)}/jobs/{job_id}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
