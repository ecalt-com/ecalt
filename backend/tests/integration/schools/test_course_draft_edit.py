"""AI course builder — draft editing (M4 SC-403).

A teacher refines the generated draft: edit the course meta, and add / patch /
delete / reorder steps. Every write takes an optimistic lock on the draft's
`revision` (stale → 409 `draft_conflict`), is refused while a job is writing the
draft (`course_busy`), and tracks hand edits so regeneration can protect them.
"""
import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _sid(w):
    return w.school_a["id"]


def _url(w, jid, suffix=""):
    return f"/api/v1/schools/{_sid(w)}/courses/{jid}{suffix}"


def _steps(resp):
    return resp.json()["draft"]["steps"]


def test_patch_meta_updates_title_and_bumps_revision(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)   # revision 1
    r = client.patch(_url(world, jid, "/draft"),
                     json={"expected_revision": 1, "title": "Weather 101", "estimated_hours": 2},
                     headers=world.headers("SA"))
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Weather 101"              # journeys.title updated
    assert body["draft"]["meta"]["estimated_hours"] == 2
    assert body["draft"]["revision"] == 2
    # the new title shows in the course list, not just the draft meta
    courses = client.get(f"/api/v1/schools/{_sid(world)}/courses", headers=world.headers("SA")).json()["courses"]
    assert any(c["journey_id"] == jid and c["title"] == "Weather 101" for c in courses)


def test_add_step_appends_teacher_owned(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/draft/steps"),
                    json={"expected_revision": 1, "title": "Wrap up", "type": "challenge"},
                    headers=world.headers("SA"))
    assert r.status_code == 200
    assert [s["title"] for s in _steps(r)] == ["Introduction", "Going deeper", "Wrap up"]
    new = _steps(r)[-1]
    assert new["origin"] == "teacher" and new["edited_by_teacher"] is True
    assert new["type"] == "challenge" and new["chunk_ids"] == [] and new["build_status"] == "empty"


def test_add_step_after_a_given_step(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/draft/steps"),
                    json={"title": "Middle", "after_step_id": "s1"}, headers=world.headers("SA"))
    assert [s["title"] for s in _steps(r)] == ["Introduction", "Middle", "Going deeper"]


def test_patch_step_marks_edited_and_clears_critic_flags(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    # s1 carries an AI critic flag; a hand-edited body means the teacher owns the text
    f.fetch(db, """UPDATE course_versions
                      SET steps = jsonb_set(steps, '{0,flags}', '[{"kind":"unsupported"}]'::jsonb)
                    WHERE journey_id = %s AND state = 'draft'""", (jid,))
    r = client.patch(_url(world, jid, "/draft/steps/s1"),
                     json={"title": "Intro v2", "body_md": "# Hand written"}, headers=world.headers("SA"))
    assert r.status_code == 200
    s1 = next(s for s in _steps(r) if s["id"] == "s1")
    assert s1["title"] == "Intro v2" and s1["edited_by_teacher"] is True
    assert s1["flags"] == [] and s1["body_md"] == "# Hand written" and s1["build_status"] == "built"


def test_patch_step_rejects_unknown_type(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.patch(_url(world, jid, "/draft/steps/s1"),
                     json={"type": "bogus"}, headers=world.headers("SA"))
    assert r.status_code == 422 and r.json()["detail"]["error"] == "invalid_step_type"


def test_delete_step(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.delete(_url(world, jid, "/draft/steps/s1?revision=1"), headers=world.headers("SA"))
    assert r.status_code == 200 and [s["id"] for s in _steps(r)] == ["s2"]


def test_delete_unknown_step_is_404(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.delete(_url(world, jid, "/draft/steps/nope"), headers=world.headers("SA"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "step_not_found"


def test_reorder_steps(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/draft/steps/reorder"),
                    json={"order": ["s2", "s1"]}, headers=world.headers("SA"))
    assert r.status_code == 200 and [s["id"] for s in _steps(r)] == ["s2", "s1"]


def test_reorder_must_be_a_permutation(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/draft/steps/reorder"),
                    json={"order": ["s1"]}, headers=world.headers("SA"))
    assert r.status_code == 422 and r.json()["detail"]["error"] == "invalid_order"


def test_stale_revision_is_a_conflict(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)   # revision 1
    ok = client.patch(_url(world, jid, "/draft"),
                      json={"expected_revision": 1, "title": "A"}, headers=world.headers("SA"))
    assert ok.status_code == 200 and ok.json()["draft"]["revision"] == 2
    stale = client.patch(_url(world, jid, "/draft"),
                         json={"expected_revision": 1, "title": "B"}, headers=world.headers("SA"))
    assert stale.status_code == 409
    assert stale.json()["detail"]["error"] == "draft_conflict"
    assert stale.json()["detail"]["current_revision"] == 2
    # the losing edit did not land
    assert client.get(_url(world, jid), headers=world.headers("SA")).json()["title"] == "A"


def test_edits_blocked_while_the_course_is_generating(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    f.fetch(db, """UPDATE course_versions SET meta = jsonb_set(meta, '{status}', '"building"')
                    WHERE journey_id = %s AND state = 'draft'""", (jid,))
    r = client.patch(_url(world, jid, "/draft"), json={"title": "X"}, headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "course_busy"


def test_edit_unknown_course_is_404(client, world, db):
    import uuid
    r = client.patch(_url(world, str(uuid.uuid4()), "/draft"),
                     json={"title": "X"}, headers=world.headers("SA"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "course_not_found"
