"""SC-803 offboarding (INV-13c, DBI-DEL-*): a terminated school's data is
deleted after the grace period — students (incl. Firebase logins), courses,
documents and stored files, staff memberships, classes, usage — and nothing
of another school is touched. Only the audit log and pseudonymised consent
events stay."""
import asyncio

import pytest

from app.services import school_offboarding_service as off
from app.services import school_storage_service as storage
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _q(db, sql, *args):
    with db.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def _terminate(db, school, days_ago=31):
    _q(db, "UPDATE schools SET status = 'terminated', terminated_at = now() - make_interval(days => %s) "
           "WHERE id = %s", days_ago, school["id"])


def _seed_learning(db, world):
    """Student activity, a staff preview, a document with a stored file and a hero image."""
    doc = f.make_document(db, world.school_a, uploaded_by=world.T)
    f.add_chunks(db, doc["id"], ["Plants make food from light."])
    _q(db, "UPDATE journeys SET hero_image_url = %s WHERE id = %s",
       f"https://x.supabase.co/storage/v1/object/public/journey-images/{world.C1}.webp", world.C1)
    for uid in (world.S, world.T):
        _q(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, 'step-1')", uid, world.C1)
    _q(db, "INSERT INTO conversations (uid, title) VALUES (%s, 'tutor')", world.S)
    _q(db, "INSERT INTO consent_events (uid, action, method) VALUES (%s, 'granted', 'school_authorization')",
       world.S)
    return doc


def test_purge_deletes_everything_of_the_school_and_nothing_else(db, world, fake_storage, fake_images,
                                                               firebase_deletes):
    doc = _seed_learning(db, world)
    _q(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, 'step-1')", world.XS, world.CB)
    _terminate(db, world.school_a)
    students_a = [world.S, world.S2, world.SX]

    result = asyncio.run(off.purge_school(world.school_a["id"]))

    assert result["status"] == "deleted", result
    assert result["students"] == 3 and result["firebase_failures"] == 0
    assert off.remaining(world.school_a["id"]) == {}

    # Students: accounts and learner data gone, Firebase logins purged.
    assert not _q(db, "SELECT 1 FROM users WHERE uid = ANY(%s)", students_a)
    assert not _q(db, "SELECT 1 FROM conversations WHERE uid = %s", world.S)
    assert not _q(db, "SELECT 1 FROM user_progress WHERE journey_id = %s", world.C1)  # incl. the staff preview
    purged = {c.args[0] for c in firebase_deletes.await_args_list}
    assert set(students_a) <= purged

    # Consent proof survives, pseudonymised.
    assert not _q(db, "SELECT 1 FROM consent_events WHERE uid = %s", world.S)
    assert _q(db, "SELECT 1 FROM consent_events WHERE method = 'school_offboarding'")

    # Courses, documents and stored files.
    assert not _q(db, "SELECT 1 FROM journeys WHERE id = ANY(%s)", [world.C1, world.C_DRAFT])
    assert not _q(db, "SELECT 1 FROM document_chunks WHERE document_id = %s", doc["id"])
    assert doc["storage_path"] in fake_storage.deleted
    assert any(world.C1 in u for u in fake_images.deleted_urls)

    # Staff keep their own accounts; ordinary journeys untouched.
    assert _q(db, "SELECT 1 FROM users WHERE uid = %s", world.T)
    assert _q(db, "SELECT 1 FROM journeys WHERE id = %s", world.N1)

    # School B is untouched.
    assert off.remaining(world.school_b["id"])["school_students"] == 1
    assert _q(db, "SELECT 1 FROM user_progress WHERE uid = %s", world.XS)
    assert _q(db, "SELECT 1 FROM journeys WHERE id = %s", world.CB)

    # The audit trail stays, ending with the deletion record.
    rows = _q(db, "SELECT action, meta FROM school_audit_log WHERE school_id = %s ORDER BY id DESC",
              world.school_a["id"])
    action, meta = rows[0]
    assert action == "school.data_deleted"
    assert meta["students"] == 3 and meta["name"] == "School A"


def test_only_schools_past_the_grace_period_are_due(db, world):
    c = f.make_school(db, name="School C")
    d = f.make_school(db, name="School D")
    _terminate(db, world.school_a, days_ago=31)
    _terminate(db, c, days_ago=29)
    _q(db, "UPDATE schools SET status = 'suspended' WHERE id = %s", d["id"])
    assert off.due_school_ids() == [world.school_a["id"]]


def test_refuses_a_school_that_is_not_terminated(db, world):
    with pytest.raises(off.OffboardingError):
        asyncio.run(off.purge_school(world.school_a["id"]))
    assert _q(db, "SELECT 1 FROM school_students WHERE uid = %s", world.S)


def test_a_failed_file_delete_stops_before_the_database(db, world, monkeypatch):
    doc = _seed_learning(db, world)
    _terminate(db, world.school_a)

    def _fail(path, *, strict=False):
        raise storage.StorageError("bucket unavailable")
    monkeypatch.setattr(storage, "delete", _fail)

    results = asyncio.run(off.run_due())
    assert results[0]["status"] == "failed"
    assert _q(db, "SELECT 1 FROM school_students WHERE uid = %s", world.S)
    assert _q(db, "SELECT 1 FROM source_documents WHERE id = %s", doc["id"])


def test_rerun_is_safe_and_one_failure_does_not_block_others(db, world, monkeypatch):
    _terminate(db, world.school_a)
    _terminate(db, world.school_b)
    real = off._delete_files

    def _flaky(school_id):
        if school_id == world.school_a["id"]:
            raise off.OffboardingError("boom")
        return real(school_id)
    monkeypatch.setattr(off, "_delete_files", _flaky)

    results = {r["school_id"]: r["status"] for r in asyncio.run(off.run_due())}
    assert results == {world.school_a["id"]: "failed", world.school_b["id"]: "deleted"}

    monkeypatch.setattr(off, "_delete_files", real)
    assert [r["status"] for r in asyncio.run(off.run_due())] == ["deleted"]
    assert asyncio.run(off.purge_school(world.school_a["id"]))["status"] == "already_deleted"


def test_admin_view_shows_when_deletion_is_due(db, world, client):
    _terminate(db, world.school_a, days_ago=10)
    r = client.get("/api/v1/admin/schools", headers=world.headers("ADM"))
    assert r.status_code == 200, r.text
    items = r.json().get("schools") or r.json().get("items") or r.json()
    a = next(s for s in items if s["id"] == world.school_a["id"])
    b = next(s for s in items if s["id"] == world.school_b["id"])
    assert a["deletion_due_at"] and b["deletion_due_at"] is None
