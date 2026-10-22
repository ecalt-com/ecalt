"""DB-backed background-job queue + in-process worker for schools (README §3.13).

The heavy school work — extracting an uploaded document, generating a course
outline, building step content, proposing updates — runs out of band so the
request path stays fast and a slow model call never holds a web worker. The
queue is the `school_jobs` table; a small pool of worker threads claims rows
with ``FOR UPDATE SKIP LOCKED`` (safe even if Railway ever runs more than one
replica), runs a per-kind handler, and records success or failure with capped
retries and backoff.

Design notes:
  * Independent of the notification scheduler (`SCHEDULER_ENABLED`): the worker
    is gated on its own flag `SCHOOL_JOBS_WORKER_ENABLED` so dev can process
    jobs. Like the scheduler it must point at the right DB — keep it off locally
    unless pointed at a local database.
  * Concurrency is capped globally (`SCHOOL_JOBS_MAX_CONCURRENCY`) and per school
    (`SCHOOL_JOBS_PER_SCHOOL_CONCURRENCY`) so one busy school can't starve the
    others. The per-school cap is a soft limit enforced at claim time.
  * A `running` job whose lock is older than `SCHOOL_JOBS_STALE_LOCK_MINUTES` is
    assumed dead (lost to a redeploy) and re-queued, or failed once retries run
    out.
  * Handlers register themselves by kind. They receive the claimed job row and
    return a JSON-serialisable result; raising aborts the attempt. A handler
    that may run for a while should call :func:`raise_if_cancelled` between
    steps and :func:`update_progress` to report progress the UI polls.

Tests drive the queue synchronously with :func:`process_one`; production uses
the thread pool started by :func:`start_worker` from the app lifespan.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import uuid
from typing import Callable, Optional

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

# Job kinds the schema allows (school_jobs.kind CHECK). Kept here so enqueue can
# fail fast with a clear error instead of a constraint violation.
JOB_KINDS = ("extract", "ocr", "outline", "build", "regenerate_step", "propose_update")

JobHandler = Callable[[dict], Optional[dict]]
_HANDLERS: dict[str, JobHandler] = {}


class JobCancelled(Exception):
    """Raised by a handler (via :func:`raise_if_cancelled`) when a cancel was
    requested; the worker records the job as ``cancelled`` rather than failed."""


def register_handler(kind: str, fn: JobHandler) -> None:
    """Register the handler for a job kind. Called at import time by each
    handler module; the worker imports those modules on startup."""
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    _HANDLERS[kind] = fn


def _load_handlers() -> None:
    """Import the modules that register handlers. Imported lazily (not at module
    load) to avoid a circular import with the services that enqueue jobs."""
    try:  # handlers land with M3/M4; tolerate their absence so the queue still runs
        import app.services.school_ingest_service  # noqa: F401  (registers 'extract')
    except Exception:  # pragma: no cover - defensive until M3 lands
        logger.debug("no ingest handler to load yet", exc_info=True)


# ── Enqueue / read / cancel ──────────────────────────────────────────────────

def enqueue(
    school_id: str,
    kind: str,
    payload: Optional[dict] = None,
    *,
    created_by: Optional[str] = None,
    max_attempts: int = 3,
) -> str:
    """Add a job to the queue and return its id. Idempotency is the caller's
    concern — handlers are written to be safe to run more than once."""
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO school_jobs (school_id, kind, payload, max_attempts, created_by)
                VALUES (%s, %s, %s::jsonb, %s, %s)
                RETURNING id
                """,
                (school_id, kind, json.dumps(payload or {}), max_attempts, created_by),
            )
            return str(cur.fetchone()["id"])


def get_job(school_id: str, job_id: str) -> Optional[dict]:
    """A job scoped to its school (so one school can't read another's). Returns
    a trimmed, API-safe view (no internal lock columns)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, school_id, kind, status, progress, result, error,
                       attempts, max_attempts, cancel_requested,
                       created_at, started_at, finished_at
                  FROM school_jobs
                 WHERE id = %s AND school_id = %s
                """,
                (job_id, school_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def request_cancel(school_id: str, job_id: str) -> Optional[str]:
    """Ask for a job to stop. A queued job is cancelled immediately; a running
    one gets ``cancel_requested`` set and stops at its next checkpoint. Returns
    the resulting status, or None if the job doesn't exist / isn't cancellable."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                       cancel_requested = true,
                       finished_at = CASE WHEN status = 'queued' THEN now() ELSE finished_at END
                 WHERE id = %s AND school_id = %s AND status IN ('queued', 'running')
                RETURNING status
                """,
                (job_id, school_id),
            )
            row = cur.fetchone()
            return row["status"] if row else None


# ── Handler helpers ──────────────────────────────────────────────────────────

def raise_if_cancelled(job_id: str) -> None:
    """Handlers call this between steps so a cancel takes effect promptly."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cancel_requested FROM school_jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
    if row and row["cancel_requested"]:
        raise JobCancelled()


def update_progress(job_id: str, progress: dict) -> None:
    """Replace a job's progress blob (e.g. ``{"steps_done": 3, "steps_total": 8}``)
    for the UI to poll. Best-effort: a progress write never aborts the job."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE school_jobs SET progress = %s::jsonb WHERE id = %s",
                    (json.dumps(progress), job_id),
                )
    except Exception:  # pragma: no cover - progress is advisory
        logger.warning("failed to update progress for job %s", job_id, exc_info=True)


# ── Worker internals ─────────────────────────────────────────────────────────

def requeue_stale_jobs() -> int:
    """Recover jobs whose worker vanished (redeploy, crash): a `running` row
    whose lock is older than the stale window is re-queued if it has retries
    left, otherwise failed. Returns how many rows it touched."""
    touched = 0
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = 'queued', locked_at = NULL, locked_by = NULL
                 WHERE status = 'running'
                   AND locked_at < now() - make_interval(mins => %s)
                   AND attempts < max_attempts
                """,
                (settings.SCHOOL_JOBS_STALE_LOCK_MINUTES,),
            )
            touched += cur.rowcount
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = 'failed', finished_at = now(),
                       error = 'worker lost the job and retries are exhausted'
                 WHERE status = 'running'
                   AND locked_at < now() - make_interval(mins => %s)
                   AND attempts >= max_attempts
                """,
                (settings.SCHOOL_JOBS_STALE_LOCK_MINUTES,),
            )
            touched += cur.rowcount
    return touched


def _claim_one(worker_id: str) -> Optional[dict]:
    """Atomically claim the oldest runnable job, honouring the per-school cap.
    Uses FOR UPDATE SKIP LOCKED so concurrent workers never fight over a row."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = 'running', locked_at = now(), locked_by = %s,
                       started_at = COALESCE(started_at, now()),
                       attempts = attempts + 1
                 WHERE id = (
                    SELECT j.id FROM school_jobs j
                     WHERE j.status = 'queued'
                       AND j.run_after <= now()
                       AND (SELECT count(*) FROM school_jobs r
                             WHERE r.school_id = j.school_id AND r.status = 'running')
                           < %s
                     ORDER BY j.run_after, j.created_at
                     FOR UPDATE SKIP LOCKED
                     LIMIT 1
                 )
                RETURNING *
                """,
                (worker_id, settings.SCHOOL_JOBS_PER_SCHOOL_CONCURRENCY),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _finish(job_id: str, status: str, *, result: Optional[dict] = None, error: Optional[str] = None) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = %s, finished_at = now(), locked_at = NULL, locked_by = NULL,
                       result = COALESCE(%s::jsonb, result), error = %s
                 WHERE id = %s
                """,
                (status, json.dumps(result) if result is not None else None, error, job_id),
            )


def _retry_later(job_id: str, attempts: int, error: str) -> None:
    """Return a failed-but-retriable job to the queue with exponential backoff."""
    backoff = min(600, 15 * (2 ** max(0, attempts - 1)))  # 15s, 30s, 60s … capped at 10 min
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = 'queued', locked_at = NULL, locked_by = NULL,
                       run_after = now() + make_interval(secs => %s), error = %s
                 WHERE id = %s
                """,
                (backoff, error, job_id),
            )


def run_job(job: dict) -> str:
    """Run a claimed job's handler and record the outcome. Returns the final
    status. Never raises — a handler failure becomes a retry or a failed row."""
    job_id = str(job["id"])
    kind = job["kind"]
    handler = _HANDLERS.get(kind)
    if handler is None:
        _finish(job_id, "failed", error=f"no handler registered for kind '{kind}'")
        logger.error("school job %s has no handler for kind %s", job_id, kind)
        return "failed"
    try:
        result = handler(job)
        _finish(job_id, "succeeded", result=result if isinstance(result, dict) else None)
        return "succeeded"
    except JobCancelled:
        _finish(job_id, "cancelled")
        logger.info("school job %s (%s) cancelled", job_id, kind)
        return "cancelled"
    except Exception as exc:  # handler bug or transient failure
        error = f"{type(exc).__name__}: {exc}"[:2000]
        if job["attempts"] >= job["max_attempts"]:
            _finish(job_id, "failed", error=error)
            logger.exception("school job %s (%s) failed permanently", job_id, kind)
            return "failed"
        _retry_later(job_id, job["attempts"], error)
        logger.warning("school job %s (%s) failed, will retry (attempt %s/%s): %s",
                       job_id, kind, job["attempts"], job["max_attempts"], error)
        return "queued"


def process_one(worker_id: str = "sync") -> bool:
    """Claim and run a single job. Returns True if a job ran. Used by the worker
    loop and by tests to drive the queue deterministically."""
    job = _claim_one(worker_id)
    if job is None:
        return False
    run_job(job)
    return True


# ── Worker thread pool (production) ──────────────────────────────────────────

_stop = threading.Event()
_threads: list[threading.Thread] = []


def _worker_loop(worker_id: str) -> None:
    while not _stop.is_set():
        try:
            if worker_id.endswith("-0"):  # one worker handles stale-lock sweeps
                requeue_stale_jobs()
            ran = process_one(worker_id)
        except Exception:  # never let the loop die on a transient DB error
            logger.exception("school job worker %s hit an error; backing off", worker_id)
            ran = False
        if not ran:
            _stop.wait(settings.SCHOOL_JOBS_POLL_SECONDS)


def start_worker() -> bool:
    """Start the worker thread pool. No-op (returns False) when disabled or
    already running. Called from the app lifespan."""
    if not settings.SCHOOL_JOBS_WORKER_ENABLED:
        logger.info("school jobs worker disabled (SCHOOL_JOBS_WORKER_ENABLED=false)")
        return False
    if _threads:
        return False
    _load_handlers()
    _stop.clear()
    host = socket.gethostname()[:40]
    count = max(1, settings.SCHOOL_JOBS_MAX_CONCURRENCY)
    for i in range(count):
        worker_id = f"{host}-{uuid.uuid4().hex[:6]}-{i}"
        t = threading.Thread(target=_worker_loop, args=(worker_id,), name=f"school-jobs-{i}", daemon=True)
        t.start()
        _threads.append(t)
    logger.info("school jobs worker started with %s threads", count)
    return True


def stop_worker(timeout: float = 5.0) -> None:
    """Signal the pool to stop and wait briefly for the threads to drain."""
    _stop.set()
    for t in _threads:
        t.join(timeout=timeout)
    _threads.clear()
