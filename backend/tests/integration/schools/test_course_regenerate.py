"""AI course builder — regenerate one step (M4 SC-405).

A teacher re-generates a single step's body from its cited chunks, optionally
with an instruction. The new draft is grounded like the build job; teacher edits
are protected unless the teacher explicitly overwrites them; ungrounded
teacher-authored steps can't be AI-regenerated.
"""
import json

import pytest

from app.services import school_course_builder  # noqa: F401 - registers 'regenerate_step'
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider

pytestmark = pytest.mark.schools_db

_SUPPORTED = json.dumps({"supported": True, "flags": []})


def _sid(w):
    return w.school_a["id"]


def _url(w, jid, step="s1"):
    return f"/api/v1/schools/{_sid(w)}/courses/{jid}/draft/steps/{step}/regenerate"


def _body_response(system, user):
    import re
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", user)]
    return json.dumps({"body_md": "## Regenerated\n\nFresh grounded text.",
                       "citations": ids[:2] or [0], "key_facts": ["Fresh fact"]})


def _install(monkeypatch, body=_body_response):
    return (FakeProvider()
            .respond("school_step_content", body)
            .respond("school_faithfulness_critic", _SUPPORTED)
            .install(monkeypatch))


def _step(client, world, jid, step_id="s1"):
    draft = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()["draft"]
    return next(s for s in draft["steps"] if s["id"] == step_id)


def test_regenerate_happy_path(client, world, db, monkeypatch):
    jid = f.make_built_draft(db, world.school_a)
    _install(monkeypatch)
    r = client.post(_url(world, jid), json={}, headers=world.headers("SA"))
    assert r.status_code == 200 and r.json()["status"] == "regenerating"
    assert sj.process_one("w1") is True

    s1 = _step(client, world, jid)
    assert s1["body_md"] == "## Regenerated\n\nFresh grounded text."
    assert s1["origin"] == "ai" and s1["edited_by_teacher"] is False
    assert s1["citations"] and all(isinstance(c, str) for c in s1["citations"])
    # the other step was untouched
    assert _step(client, world, jid, "s2")["body_md"].startswith("## Going deeper")


def test_regenerate_passes_instruction_to_the_model(client, world, db, monkeypatch):
    jid = f.make_built_draft(db, world.school_a)
    fake = _install(monkeypatch)
    client.post(_url(world, jid), json={"instruction": "Simplify for younger readers"},
                headers=world.headers("SA"))
    sj.process_one("w1")
    assert any("Simplify for younger readers" in c.user_content
               for c in fake.calls_for("school_step_content"))


def test_regenerate_protects_teacher_edits_unless_overwritten(client, world, db, monkeypatch):
    jid = f.make_built_draft(db, world.school_a)
    # a hand edit marks the step teacher-owned
    client.patch(f"/api/v1/schools/{_sid(world)}/courses/{jid}/draft/steps/s1",
                 json={"body_md": "teacher wrote this"}, headers=world.headers("SA"))
    _install(monkeypatch)

    blocked = client.post(_url(world, jid), json={}, headers=world.headers("SA"))
    assert blocked.status_code == 409 and blocked.json()["detail"]["error"] == "teacher_edits_protected"

    ok = client.post(_url(world, jid), json={"overwrite_teacher_edits": True}, headers=world.headers("SA"))
    assert ok.status_code == 200
    assert sj.process_one("w1") is True
    s1 = _step(client, world, jid)
    assert s1["body_md"] == "## Regenerated\n\nFresh grounded text." and s1["edited_by_teacher"] is False


def test_regenerate_rejects_ungrounded_teacher_step(client, world, db, monkeypatch):
    jid = f.make_built_draft(db, world.school_a)
    added = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/draft/steps",
                        json={"title": "My own step"}, headers=world.headers("SA")).json()
    new_id = added["draft"]["steps"][-1]["id"]
    r = client.post(_url(world, jid, new_id), json={}, headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "step_not_grounded"


def test_regenerate_unknown_step_is_404(client, world, db):
    jid = f.make_built_draft(db, world.school_a)
    r = client.post(_url(world, jid, "nope"), json={}, headers=world.headers("SA"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "step_not_found"


def test_regenerate_blocked_when_budget_exhausted(client, db):
    school = f.make_school(db, name="Broke Regen School", budget_cents=0)
    from tests.schools import identity
    owner = f.make_staff(db, school, "owner")
    identity.register(owner)
    jid = f.make_built_draft(db, school)
    r = client.post(f"/api/v1/schools/{school['id']}/courses/{jid}/draft/steps/s1/regenerate",
                    json={}, headers={"Authorization": f"Bearer test:{owner}"})
    assert r.status_code == 402 and r.json()["detail"]["error"] == "school_budget_exhausted"
