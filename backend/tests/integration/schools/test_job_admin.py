"""SC-805/806: ECALT support tools for the school job queue + health alerts."""
import logging

import pytest

from app.services import school_job_admin as ja
from app.services import school_jobs as sj
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db

URL = "/api/v1/admin/schools/jobs"


def _age(db, job_id, col, minutes):
    with db.cursor() as cur:
        cur.execute(f"UPDATE school_jobs SET {col} = now() - make_interval(mins => %s) WHERE id = %s", (minutes, job_id))


def test_list_shows_failed_and_stuck_jobs_across_schools(client, world, db):
    failed = f.enqueue_job(db, world.school_a, status="failed")
    with db.cursor() as cur:
        cur.execute("UPDATE school_jobs SET finished_at = now(), error = 'RuntimeError: boom' WHERE id = %s", (failed,))
    stuck = f.enqueue_job(db, world.school_b)
    _age(db, stuck, "run_after", 20)
    fresh = f.enqueue_job(db, world.school_a)
    r = client.get(URL, headers=world.headers("ADM"))
    assert r.status_code == 200, r.text
    ids = {j["id"]: j for j in r.json()["jobs"]}
    assert failed in ids and stuck in ids and fresh not in ids
    assert ids[failed]["school_name"] == "School A" and ids[failed]["error"] == "RuntimeError: boom"
    health = r.json()["health"]
    assert health["stuck_queued"] == 1 and health["failed_last_day"] == 1
    active = client.get(URL + "?state=active", headers=world.headers("ADM")).json()["jobs"]
    assert {j["id"] for j in active} == {stuck, fresh}


def test_retry_requeues_a_failed_job_and_it_runs(client, world, db, monkeypatch):
    calls = []
    monkeypatch.setitem(sj._HANDLERS, "outline", lambda job: calls.append(job["id"]) or {"ok": True})
    job = f.enqueue_job(db, world.school_a, kind="outline", status="failed")
    with db.cursor() as cur:
        cur.execute("UPDATE school_jobs SET attempts = 3, error = 'x' WHERE id = %s", (job,))
    r = client.post(f"{URL}/{job}/retry", headers=world.headers("ADM"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued" and r.json()["attempts"] == 0
    assert sj.process_one("test") is True and calls
    assert f.fetch(db, "SELECT status FROM school_jobs WHERE id = %s", (job,))[0]["status"] == "succeeded"
    audit = f.fetch(db, "SELECT action FROM school_audit_log WHERE target_id = %s", (job,))
    assert [a["action"] for a in audit] == ["job.retried_by_ecalt"]
    # A succeeded job can't be retried.
    assert client.post(f"{URL}/{job}/retry", headers=world.headers("ADM")).status_code == 409


def test_cancel_queued_now_and_running_at_next_checkpoint(client, world, db):
    queued = f.enqueue_job(db, world.school_a)
    running = f.enqueue_job(db, world.school_a, status="running")
    assert client.post(f"{URL}/{queued}/cancel", headers=world.headers("ADM")).json()["status"] == "cancelled"
    assert client.post(f"{URL}/{running}/cancel", headers=world.headers("ADM")).json()["status"] == "cancel_requested"
    assert f.fetch(db, "SELECT cancel_requested FROM school_jobs WHERE id = %s", (running,))[0]["cancel_requested"]
    assert client.post(f"{URL}/{queued}/cancel", headers=world.headers("ADM")).status_code == 409
    assert client.post(f"{URL}/not-a-uuid/cancel", headers=world.headers("ADM")).status_code == 404


def test_health_check_logs_errors_for_stalls_and_failures(db, world, caplog):
    assert ja.check_health()["stuck_queued"] == 0
    stuck = f.enqueue_job(db, world.school_a)
    _age(db, stuck, "run_after", 20)
    failed = f.enqueue_job(db, world.school_a, status="failed")
    with db.cursor() as cur:
        cur.execute("UPDATE school_jobs SET finished_at = now() WHERE id = %s", (failed,))
    with caplog.at_level(logging.ERROR, logger="app.services.school_job_admin"):
        h = ja.check_health()
    assert h["stuck_queued"] == 1 and h["failed_last_hour"] == 1
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "queue stalled" in msgs and "failed in the last hour" in msgs


def test_job_metrics_are_logged(db, world, caplog, monkeypatch):
    monkeypatch.setitem(sj._HANDLERS, "outline", lambda job: {"ok": True})
    f.enqueue_job(db, world.school_a, kind="outline")
    with caplog.at_level(logging.INFO, logger="app.services.school_jobs"):
        sj.process_one("test")
    assert any("school_job_metric kind=outline status=succeeded" in r.getMessage() for r in caplog.records)
