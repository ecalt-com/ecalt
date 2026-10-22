"""School AI course builder — course lifecycle + outline kickoff (M4 SC-402/403).

A school course is a `journeys` row (uid NULL, school-owned) + a `school_courses`
row + a chain of `course_versions`; the working **draft** is the version in state
'draft', whose `meta.status` tracks the build pipeline
(empty → outlining → outline_ready → building → built) and whose `steps` holds the
outline/step content. This module creates courses, attaches ready documents,
estimates the generation cost, and kicks off the outline job. The heavy
generation lives in `school_course_builder`.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import SchoolCtx, uuid_or_404
from app.services import school_jobs, subscription_service
from app.services.provider_service import cost_for_tokens, get_config
from app.services.school_service import school_audit

# Very rough token estimate for budgeting (≈ 4 chars/token).
def _tokens(chars: int) -> int:
    return max(1, chars // 4)


# ── Create / list / get ──────────────────────────────────────────────────────

def create_course(ctx: SchoolCtx, title: str, document_ids: list) -> dict:
    """Create a draft course from one or more **ready** source documents."""
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail={"error": "title_required", "message": "Give the course a title."})
    doc_ids = [uuid_or_404(d, "document_not_found") for d in (document_ids or [])]
    if not doc_ids:
        raise HTTPException(status_code=422, detail={
            "error": "no_documents", "message": "Pick at least one uploaded document to build from."})

    journey_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM source_documents WHERE school_id = %s AND id = ANY(%s::uuid[])",
                (ctx.school_id, doc_ids),
            )
            found = {str(r["id"]): r["status"] for r in cur.fetchall()}
            missing = [d for d in doc_ids if d not in found]
            if missing:
                raise HTTPException(status_code=404, detail={"error": "document_not_found", "message": "Document not found."})
            not_ready = [d for d in doc_ids if found[d] != "ready"]
            if not_ready:
                raise HTTPException(status_code=409, detail={
                    "error": "document_not_ready",
                    "message": "Those documents are still being read. Wait until they're ready, then try again."})

            cur.execute(
                """
                INSERT INTO journeys (id, uid, school_id, question, title, description, estimated_hours, steps)
                VALUES (%s, NULL, %s, %s, %s, %s, 0, '[]'::jsonb)
                """,
                (journey_id, ctx.school_id, title, title, ""),
            )
            cur.execute(
                """
                INSERT INTO school_courses (journey_id, school_id, status, created_by)
                VALUES (%s, %s, 'draft', %s)
                """,
                (journey_id, ctx.school_id, ctx.uid),
            )
            cur.execute(
                """
                INSERT INTO course_versions (journey_id, version, state, revision, meta, steps, created_by)
                VALUES (%s, 1, 'draft', 0, %s::jsonb, '[]'::jsonb, %s)
                """,
                (journey_id, json.dumps({"status": "empty"}), ctx.uid),
            )
            for d in doc_ids:
                cur.execute(
                    "INSERT INTO course_sources (journey_id, document_id, school_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (journey_id, d, ctx.school_id),
                )
            school_audit(cur, ctx.school_id, ctx.uid, "course.created", "course", journey_id,
                         {"documents": len(doc_ids)})
    return get_course(ctx, journey_id)


def list_courses(ctx: SchoolCtx) -> list:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.journey_id, j.title, sc.status, sc.published_version, sc.created_at, sc.updated_at,
                       (cv.meta->>'status') AS draft_status,
                       jsonb_array_length(COALESCE(cv.steps, '[]'::jsonb)) AS step_count
                  FROM school_courses sc
                  JOIN journeys j ON j.id = sc.journey_id
                  LEFT JOIN course_versions cv ON cv.journey_id = sc.journey_id AND cv.state = 'draft'
                 WHERE sc.school_id = %s AND sc.status <> 'archived'
                 ORDER BY sc.updated_at DESC
                """,
                (ctx.school_id,),
            )
            return [{
                "journey_id": r["journey_id"], "title": r["title"], "status": r["status"],
                "published_version": r["published_version"], "draft_status": r["draft_status"],
                "step_count": r["step_count"] or 0,
                "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
            } for r in cur.fetchall()]


def get_course(ctx: SchoolCtx, journey_id: str) -> dict:
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    draft = _draft_version(journey_id)
    sources = _sources(ctx.school_id, journey_id)
    return {
        "journey_id": journey_id,
        "title": course["title"],
        "status": course["status"],
        "published_version": course["published_version"],
        "documents": sources,
        "draft": {
            "version": draft["version"], "revision": draft["revision"],
            "status": (draft["meta"] or {}).get("status", "empty"),
            "meta": draft["meta"] or {}, "steps": draft["steps"] or [],
        } if draft else None,
    }


# ── Estimate + outline kickoff ───────────────────────────────────────────────

def estimate(ctx: SchoolCtx, journey_id: str) -> dict:
    """Ballpark the generation cost from the source chunk sizes, so the UI can
    warn before spending the school's budget."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    _load_course(ctx.school_id, journey_id)
    chunks = course_chunks(ctx.school_id, journey_id)
    total_chars = sum(c["char_count"] for c in chunks)
    input_tokens = _tokens(total_chars)
    # The build pass dominates: it re-reads cited chunks and writes bodies. Scale
    # the raw input tokens up for output + per-step overhead, priced at the
    # step-content model's rate.
    model = get_config("school_step_content")["model"]
    est_in = int(input_tokens * 1.4)
    est_out = int(input_tokens * 0.6)
    return {
        "document_count": len({c["document_id"] for c in chunks}),
        "chunk_count": len(chunks),
        "input_tokens": input_tokens,
        "estimated_cost_cents": round(cost_for_tokens(model, est_in, est_out), 2),
    }


def start_outline(ctx: SchoolCtx, journey_id: str, inputs: dict) -> dict:
    """Budget-check, then enqueue the outline generation job."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] != "draft":
        raise HTTPException(status_code=409, detail={
            "error": "course_not_draft", "message": "This course can't be regenerated once published."})
    if not course_chunks(ctx.school_id, journey_id):
        raise HTTPException(status_code=409, detail={
            "error": "no_source_text", "message": "The source documents have no readable text yet."})
    allowed, reason = subscription_service.check_school_budget(ctx.school_id)
    if not allowed:
        raise HTTPException(status_code=402, detail=subscription_service.budget_error_detail(reason))

    draft = _draft_version(journey_id)
    _set_meta(journey_id, {**(draft["meta"] or {}), "status": "outlining", "inputs": inputs})
    job_id = school_jobs.enqueue(ctx.school_id, "outline", {"journey_id": journey_id, "inputs": inputs},
                                 created_by=ctx.uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            school_audit(cur, ctx.school_id, ctx.uid, "course.outline_started", "course", journey_id)
    return {"job_id": job_id, "status": "outlining"}


# ── Chunk gathering (shared with the builder) ────────────────────────────────

def course_chunks(school_id: str, journey_id: str) -> list:
    """Every source chunk for the course, ordered and assigned a stable 0-based
    `cite_id` the model uses to ground steps. Spans multiple documents."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dc.id, dc.document_id, dc.ordinal, dc.heading_path, dc.page_start, dc.page_end,
                       dc.text, dc.char_count, sd.filename
                  FROM course_sources cs
                  JOIN document_chunks dc ON dc.document_id = cs.document_id
                  JOIN source_documents sd ON sd.id = cs.document_id
                 WHERE cs.journey_id = %s AND cs.school_id = %s AND sd.status <> 'deleted'
                 ORDER BY sd.created_at, dc.document_id, dc.ordinal
                """,
                (journey_id, school_id),
            )
            rows = cur.fetchall()
    return [{
        "cite_id": i, "chunk_id": str(r["id"]), "document_id": str(r["document_id"]),
        "heading_path": r["heading_path"] or [], "page_start": r["page_start"], "page_end": r["page_end"],
        "text": r["text"], "char_count": r["char_count"], "filename": r["filename"],
    } for i, r in enumerate(rows)]


# ── Internals ────────────────────────────────────────────────────────────────

def _load_course(school_id: str, journey_id: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.journey_id, sc.status, sc.published_version, j.title
                  FROM school_courses sc JOIN journeys j ON j.id = sc.journey_id
                 WHERE sc.journey_id = %s AND sc.school_id = %s
                """,
                (journey_id, school_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "course_not_found", "message": "Course not found."})
    return dict(row)


def _draft_version(journey_id: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version, state, revision, meta, steps FROM course_versions "
                "WHERE journey_id = %s AND state = 'draft'",
                (journey_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _sources(school_id: str, journey_id: str) -> list:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sd.id, sd.filename, sd.status, sd.page_count
                  FROM course_sources cs JOIN source_documents sd ON sd.id = cs.document_id
                 WHERE cs.journey_id = %s AND cs.school_id = %s
                 ORDER BY sd.created_at
                """,
                (journey_id, school_id),
            )
            return [{"id": str(r["id"]), "filename": r["filename"], "status": r["status"],
                     "page_count": r["page_count"]} for r in cur.fetchall()]


def _set_meta(journey_id: str, meta: dict) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE course_versions SET meta = %s::jsonb, updated_at = now() "
                "WHERE journey_id = %s AND state = 'draft'",
                (json.dumps(meta), journey_id),
            )


def _iso(ts) -> Optional[str]:
    return ts.isoformat() if ts else None
