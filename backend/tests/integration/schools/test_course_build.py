"""AI course builder — outline approve → build job (M4 SC-404).

Drives the build job through the queue with a deterministic fake model: each
reviewed outline step gets a grounded body + faithfulness critic pass. A clean
build lands reviewable step content; unsupported claims the critic flags are
kept on the step for a teacher; a body that stays invalid fails that step softly
without sinking the build; the job reports progress and stops on cancel; step
bodies build with bounded concurrency; the school budget gates the spend.
"""
import json
import re

import pytest

from app.services import school_course_builder as builder  # noqa: F401 - registers 'build'
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider

pytestmark = pytest.mark.schools_db

_SUPPORTED = json.dumps({"supported": True, "flags": []})
_UNSUPPORTED = json.dumps({"supported": False,
                           "flags": [{"claim": "The sky is green", "reason": "not in the source"}]})


def _sid(w):
    return w.school_a["id"]


def _body_response(system, user):
    """A valid body that cites whatever chunk ids the step's prompt actually
    lists — so one fake satisfies every step regardless of its sources."""
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", user)]
    return json.dumps({
        "body_md": "## Lesson\n\nA grounded explanation of the material.",
        "citations": ids[:2] or [0],
        "key_facts": ["Key fact one", "Key fact two"],
    })


def _build(client, world, jid):
    return client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/build",
                       json={}, headers=world.headers("SA"))


def _draft(client, world, jid):
    return client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}",
                      headers=world.headers("SA")).json()["draft"]


def test_build_happy_path(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))

    r = _build(client, world, jid)
    assert r.status_code == 200 and r.json()["status"] == "building"
    assert sj.process_one("w1") is True

    draft = _draft(client, world, jid)
    assert draft["status"] == "built"
    assert len(draft["steps"]) == 2
    for s in draft["steps"]:
        assert s["build_status"] == "built"
        assert s["body_md"]
        assert not s["flags"]
        # citations were mapped back to real chunk UUIDs, not left as cite indices
        assert s["citations"] and all(isinstance(c, str) and c for c in s["citations"])
        assert s["quiz_anchors"] and s["quiz_anchors"][0]["chunk_ids"] == s["citations"]


def test_build_keeps_unsupported_claims_as_flags(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _UNSUPPORTED)   # critic never satisfied
        .install(monkeypatch))

    _build(client, world, jid)
    assert sj.process_one("w1") is True

    draft = _draft(client, world, jid)
    assert draft["status"] == "built"            # flagged, not failed — a teacher reviews
    assert draft["meta"]["steps_flagged"] == 2
    for s in draft["steps"]:
        assert s["body_md"]                       # body is kept
        assert s["flags"] and s["flags"][0]["kind"] == "unsupported"


def test_build_fails_step_softly_on_invalid_body(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", "{ not json")   # never parses, even after retry
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))

    _build(client, world, jid)
    assert sj.process_one("w1") is True            # the job completes; steps fail, not the worker

    draft = _draft(client, world, jid)
    assert draft["status"] == "build_failed"       # every step failed
    assert draft["meta"]["steps_failed"] == 2
    for s in draft["steps"]:
        assert s["build_status"] == "failed" and s["body_md"] is None
        assert s["flags"][0]["kind"] == "build_error"


def test_build_rejects_citations_outside_the_step(client, world, db, monkeypatch):
    # Step s2 cites only chunk 2; a body citing [0] (not in the step's sources)
    # is a grounding violation → that step fails rather than ship ungrounded.
    jid = f.make_outlined_draft(db, world.school_a)
    bad = json.dumps({"body_md": "x", "citations": [0], "key_facts": []})
    (FakeProvider()
        .respond("school_step_content", lambda s, u: bad if "topic 3" in u else _body_response(s, u))
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))

    _build(client, world, jid)
    sj.process_one("w1")

    steps = {s["id"]: s for s in _draft(client, world, jid)["steps"]}
    assert steps["s1"]["build_status"] == "built"
    assert steps["s2"]["build_status"] == "failed"


def test_build_reports_progress(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    r = _build(client, world, jid)
    job_id = r.json()["job_id"]
    sj.process_one("w1")

    job = client.get(f"/api/v1/schools/{_sid(world)}/jobs/{job_id}", headers=world.headers("SA")).json()
    assert job["status"] == "succeeded"
    assert job["progress"] == {"steps_done": 2, "steps_total": 2}


def test_build_stops_on_cancel(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    job_id = _build(client, world, jid).json()["job_id"]
    # cancel requested before the worker picks it up: it stops at the first checkpoint
    f.fetch(db, "UPDATE school_jobs SET cancel_requested = true WHERE id = %s", (job_id,))

    sj.process_one("w1")
    job = sj.get_job(_sid(world), job_id)
    assert job["status"] == "cancelled"
    draft = _draft(client, world, jid)
    assert draft["status"] == "outline_ready"       # left rebuildable, not stuck 'building'
    assert all(s["body_md"] is None for s in draft["steps"])


def test_build_runs_steps_concurrently_within_bound(world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    fake = (FakeProvider(slow_seconds=0.1)
            .respond("school_step_content", _body_response)
            .respond("school_faithfulness_critic", _SUPPORTED))
    fake.set_mode("slow", "school_step_content")
    fake.install(monkeypatch)

    job = {"id": f.enqueue_job(db, world.school_a, kind="build"),
           "school_id": _sid(world), "payload": {"journey_id": jid}, "attempts": 1, "max_attempts": 3}
    out = builder.build_handler(job)

    assert out["status"] == "built"
    # both step bodies were in flight at once, and never more than the bound
    assert 1 < fake.max_in_flight <= builder._BUILD_CONCURRENCY


def test_build_blocked_when_school_budget_exhausted(client, db):
    school = f.make_school(db, name="Broke Build School", budget_cents=0)
    from tests.schools import identity
    owner = f.make_staff(db, school, "owner")
    identity.register(owner)
    jid = f.make_outlined_draft(db, school)
    r = client.post(f"/api/v1/schools/{school['id']}/courses/{jid}/build", json={},
                    headers={"Authorization": f"Bearer test:{owner}"})
    assert r.status_code == 402 and r.json()["detail"]["error"] == "school_budget_exhausted"


def test_build_refuses_without_an_outline(client, world, db):
    jid = f.make_course_draft(db, world.school_a)   # status 'empty', no steps
    r = _build(client, world, jid)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "no_outline"
