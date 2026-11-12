"""#16 course-builder backend: cited chunk preview, Not covered → step,
course icon/tags, quiz preview, and the fuller estimate."""
import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _url(w, jid, tail=""):
    return f"/api/v1/schools/{w.school_a['id']}/courses/{jid}{tail}"


def _draft(client, w, jid):
    return client.get(_url(w, jid), headers=w.headers("T")).json()["draft"]


def test_chunks_returns_text_and_pages_for_this_course_only(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    other = f.make_outlined_draft(db, world.school_b)
    mine = _draft(client, world, jid)["steps"][0]["chunk_ids"]
    theirs = f.fetch(db, "SELECT steps FROM course_versions WHERE journey_id = %s", (other,))[0]["steps"][0]["chunk_ids"]
    r = client.get(_url(world, jid, f"/chunks?ids={','.join(mine + theirs)},not-a-uuid"), headers=world.headers("T"))
    assert r.status_code == 200, r.text
    chunks = r.json()["chunks"]
    assert [c["id"] for c in chunks] == mine
    assert chunks[0]["text"].startswith("Lesson content about topic 1") and chunks[0]["filename"] == "notes.pdf"
    assert set(chunks[0]) >= {"page_start", "page_end", "heading_path"}


def test_not_covered_section_becomes_a_grounded_step(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a, skipped=[{"heading": "Section 3", "reason": "appendix"}])
    rev = _draft(client, world, jid)["revision"]
    r = client.post(_url(world, jid, "/draft/steps/from-section"), json={"heading": "section 3", "expected_revision": rev},
                    headers=world.headers("T"))
    assert r.status_code == 200, r.text
    draft = r.json()["draft"]
    new = draft["steps"][-1]
    assert new["title"] == "Section 3" and new["origin"] == "ai" and len(new["chunk_ids"]) == 1
    assert draft["meta"]["skipped_sections"] == []
    # Again → the section is no longer listed.
    r = client.post(_url(world, jid, "/draft/steps/from-section"), json={"heading": "Section 3"}, headers=world.headers("T"))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "section_not_found"


def test_icon_and_tags_are_cleaned_and_published(client, world, db):
    jid = f.make_built_draft(db, world.school_a)
    r = client.patch(_url(world, jid, "/draft"), json={"icon": "🌋<b>", "tags": ["Earth Science", "earth science", "<x>", ""]},
                     headers=world.headers("T"))
    assert r.status_code == 200, r.text
    meta = r.json()["draft"]["meta"]
    assert meta["icon"] == "🌋b" and meta["tags"] == ["earth science", "x"]
    assert client.post(_url(world, jid, "/publish"), json={}, headers=world.headers("T")).status_code == 200
    row = f.fetch(db, "SELECT icon, tags FROM journeys WHERE id = %s", (jid,))[0]
    assert row["icon"] == "🌋b" and row["tags"] == ["earth science", "x"]


def test_quiz_preview_is_billed_and_saves_nothing(client, world, db, fake_quiz_preview):
    jid = f.make_built_draft(db, world.school_a)
    before = f.fetch(db, "SELECT count(*) AS n FROM quiz_sessions")[0]["n"]
    r = client.post(_url(world, jid, "/draft/steps/s1/quiz-preview"), json={}, headers=world.headers("T"))
    assert r.status_code == 200, r.text
    qs = r.json()["questions"]
    assert len(qs) == 2 and qs[0]["answer"] == "Food"
    assert "A grounded lesson body for step 1" in fake_quiz_preview[0]
    assert f.fetch(db, "SELECT count(*) AS n FROM quiz_sessions")[0]["n"] == before
    assert f.fetch(db, "SELECT cost_cents FROM school_usage WHERE school_id = %s", (world.school_a["id"],))


def test_quiz_preview_needs_content_and_budget(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/draft/steps/s1/quiz-preview"), json={}, headers=world.headers("T"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "step_has_no_content"
    built = f.make_built_draft(db, world.school_a)
    with db.cursor() as cur:
        cur.execute("UPDATE schools SET monthly_ai_budget_cents = 0 WHERE id = %s", (world.school_a["id"],))
    assert client.post(_url(world, built, "/draft/steps/s1/quiz-preview"), json={}, headers=world.headers("T")).status_code == 402


def test_estimate_includes_time_and_remaining_budget(client, world, db):
    jid = f.make_course_draft(db, world.school_a)
    r = client.post(_url(world, jid, "/estimate"), headers=world.headers("T"))
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["estimated_minutes"] >= 1 and e["estimated_steps"] >= 3
    assert e["budget_cents"] == 10_000 and e["budget_remaining_cents"] == 10_000
