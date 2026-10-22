"""AI course builder — publish + version history (M4 SC-406 / SC-407).

Publishing a built draft writes the student-facing `journeys.steps` + locked
`step_content` (invariant I5: nothing automatic overwrites it) and promotes the
version; restore/duplicate/archive manage the version lifecycle. Students never
see step bodies with flags/citations — only the published public fields.
"""
import pytest

from app.services import ai_service
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _sid(w):
    return w.school_a["id"]


def _url(w, jid, suffix=""):
    return f"/api/v1/schools/{_sid(w)}/courses/{jid}{suffix}"


# ── Publish ───────────────────────────────────────────────────────────────────

def test_publish_writes_student_facing_journey_and_locked_content(client, world, db):
    jid = f.make_built_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "published" and body["published_version"] == 1
    assert body["draft"] is None   # the draft was promoted; nothing left to edit

    # journeys.steps holds only public fields — no bodies, flags or citations
    jsteps = f.fetch(db, "SELECT steps FROM journeys WHERE id = %s", (jid,))[0]["steps"]
    assert len(jsteps) == 2
    assert all(set(s.keys()) <= {"id", "title", "description", "type", "estimated_minutes", "core_question"}
               for s in jsteps)

    # step_content rows are locked + school_published
    rows = f.fetch(db, "SELECT step_id, content, source, locked FROM step_content WHERE journey_id = %s ORDER BY step_id", (jid,))
    assert len(rows) == 2
    assert all(row["source"] == "school_published" and row["locked"] is True and row["content"] for row in rows)

    # the version is now published
    v = f.fetch(db, "SELECT version, state FROM course_versions WHERE journey_id = %s", (jid,))
    assert len(v) == 1 and v[0]["state"] == "published" and v[0]["version"] == 1


def test_published_content_is_not_overwritten_by_automatic_regen(client, world, db):
    # I5: upsert_step_content (lazy/auto regen path) must refuse a published school course
    jid = f.make_built_draft(db, world.school_a)
    client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    wrote = ai_service.upsert_step_content(jid, "s1", "HIJACKED", [], "gpt-x")
    assert wrote is False
    content = f.fetch(db, "SELECT content FROM step_content WHERE journey_id = %s AND step_id = 's1'", (jid,))[0]["content"]
    assert content != "HIJACKED"


def test_publish_refuses_incomplete_steps(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)   # steps have no body yet
    r = client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "steps_incomplete"
    assert r.json()["detail"]["steps"] == ["s1", "s2"]


def test_publish_refuses_empty_course(client, world, db):
    jid = f.make_course_draft(db, world.school_a)      # status 'empty', zero steps
    r = client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "empty_course"


def test_publish_honours_the_revision_lock(client, world, db):
    jid = f.make_built_draft(db, world.school_a)       # revision 2
    r = client.post(_url(world, jid, "/publish"), json={"expected_revision": 0}, headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "draft_conflict"


# ── Versions: restore / duplicate / archive ───────────────────────────────────

def test_versions_list_and_restore_creates_new_draft(client, world, db):
    jid = f.make_published_course(db, world.school_a)
    vs = client.get(_url(world, jid, "/versions"), headers=world.headers("SA")).json()["versions"]
    assert [v["version"] for v in vs] == [1] and vs[0]["state"] == "published"

    r = client.post(_url(world, jid, "/versions/1/restore"), json={}, headers=world.headers("SA"))
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft is not None and draft["version"] == 2 and draft["status"] == "built"
    assert [s["title"] for s in draft["steps"]] == ["Introduction", "Going deeper"]
    # a second restore is refused while the draft exists
    again = client.post(_url(world, jid, "/versions/1/restore"), json={}, headers=world.headers("SA"))
    assert again.status_code == 409 and again.json()["detail"]["error"] == "draft_exists"


def test_restore_then_publish_supersedes_the_old_version(client, world, db):
    jid = f.make_published_course(db, world.school_a)           # v1 published
    client.post(_url(world, jid, "/versions/1/restore"), json={}, headers=world.headers("SA"))  # → draft v2
    r = client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    assert r.status_code == 200 and r.json()["published_version"] == 2
    states = {row["version"]: row["state"]
              for row in f.fetch(db, "SELECT version, state FROM course_versions WHERE journey_id = %s", (jid,))}
    assert states == {1: "superseded", 2: "published"}


def test_restore_unknown_version_is_404(client, world, db):
    jid = f.make_published_course(db, world.school_a)
    r = client.post(_url(world, jid, "/versions/9/restore"), json={}, headers=world.headers("SA"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "version_not_found"


def test_duplicate_creates_a_fresh_draft_course(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/duplicate"), json={}, headers=world.headers("SA"))
    assert r.status_code == 200
    new_jid = r.json()["journey_id"]
    assert new_jid != jid and r.json()["status"] == "draft"
    assert r.json()["title"].endswith("(copy)")
    # the copy carries the source document link + the same steps
    assert len(r.json()["documents"]) == 1
    assert [s["title"] for s in r.json()["draft"]["steps"]] == ["Introduction", "Going deeper"]


def test_archive_hides_the_course_and_blocks_regeneration(client, world, db):
    jid = f.make_published_course(db, world.school_a)
    r = client.post(_url(world, jid, "/archive"), json={}, headers=world.headers("SA"))
    assert r.status_code == 200 and r.json()["status"] == "archived"
    # archived courses drop out of the list
    lst = client.get(f"/api/v1/schools/{_sid(world)}/courses", headers=world.headers("SA")).json()["courses"]
    assert all(c["journey_id"] != jid for c in lst)
    # and can't be published/outlined until restored
    pub = client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("SA"))
    assert pub.status_code == 409 and pub.json()["detail"]["error"] == "course_archived"
