"""AI course builder — optional hero image (M4 SC-409).

A staff member generates a hero image for a course via `image_service`, billed to
the school's AI pool. It's stored on the draft and carried onto the journey at
publish. `fake_images` (autouse) stubs generation + upload.
"""
import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _sid(w):
    return w.school_a["id"]


def test_generate_hero_stores_url_and_bills_the_school(client, world, db):
    jid = f.make_built_draft(db, world.school_a)
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/hero-image", json={},
                    headers=world.headers("SA"))
    assert r.status_code == 200
    url = r.json()["hero_image_url"]
    assert url.endswith(".webp")
    # stored on the draft meta so publish carries it onto the journey
    draft = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()["draft"]
    assert draft["meta"]["hero_image_url"] == url
    # the school's monthly pool was charged
    used = f.fetch(db, "SELECT cost_cents FROM school_usage WHERE school_id = %s", (world.school_a["id"],))
    assert used and float(used[0]["cost_cents"]) > 0


def test_hero_image_carried_through_publish(client, world, db):
    jid = f.make_built_draft(db, world.school_a)
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/hero-image", json={}, headers=world.headers("SA"))
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/publish", json={}, headers=world.headers("SA"))
    hero = f.fetch(db, "SELECT hero_image_url FROM journeys WHERE id = %s", (jid,))[0]["hero_image_url"]
    assert hero and hero.endswith(".webp")


def test_hero_image_unavailable_without_config(client, world, db, monkeypatch):
    import app.services.image_service as image_service
    monkeypatch.setattr(image_service, "images_enabled", lambda: False)
    jid = f.make_built_draft(db, world.school_a)
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/hero-image", json={},
                    headers=world.headers("SA"))
    assert r.status_code == 503 and r.json()["detail"]["error"] == "image_unavailable"
