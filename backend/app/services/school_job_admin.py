"""ECALT support view of the school job queue (SC-805 / SC-806).

- `list_jobs` / `retry_job` / `cancel_job`: admin tools for failed and stuck
  jobs across every school (staff can already cancel their own).
- `queue_health` + the scheduler's `school_jobs_health` check: log an ERROR
  (→ Sentry alert) when jobs fail or the queue stops moving, e.g. because no
  instance runs the worker.

Errors stored on jobs are exception messages from our own code; they never
include document text or student data, but the list truncates them anyway.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import uuid_or_404

logger = logging.getLogger(__name__)

STUCK_QUEUED_MINUTES = 15   # queued + runnable this long → the worker isn't picking jobs up
STUCK_RUNNING_MINUTES = 30  # running this long without finishing


def _row(r: dict) -> dict:
    out = dict(r)
    for k in ("id", "school_id"):
        out[k] = str(out[k]) if out.get(k) else None
    for k in ("created_at", "started_at", "finished_at", "run_after", "locked_at"):
        if out.get(k):
            out[k] = out[k].isoformat()
    out["error"] = (out.get("error") or "")[:300] or None
    return out


def list_jobs(state: str = "attention", limit: int = 100) -> list[dict]:
    """state: 'attention' (failed in the last 7 days + stuck), 'failed', 'stuck', 'active'."""
    where = {
        "failed": "j.status = 'failed' AND j.finished_at > now() - interval '7 days'",
        "stuck": (f"((j.status = 'queued' AND j.run_after < now() - interval '{STUCK_QUEUED_MINUTES} minutes') "
                  f"OR (j.status = 'running' AND j.started_at < now() - interval '{STUCK_RUNNING_MINUTES} minutes'))"),
        "active": "j.status IN ('queued', 'running')",
    }
    where["attention"] = f"(({where['failed']}) OR ({where['stuck']}))"
    if state not in where:
        raise HTTPException(status_code=422, detail={"error": "invalid_state", "message": "Unknown job filter."})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT j.id, j.school_id, s.name AS school_name, j.kind, j.status, j.attempts, j.max_attempts,
                       j.error, j.created_at, j.started_at, j.finished_at, j.run_after, j.locked_at,
                       j.cancel_requested, j.payload->>'journey_id' AS journey_id
                  FROM school_jobs j JOIN schools s ON s.id = j.school_id
                 WHERE {where[state]}
                 ORDER BY j.created_at DESC
                 LIMIT %s
                """,
                (max(1, min(int(limit), 500)),),
            )
            return [_row(r) for r in cur.fetchall()]


def _load(cur, job_id: str) -> dict:
    cur.execute("SELECT id, school_id, kind, status FROM school_jobs WHERE id = %s FOR UPDATE", (job_id,))
    job = cur.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "message": "Job not found."})
    return job


def retry_job(admin_uid: str, job_id: str) -> dict:
    """Put a failed or cancelled job back in the queue with fresh attempts."""
    from app.services.school_service import school_audit
    job_id = uuid_or_404(job_id, "job_not_found")
    with get_db() as conn:
        with conn.cursor() as cur:
            job = _load(cur, job_id)
            if job["status"] not in ("failed", "cancelled"):
                raise HTTPException(status_code=409, detail={
                    "error": "job_not_retryable", "message": "Only failed or cancelled jobs can be retried."})
            cur.execute(
                """
                UPDATE school_jobs
                   SET status = 'queued', attempts = 0, error = NULL, cancel_requested = FALSE,
                       run_after = now(), finished_at = NULL, locked_at = NULL, locked_by = NULL
                 WHERE id = %s
                RETURNING id, school_id, kind, status, attempts, max_attempts, error, created_at,
                          started_at, finished_at, run_after, locked_at, cancel_requested
                """,
                (job_id,),
            )
            row = cur.fetchone()
            school_audit(cur, str(job["school_id"]), admin_uid, "job.retried_by_ecalt", "job", job_id,
                         {"kind": job["kind"]})
    logger.info("school job %s (%s) re-queued by an ECALT admin", job_id, job["kind"])
    return _row(row)


def cancel_job(admin_uid: str, job_id: str) -> dict:
    """Cancel a queued job now, or ask a running one to stop at its next checkpoint."""
    from app.services.school_service import school_audit
    job_id = uuid_or_404(job_id, "job_not_found")
    with get_db() as conn:
        with conn.cursor() as cur:
            job = _load(cur, job_id)
            if job["status"] == "queued":
                cur.execute("UPDATE school_jobs SET status = 'cancelled', finished_at = now() WHERE id = %s",
                            (job_id,))
                status = "cancelled"
            elif job["status"] == "running":
                cur.execute("UPDATE school_jobs SET cancel_requested = TRUE WHERE id = %s", (job_id,))
                status = "cancel_requested"
            else:
                raise HTTPException(status_code=409, detail={
                    "error": "job_finished", "message": "This job has already finished."})
            school_audit(cur, str(job["school_id"]), admin_uid, "job.cancelled_by_ecalt", "job", job_id,
                         {"kind": job["kind"]})
    return {"id": job_id, "status": status}


def queue_health() -> dict:
    """Counts for the health check and the admin panel."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  count(*) FILTER (WHERE status = 'queued')                                       AS queued,
                  count(*) FILTER (WHERE status = 'running')                                      AS running,
                  count(*) FILTER (WHERE status = 'queued'
                                     AND run_after < now() - interval '{STUCK_QUEUED_MINUTES} minutes') AS stuck_queued,
                  count(*) FILTER (WHERE status = 'running'
                                     AND started_at < now() - interval '{STUCK_RUNNING_MINUTES} minutes') AS stuck_running,
                  count(*) FILTER (WHERE status = 'failed' AND finished_at > now() - interval '1 hour')  AS failed_last_hour,
                  count(*) FILTER (WHERE status = 'failed' AND finished_at > now() - interval '24 hours') AS failed_last_day
                  FROM school_jobs
                """
            )
            return {k: int(v or 0) for k, v in dict(cur.fetchone()).items()}


def check_health() -> dict:
    """Scheduler entry point: log an ERROR (Sentry alerts on it) when the queue
    is stalled or jobs failed in the last hour. Returns the counts."""
    h = queue_health()
    if h["stuck_queued"] or h["stuck_running"]:
        logger.error("school job queue stalled: %s queued > %s min, %s running > %s min "
                     "(is SCHOOL_JOBS_WORKER_ENABLED on exactly one instance?)",
                     h["stuck_queued"], STUCK_QUEUED_MINUTES, h["stuck_running"], STUCK_RUNNING_MINUTES)
    if h["failed_last_hour"]:
        logger.error("school jobs failed in the last hour: %s (admin → Schools → Background jobs)",
                     h["failed_last_hour"])
    return h
