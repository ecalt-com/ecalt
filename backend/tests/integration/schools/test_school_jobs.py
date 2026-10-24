"""Background-job queue + worker (README §3.13, M3 SC-30x backbone).

The queue is what document extraction and course generation run on, so its
mechanics are load-bearing: claim-once semantics, capped retries with backoff,
cancellation, per-school concurrency and stale-lock recovery.
"""
import pytest

from app.services import school_jobs as sj
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


@pytest.fixture
def handlers(monkeypatch):
    """Isolate the module-level handler registry so a test's fake handlers
    never leak into another test."""
    monkeypatch.setattr(sj, "_HANDLERS", {})
    return sj._HANDLERS


@pytest.fixture
def school(db):
    return f.make_school(db, name="Jobs School")


def _running(db, job_id, *, attempts=1, max_attempts=3, locked_min_ago=0):
    """Force a job into the 'running' state as if a worker had claimed it."""
    f.fetch(db, """
        UPDATE school_jobs
           SET status = 'running', attempts = %s, max_attempts = %s,
               locked_by = 'w', locked_at = now() - make_interval(mins => %s), started_at = now()
         WHERE id = %s
    """, (attempts, max_attempts, locked_min_ago, job_id))


def test_enqueue_and_read(school, db):
    job_id = sj.enqueue(school["id"], "extract", {"document_id": "d1"}, created_by=None)
    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "queued" and job["kind"] == "extract"
    assert job["progress"] == {} and job["attempts"] == 0
    # Scoped to the school: another school can't read it.
    other = f.make_school(db, name="Other")
    assert sj.get_job(other["id"], job_id) is None
    with pytest.raises(ValueError):
        sj.enqueue(school["id"], "not_a_kind", {})


def test_process_one_runs_handler_and_stores_result(school, handlers):
    seen = {}

    def handle(job):
        seen["payload"] = job["payload"]
        sj.update_progress(str(job["id"]), {"steps_done": 1, "steps_total": 1})
        return {"chunks": 7}

    sj.register_handler("extract", handle)
    job_id = sj.enqueue(school["id"], "extract", {"document_id": "d1"})

    assert sj.process_one("w1") is True
    assert sj.process_one("w1") is False  # queue now empty

    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "succeeded"
    assert job["result"] == {"chunks": 7} and job["attempts"] == 1
    assert job["progress"] == {"steps_done": 1, "steps_total": 1}
    assert seen["payload"] == {"document_id": "d1"}


def test_failure_retries_with_backoff_then_fails(school, handlers, db):
    def boom(job):
        raise RuntimeError("kaboom")

    sj.register_handler("build", boom)
    job_id = sj.enqueue(school["id"], "build", {}, max_attempts=2)

    sj.process_one("w1")                          # attempt 1 → retry
    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "queued" and job["attempts"] == 1
    assert "kaboom" in job["error"]
    # Backoff pushes run_after into the future, so it isn't immediately claimable.
    assert sj.process_one("w1") is False
    assert f.fetch(db, "SELECT run_after > now() AS later FROM school_jobs WHERE id = %s", (job_id,))[0]["later"]

    # Make it runnable again; the second failure is terminal (max_attempts=2).
    f.fetch(db, "UPDATE school_jobs SET run_after = now() WHERE id = %s", (job_id,))
    sj.process_one("w1")
    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "failed" and job["attempts"] == 2


def test_no_handler_fails_the_job(school, handlers):
    job_id = sj.enqueue(school["id"], "outline", {})
    sj.process_one("w1")
    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "failed" and "no handler" in job["error"]


def test_cancel_queued_job_immediately(school, handlers):
    job_id = sj.enqueue(school["id"], "extract", {})
    assert sj.request_cancel(school["id"], job_id) == "cancelled"
    job = sj.get_job(school["id"], job_id)
    assert job["status"] == "cancelled" and job["finished_at"] is not None
    # A cancelled job is never claimed.
    assert sj.process_one("w1") is False


def test_cancel_while_running(school, handlers):
    def handle(job):
        jid = str(job["id"])
        sj.request_cancel(job["school_id"], jid)  # external cancel arrives mid-run
        sj.raise_if_cancelled(jid)                # handler's checkpoint
        return {"should": "not reach"}

    sj.register_handler("build", handle)
    job_id = sj.enqueue(school["id"], "build", {})
    sj.process_one("w1")
    assert sj.get_job(school["id"], job_id)["status"] == "cancelled"


def test_per_school_concurrency_cap(school, handlers, db, monkeypatch):
    monkeypatch.setattr(sj.settings, "SCHOOL_JOBS_PER_SCHOOL_CONCURRENCY", 1)
    other = f.make_school(db, name="Busy Neighbour")

    busy = sj.enqueue(school["id"], "build", {})
    _running(db, busy)                            # school A already at its cap of 1
    blocked = sj.enqueue(school["id"], "build", {})
    free = sj.enqueue(other["id"], "build", {})

    claimed = sj._claim_one("w1")
    # The claim skips school A (at cap) and takes school B's job instead.
    assert claimed is not None and str(claimed["id"]) == free
    assert sj.get_job(school["id"], blocked)["status"] == "queued"


def test_requeue_stale_jobs(school, handlers, db, monkeypatch):
    monkeypatch.setattr(sj.settings, "SCHOOL_JOBS_STALE_LOCK_MINUTES", 10)
    recoverable = sj.enqueue(school["id"], "extract", {})
    exhausted = sj.enqueue(school["id"], "extract", {})
    _running(db, recoverable, attempts=1, max_attempts=3, locked_min_ago=20)
    _running(db, exhausted, attempts=3, max_attempts=3, locked_min_ago=20)
    fresh = sj.enqueue(school["id"], "extract", {})
    _running(db, fresh, attempts=1, max_attempts=3, locked_min_ago=0)

    touched = sj.requeue_stale_jobs()
    assert touched == 2
    assert sj.get_job(school["id"], recoverable)["status"] == "queued"
    assert sj.get_job(school["id"], exhausted)["status"] == "failed"
    assert sj.get_job(school["id"], fresh)["status"] == "running"  # lock still fresh
