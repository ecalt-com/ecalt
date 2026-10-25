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


# ── Replace mode (SC-605) ─────────────────────────────────────────────────────

# A fresh outline over the revised document: the first step's title matches the
# published "Introduction" (so its id is kept), the second is new material.
_REPLACE_OUTLINE = json.dumps({
    "meta": {"title": "Rebuilt Course", "description": "From the new edition.", "estimated_hours": 1},
    "steps": [
        {"title": "Introduction", "description": "Topics 1 and 2.", "type": "concept",
         "estimated_minutes": 15, "core_question": "What is topic 1?",
         "learning_objective": "Understand topic 1", "chunk_ids": [0, 1]},
        {"title": "Volcanoes", "description": "How volcanoes erupt.", "type": "concept",
         "estimated_minutes": 15, "core_question": "How do volcanoes form?",
         "learning_objective": "Explain volcanism", "chunk_ids": [2]},
    ],
    "skipped_sections": [],
})


def test_replace_mode_rebuilds_the_draft_keeping_matching_step_ids(client, world, db, monkeypatch):
    (FakeProvider()
        .respond("school_course_outline", _REPLACE_OUTLINE)
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    jid = f.make_published_course(db, world.school_a)      # steps s1 "Introduction", s2 "Going deeper"
    doc = _new_doc(db, world.school_a, _REVISED)

    r = _start(client, world, jid, doc, mode="replace")
    assert r.status_code == 200 and r.json()["mode"] == "replace"
    assert sj.process_one("w1") is True

    # Replace reviews as a whole draft, not as individual proposals.
    assert _proposals(client, world, jid)["proposals"] == []
    draft = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}",
                       headers=world.headers("SA")).json()["draft"]
    assert draft["status"] == "built" and draft["version"] == 2
    assert draft["meta"]["updated_from_version"] == 1 and draft["meta"]["rebuilt_from_document"] is True
    titles = [s["title"] for s in draft["steps"]]
    ids = [s["id"] for s in draft["steps"]]
    assert titles == ["Introduction", "Volcanoes"]
    assert ids[0] == "s1"              # title matched → id kept, progress survives
    assert ids[1] != "s2"              # different material never inherits a dropped step's id
    assert all(s["body_md"] for s in draft["steps"])


def test_replace_mode_reports_a_rejected_outline(client, world, db, monkeypatch):
    (FakeProvider().respond("school_course_outline", '{"steps": []}')
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    jid = f.make_published_course(db, world.school_a)
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc, mode="replace")
    sj.process_one("w1")

    # The published course is untouched and no draft was created.
    assert client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}",
                      headers=world.headers("SA")).json()["draft"] is None


def test_update_rejects_an_unknown_mode(client, world, db):
    jid = f.make_published_course(db, world.school_a)
    doc = f.make_document(db, world.school_a, status="ready")["id"]
    assert _start(client, world, jid, doc, mode="rewrite").status_code == 422


# ── "Updated since you finished" (SC-604) ─────────────────────────────────────

def _publish(client, world, jid):
    return client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/publish",
                       json={}, headers=world.headers("SA"))


def test_republish_badges_only_the_steps_whose_content_changed(client, world, db, monkeypatch):
    _install_model(monkeypatch)
    jid = f.make_built_draft(db, world.school_a)
    assert _publish(client, world, jid).status_code == 200      # v1 → locked step_content
    f.assign(db, world.A1, jid)
    for step in ("s1", "s2"):
        f.fetch(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, %s)",
                (world.S, jid, step))

    # v1 carries no stamp — nothing has changed under anyone yet.
    r = client.get(f"/api/v1/progress/{jid}", headers=world.headers("S"))
    assert r.status_code == 200 and r.json()["updated_step_ids"] == []

    # Revise from a new document: only s2's source changed.
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc)
    sj.process_one("w1")
    modify = next(p for p in _proposals(client, world, jid)["proposals"] if p["op"] == "modify")
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/{modify['id']}/decide",
                json={"decision": "accept"}, headers=world.headers("SA"))
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/apply",
                json={}, headers=world.headers("SA"))
    assert _publish(client, world, jid).status_code == 200

    body = client.get(f"/api/v1/progress/{jid}", headers=world.headers("S")).json()
    assert body["updated_step_ids"] == ["s2"]                  # s1's body is byte-identical
    assert sorted(body["completed_step_ids"]) == ["s1", "s2"]  # progress survived the update

    # The stamp lives on the student-facing step and survives a later publish.
    public = {s["id"]: s for s in f.fetch(db, "SELECT steps FROM journeys WHERE id = %s", (jid,))[0]["steps"]}
    assert public["s2"]["content_updated_at"] and "content_updated_at" not in public["s1"]


def _pass_quiz(db, uid: str, journey_id: str, step_id: str) -> None:
    """A fully answered, fully correct quiz set for one step."""
    set_id = f.fetch(db, "SELECT gen_random_uuid() AS id")[0]["id"]
    for _ in range(3):
        sess = f.fetch(db, """INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id, quiz_set_id)
                              VALUES (%s, 'topic', '{}'::jsonb, %s, %s, %s) RETURNING id::text""",
                       (uid, journey_id, step_id, set_id))[0]["id"]
        f.fetch(db, """INSERT INTO quiz_results (uid, concept, difficulty, is_correct, hints_used,
                                                 journey_id, step_id, session_id)
                       VALUES (%s, 'topic', 'surface', true, 0, %s, %s, %s)""",
                (uid, journey_id, step_id, sess))


def test_changed_content_retires_the_old_quiz_pass(client, world, db, monkeypatch):
    """A quiz set drawn from the old body can ask about material that is gone,
    so it stops counting towards the step's pass once the content changes."""
    _install_model(monkeypatch)
    jid = f.make_built_draft(db, world.school_a)
    _publish(client, world, jid)
    f.assign(db, world.A1, jid)

    # The student passes both steps' quizzes on v1 (3 of 3 each).
    for step in ("s1", "s2"):
        _pass_quiz(db, world.S, jid, step)
        assert client.get(f"/api/v1/quiz/step-status/{jid}/{step}",
                          headers=world.headers("S")).json()["passed"] is True

    # Republish with a changed s2 body.
    doc = _new_doc(db, world.school_a, _REVISED)
    _start(client, world, jid, doc)
    sj.process_one("w1")
    modify = next(p for p in _proposals(client, world, jid)["proposals"] if p["op"] == "modify")
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/{modify['id']}/decide",
                json={"decision": "accept"}, headers=world.headers("SA"))
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals/apply",
                json={}, headers=world.headers("SA"))
    _publish(client, world, jid)

    assert client.get(f"/api/v1/quiz/step-status/{jid}/s2",
                      headers=world.headers("S")).json()["passed"] is False   # retired
    assert client.get(f"/api/v1/quiz/step-status/{jid}/s1",
                      headers=world.headers("S")).json()["passed"] is True    # unchanged step
