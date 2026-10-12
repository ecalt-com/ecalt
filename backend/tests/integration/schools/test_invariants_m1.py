"""M1 invariant suites (TESTING.md §1).

INV-05  (I5)  nothing automatic overwrites locked step content or generates for a
              school course (SC-109)
INV-06  (I6)  school courses never reach public or cross-user pools (SC-108)
INV-13a (I13) deleting a teacher's account keeps the school's courses (SC-110)
"""
from unittest.mock import AsyncMock

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _content(db, journey_id, step_id):
    rows = f.fetch(db, "SELECT content, locked, source FROM step_content WHERE journey_id = %s AND step_id = %s",
                   (journey_id, step_id))
    return rows[0] if rows else None


# ── INV-05 ────────────────────────────────────────────────────────────────────

def test_inv05_upsert_refuses_school_courses_and_locked_rows(world, db):
    from app.services.ai_service import upsert_step_content
    s1, s2 = f.step_ids(db, world.C1)
    f.fetch(db, "DELETE FROM step_content WHERE journey_id = %s AND step_id = %s", (world.C1, s2))

    assert upsert_step_content(world.C1, s1, "AI overwrite", [], "gpt", overwrite=True) is False
    assert upsert_step_content(world.C1, s2, "AI fill-in", [], "gpt", overwrite=False) is False
    assert _content(db, world.C1, s1)["content"] == "Published body of Step 1"
    assert _content(db, world.C1, s2) is None

    # A locked row is protected even outside a school journey.
    n_step = f.step_ids(db, world.N1)[0]
    f.fetch(db, "UPDATE step_content SET locked = TRUE WHERE journey_id = %s", (world.N1,))
    assert upsert_step_content(world.N1, n_step, "AI overwrite", [], "gpt") is False
    assert _content(db, world.N1, n_step)["content"] == "AI body of Step 1"


def test_inv05_upsert_still_caches_ordinary_journeys(world, db):
    from app.services.ai_service import upsert_step_content
    n_step = f.step_ids(db, world.N1)[0]
    assert upsert_step_content(world.N1, n_step, "Fresh AI body", [], "gpt") is True
    assert _content(db, world.N1, n_step)["content"] == "Fresh AI body"


def test_inv05_cache_miss_on_a_school_course_is_409_without_generation(client, world, db, monkeypatch):
    gen = AsyncMock(side_effect=AssertionError("model call"))
    monkeypatch.setattr("app.api.v1.endpoints.journeys.generate_step_content", gen)
    s2 = f.step_ids(db, world.C1)[1]
    f.fetch(db, "DELETE FROM step_content WHERE journey_id = %s AND step_id = %s", (world.C1, s2))
    for persona in ("T", "S"):
        r = client.get(f"/api/v1/journeys/{world.C1}/steps/{s2}/content", headers=world.headers(persona))
        assert r.status_code == 409 and r.json()["detail"]["error"] == "content_not_published"
    assert gen.call_count == 0 and _content(db, world.C1, s2) is None


def test_inv05_stale_prompt_version_never_triggers_regen_for_school_courses(client, world, db, monkeypatch):
    task = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.journeys._regenerate_step_task", task)
    f.fetch(db, "UPDATE step_content SET prompt_version = 1 WHERE journey_id IN (%s, %s)", (world.C1, world.N1))
    s1 = f.step_ids(db, world.C1)[0]
    assert client.get(f"/api/v1/journeys/{world.C1}/steps/{s1}/content", headers=world.headers("S")).status_code == 200
    assert task.call_count == 0
    # control: an ordinary journey still refreshes stale content in the background
    n1 = f.step_ids(db, world.N1)[0]
    assert client.get(f"/api/v1/journeys/{world.N1}/steps/{n1}/content", headers=world.headers("OUT")).status_code == 200
    assert task.call_count == 1


def test_inv05_regenerate_endpoint_refuses_school_courses(client, world, db, monkeypatch):
    gen = AsyncMock(side_effect=AssertionError("model call"))
    monkeypatch.setattr("app.api.v1.endpoints.journeys.generate_step_content", gen)
    s1 = f.step_ids(db, world.C1)[0]
    for persona in ("T", "SA"):
        r = client.post(f"/api/v1/journeys/{world.C1}/steps/{s1}/content/regenerate", headers=world.headers(persona))
        assert r.status_code == 409 and r.json()["detail"]["error"] == "content_locked"
    assert gen.call_count == 0
    assert _content(db, world.C1, s1)["content"] == "Published body of Step 1"


@pytest.mark.parametrize("tag", ["too_generic", "too_basic", "too_advanced"])
def test_inv05_negative_feedback_is_stored_but_never_regenerates(client, world, db, monkeypatch, tag):
    task = AsyncMock()
    monkeypatch.setattr("app.api.v1.endpoints.journeys._regenerate_step_task", task)
    s1 = f.step_ids(db, world.C1)[0]
    r = client.post(f"/api/v1/journeys/{world.C1}/steps/{s1}/feedback",
                    json={"rating": "down", "tag": tag}, headers=world.headers("S"))
    assert r.json() == {"ok": True, "regenerating": False}
    assert task.call_count == 0
    assert f.fetch(db, "SELECT tag FROM step_feedback WHERE uid = %s", (world.S,)) == [{"tag": tag}]


async def test_inv05_warm_up_and_background_regen_skip_school_courses(world, db, monkeypatch):
    from app.api.v1.endpoints import journeys
    from app.services import ai_service
    gen = AsyncMock(return_value=("AI body", [], 1, 1))
    monkeypatch.setattr(ai_service, "generate_step_content", gen)
    monkeypatch.setattr(journeys, "generate_step_content", gen)
    monkeypatch.setattr(journeys, "check_budget", lambda uid: (True, "ok"))
    monkeypatch.setattr(journeys, "record_usage", lambda *a, **k: None)

    course = journeys._db_journey(world.C1)
    await ai_service.warm_journey_steps(course, uid=world.T)
    s1 = f.step_ids(db, world.C1)[0]
    await journeys._regenerate_step_task(world.C1, s1, world.T, "note")

    assert gen.call_count == 0
    assert _content(db, world.C1, s1)["content"] == "Published body of Step 1"
    assert _content(db, world.C1, s1)["locked"] is True


# ── INV-06 ────────────────────────────────────────────────────────────────────

def test_inv06_sitemap(client, world):
    body = client.get("/api/v1/sitemap").text
    assert world.N1 in body
    assert world.C1 not in body and world.CB not in body and world.C_DRAFT not in body


def test_inv06_marketplace_and_admin_queue(client, world, db):
    f.fetch(db, "UPDATE journeys SET marketplace_status = 'published' WHERE id = %s", (world.N1,))
    listed = {j["id"] for j in client.get("/api/v1/journeys/marketplace").json()["journeys"]}
    assert listed == {world.N1}

    queue = client.get("/api/v1/admin/marketplace-queue?status=all", headers=world.headers("ADM")).json()["queue"]
    ids = {j["id"] for j in queue}
    assert world.N1 in ids and world.C1 not in ids
    r = client.post(f"/api/v1/admin/marketplace-queue/{world.C1}/approve", headers=world.headers("ADM"))
    assert r.status_code == 404


def test_inv06_admin_content_stats(client, world, db):
    for journey in (world.C1, world.N1):
        step = f.step_ids(db, journey)[0]
        f.fetch(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, %s)",
                (world.S, journey, step))
    top = client.get("/api/v1/admin/content-stats", headers=world.headers("ADM")).json()["top_journeys"]
    ids = {j["id"] for j in top}
    assert world.N1 in ids and world.C1 not in ids


def test_inv06_recommendation_pool(client, world, db, monkeypatch):
    from app.api.v1.endpoints import journeys
    seen: list[str] = []

    def spy(j, *args):
        seen.append(j.id)
        return 0.0

    monkeypatch.setattr(journeys, "_score_journey", spy)
    r = client.get("/api/v1/journeys/recommendations", headers=world.headers("T"))
    assert r.status_code == 200, r.text
    assert world.N1 in seen
    assert world.C1 not in seen and world.CB not in seen


def test_inv06_suggestion_pool(client, world, db, monkeypatch):
    from app.api.v1.endpoints import journeys
    captured = {}

    def spy(**kwargs):
        captured["pool"] = {j.id for j in kwargs["pool"]}
        return None, [], None

    monkeypatch.setattr(journeys, "pick_suggestions", spy)
    monkeypatch.setattr(journeys, "generate_next_level", AsyncMock(return_value=None))
    r = client.get(f"/api/v1/journeys/{world.N1}/suggestions", headers=world.headers("OUT"))
    assert r.status_code == 200, r.text
    assert world.C1 not in captured["pool"] and world.CB not in captured["pool"]


async def test_inv06_popularity_scan_never_queues_school_courses(world, db):
    from app.services.scheduler import _marketplace_popularity_scan
    for journey in (world.C1, world.N1):
        step = f.step_ids(db, journey)[0]
        for learner in (world.S, world.S2, world.OUT):
            f.fetch(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, %s)",
                    (learner, journey, step))
    await _marketplace_popularity_scan()
    status = {r["id"]: r["marketplace_status"]
              for r in f.fetch(db, "SELECT id, marketplace_status FROM journeys WHERE id IN (%s, %s)",
                               (world.C1, world.N1))}
    assert status == {world.C1: "private", world.N1: "pending_review"}


# ── INV-13a ───────────────────────────────────────────────────────────────────

def test_inv13a_deleting_a_teachers_account_keeps_school_courses(world, db):
    from app.services.account_service import delete_user_account
    delete_user_account(world.T)

    assert f.fetch(db, "SELECT uid FROM users WHERE uid = %s", (world.T,)) == []
    course = f.fetch(db, "SELECT school_id::text, uid FROM journeys WHERE id = %s", (world.C1,))
    assert course == [{"school_id": world.school_a["id"], "uid": None}]
    assert f.fetch(db, "SELECT status, created_by FROM school_courses WHERE journey_id = %s", (world.C1,)) == [
        {"status": "published", "created_by": None}
    ]
    assert len(f.fetch(db, "SELECT 1 FROM step_content WHERE journey_id = %s", (world.C1,))) == 2
    assert f.fetch(db, "SELECT 1 FROM school_members WHERE uid = %s", (world.T,)) == []
    assert f.fetch(db, "SELECT 1 FROM class_teachers WHERE uid = %s", (world.T,)) == []
    # the class keeps learning
    assert len(f.fetch(db, "SELECT 1 FROM course_assignments WHERE journey_id = %s", (world.C1,))) == 1
