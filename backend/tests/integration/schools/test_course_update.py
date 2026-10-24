"""Course updates from a new document (M6 SC-601..604).

Drives the whole loop against the real schema with a deterministic fake model:
publish a course, upload a revised document, run the propose-update job, review
the proposals (modify changed steps, add new sections, leave unchanged steps
alone), accept them, apply into a new draft (step ids preserved so progress
survives), and publish. Also covers supplement mode, teacher-step suggestions,
and the guard rails.
"""
import json
import re

import pytest

from app.services import school_course_update_service as updates  # noqa: F401 - registers 'propose_update'
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider

pytestmark = pytest.mark.schools_db

_SUPPORTED = json.dumps({"supported": True, "flags": []})


def _sid(w):
    return w.school_a["id"]


def _body_response(system, user):
    """A valid grounded body citing whatever chunk ids the prompt lists."""
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", user)]
    return json.dumps({
        "body_md": "## Updated lesson\n\nA grounded explanation from the new document.",
        "citations": ids[:2] or [0],
        "key_facts": ["Updated fact one", "Updated fact two"],
    })


def _install_model(monkeypatch):
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))


def _new_doc(db, school, chunks: list) -> str:
    """A ready document with the given (text, heading) chunks."""
    doc = f.make_document(db, school, filename="revised.pdf", status="ready")
    for i, (text, heading) in enumerate(chunks):
        f.fetch(db, """INSERT INTO document_chunks (document_id, ordinal, heading_path, text, char_count)
                       VALUES (%s, %s, %s, %s, %s)""",
                (doc["id"], i, [heading] if heading else [], text, len(text)))
    return doc["id"]


# The built course's steps cite: s1 → "topic 1" + "topic 2", s2 → "topic 3".
# (make_course_draft seeds chunks "Lesson content about topic N. " ×12.)
_REVISED = [
    ("Lesson content about topic 1 and topic 2", "Section 1"),            # ~unchanged vs s1
    ("Lesson content about topic 3 revised with extra detail notes", "Section 3"),  # changed vs s2
    ("Volcanoes form when magma rises through the crust and erupts", "Volcanoes"),  # new section
]


def _start(client, world, jid, doc_id, mode="revise"):
    return client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/update",
                       json={"document_id": doc_id, "mode": mode}, headers=world.headers("SA"))


def _proposals(client, world, jid):
    return client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals",
                      headers=world.headers("SA")).json()


def test_revise_proposes_modify_and_add_leaving_unchanged_alone(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_published_course(db, world.school_a)
    doc = _new_doc(db, world.school_a, _REVISED)

    r = _start(client, world, jid, doc)
    assert r.status_code == 200 and r.json()["status"] == "proposing"
    assert sj.process_one("w1") is True

    data = _proposals(client, world, jid)
    ops = sorted(p["op"] for p in data["proposals"])
    assert ops == ["add", "modify"]            # s1 unchanged → no proposal
    modify = next(p for p in data["proposals"] if p["op"] == "modify")
    assert modify["step_id"] == "s2"
    assert modify["new_body"] and modify["old_body"]
    assert modify["diff"]["added"] >= 1
    add = next(p for p in data["proposals"] if p["op"] == "add")
    assert add["title"] == "Volcanoes" and add["new_body"]


def test_accept_apply_publish_preserves_step_ids(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_published_course(db, world.school_a)
    before_ids = f.step_ids(db, jid)                       # ["s1", "s2"]
    doc = _new_doc(db, world.school_a, _REVISED)

    _start(client, world, jid, doc)
    sj.process_one("w1")
    data = _proposals(client, world, jid)
    for p in data["proposals"]:
        rr = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/{p['id']}/decide",
                         json={"decision": "accept"}, headers=world.headers("SA"))
        assert rr.status_code == 200

    ra = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/apply",
                     json={}, headers=world.headers("SA"))
    assert ra.status_code == 200
    draft = ra.json()["draft"]
    assert draft["version"] == 2 and draft["meta"]["updated_from_version"] == 1
    draft_ids = [s["id"] for s in draft["steps"]]
    assert "s1" in draft_ids and "s2" in draft_ids        # ids preserved → progress survives
    assert len(draft_ids) == 3                             # + the added volcano step
    # proposals are consumed
    assert _proposals(client, world, jid)["proposals"] == []

    # publish the reviewed draft: student-facing journey keeps the stable ids
    rp = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/publish",
                     json={}, headers=world.headers("SA"))
    assert rp.status_code == 200
    published_ids = f.step_ids(db, jid)
    assert "s1" in published_ids and "s2" in published_ids and len(published_ids) == 3


def test_reject_leaves_published_untouched(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_published_course(db, world.school_a)
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc)
    sj.process_one("w1")
    data = _proposals(client, world, jid)
    for p in data["proposals"]:
        client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/{p['id']}/decide",
                    json={"decision": "reject"}, headers=world.headers("SA"))
    # nothing accepted → apply refuses, no draft created
    ra = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/apply",
                     json={}, headers=world.headers("SA"))
    assert ra.status_code == 409 and ra.json()["detail"]["error"] == "nothing_to_apply"
    assert client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}",
                      headers=world.headers("SA")).json()["draft"] is None


def test_supplement_mode_only_adds(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_published_course(db, world.school_a)
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc, mode="supplement")
    sj.process_one("w1")
    ops = sorted(p["op"] for p in _proposals(client, world, jid)["proposals"])
    assert ops == ["add"]       # no modify/remove in supplement mode


def test_teacher_step_change_is_suggestion_only(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_published_course(db, world.school_a)
    # Mark s2 as teacher-authored on the published version.
    steps = f.fetch(db, "SELECT steps FROM course_versions WHERE journey_id = %s AND state = 'published'", (jid,))[0]["steps"]
    for s in steps:
        if s["id"] == "s2":
            s["origin"] = "teacher"
    f.fetch(db, "UPDATE course_versions SET steps = %s::jsonb WHERE journey_id = %s AND state = 'published'",
            (json.dumps(steps), jid))
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc)
    sj.process_one("w1")
    modify = next(p for p in _proposals(client, world, jid)["proposals"] if p["op"] == "modify")
    assert modify["suggestion_only"] is True


def test_update_requires_published_course(client, world, db):
    jid = f.make_built_draft(db, world.school_a)      # has a draft, not published
    doc = f.make_document(db, world.school_a, status="ready")["id"]
    r = _start(client, world, jid, doc)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "course_not_published"


def test_update_requires_ready_document(client, world, db):
    jid = f.make_published_course(db, world.school_a)
    doc = f.make_document(db, world.school_a, status="uploaded")["id"]
    r = _start(client, world, jid, doc)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "document_not_ready"
