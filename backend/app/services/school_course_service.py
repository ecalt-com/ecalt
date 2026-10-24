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
from app.services.journey_access import invalidate_journey_access
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
    if course["status"] == "archived":
        raise HTTPException(status_code=409, detail={
            "error": "course_archived", "message": "Restore the course before regenerating it."})
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


# States from which a build may (re)start: a reviewed outline, or a prior build
# to redo. Not 'empty'/'outlining' (no outline yet) nor a mid-flight 'building'.
_BUILDABLE_STATUSES = ("outline_ready", "built", "build_failed")


def start_build(ctx: SchoolCtx, journey_id: str) -> dict:
    """Approve the reviewed outline and enqueue the build job (grounded step
    bodies + critic). Budget-checked; refuses a published or un-outlined course."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] == "archived":
        raise HTTPException(status_code=409, detail={
            "error": "course_archived", "message": "Restore the course before rebuilding it."})
    draft = _draft_version(journey_id)
    status = (draft["meta"] or {}).get("status") if draft else None
    steps = (draft["steps"] or []) if draft else []
    if not steps or status not in _BUILDABLE_STATUSES:
        raise HTTPException(status_code=409, detail={
            "error": "no_outline",
            "message": "Generate and review an outline before building the course."})
    allowed, reason = subscription_service.check_school_budget(ctx.school_id)
    if not allowed:
        raise HTTPException(status_code=402, detail=subscription_service.budget_error_detail(reason))

    _set_meta(journey_id, {**(draft["meta"] or {}), "status": "building"})
    job_id = school_jobs.enqueue(ctx.school_id, "build", {"journey_id": journey_id}, created_by=ctx.uid)
    with get_db() as conn:
        with conn.cursor() as cur:
            school_audit(cur, ctx.school_id, ctx.uid, "course.build_started", "course", journey_id)
    return {"job_id": job_id, "status": "building"}


# ── Draft editing (SC-403) ────────────────────────────────────────────────────
# Teachers refine the draft between generation steps. Every edit takes an
# optimistic lock on `course_versions.revision`: a client sends the revision it
# read, and a stale one gets 409 `draft_conflict` instead of silently clobbering
# a concurrent editor. Edits are refused while a job is actively writing the
# draft (outlining/building). Hand edits are tracked (`origin`/`edited_by_teacher`)
# so step regeneration (SC-405) can protect them.

_STEP_PATCH_FIELDS = ("title", "description", "type", "estimated_minutes",
                      "core_question", "learning_objective", "body_md")
_BUSY_STATUSES = ("outlining", "building")


def patch_draft_meta(ctx: SchoolCtx, journey_id: str, expected_revision, patch: dict) -> dict:
    """Edit the course's title / description / estimated hours on the draft."""
    def mutate(cur, meta, steps):
        if "title" in patch:
            title = (patch["title"] or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail={"error": "title_required", "message": "Give the course a title."})
            meta["title"] = title
            cur.execute("UPDATE journeys SET title = %s WHERE id = %s", (title, journey_id))
        if "description" in patch:
            meta["description"] = (patch["description"] or "").strip()
        if "estimated_hours" in patch:
            meta["estimated_hours"] = patch["estimated_hours"]
        return meta, steps
    return _edit_draft(ctx, journey_id, expected_revision, mutate, "course.meta_edited",
                       {"fields": sorted(patch.keys())})


def add_step(ctx: SchoolCtx, journey_id: str, expected_revision, step: dict, after_step_id=None) -> dict:
    """Insert a teacher-authored step (ungrounded — no source chunks) after a
    given step, or at the end."""
    def mutate(cur, meta, steps):
        new = _new_step(step)
        idx = len(steps)
        if after_step_id is not None:
            idx = _step_index(steps, after_step_id) + 1
        steps.insert(idx, new)
        return meta, steps
    return _edit_draft(ctx, journey_id, expected_revision, mutate, "course.step_added")


def patch_step(ctx: SchoolCtx, journey_id: str, step_id: str, expected_revision, patch: dict) -> dict:
    """Edit a step's fields. Marks it teacher-edited; a hand-edited body clears
    the AI critic flags (the teacher now owns the text)."""
    def mutate(cur, meta, steps):
        step = steps[_step_index(steps, step_id)]
        for field in _STEP_PATCH_FIELDS:
            if field not in patch:
                continue
            if field == "type" and patch["type"] not in _STEP_TYPES:
                raise HTTPException(status_code=422, detail={"error": "invalid_step_type", "message": "Unknown step type."})
            step[field] = patch[field]
        step["edited_by_teacher"] = True
        if "body_md" in patch:
            step["flags"] = []
            step["build_status"] = "built" if (patch["body_md"] or "").strip() else step.get("build_status", "empty")
        return meta, steps
    return _edit_draft(ctx, journey_id, expected_revision, mutate, "course.step_edited", {"step_id": step_id})


def delete_step(ctx: SchoolCtx, journey_id: str, step_id: str, expected_revision) -> dict:
    def mutate(cur, meta, steps):
        del steps[_step_index(steps, step_id)]
        return meta, steps
    return _edit_draft(ctx, journey_id, expected_revision, mutate, "course.step_deleted", {"step_id": step_id})


def reorder_steps(ctx: SchoolCtx, journey_id: str, expected_revision, order: list) -> dict:
    def mutate(cur, meta, steps):
        by_id = {s["id"]: s for s in steps}
        if sorted(order) != sorted(by_id.keys()):
            raise HTTPException(status_code=422, detail={
                "error": "invalid_order", "message": "Reorder must list every step exactly once."})
        return meta, [by_id[sid] for sid in order]
    return _edit_draft(ctx, journey_id, expected_revision, mutate, "course.steps_reordered")


_STEP_TYPES = ("concept", "practice", "challenge", "explore")


def _new_step(step: dict) -> dict:
    title = (step.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail={"error": "title_required", "message": "Give the step a title."})
    stype = step.get("type")
    if stype is not None and stype not in _STEP_TYPES:
        raise HTTPException(status_code=422, detail={"error": "invalid_step_type", "message": "Unknown step type."})
    body = (step.get("body_md") or "").strip() or None
    return {
        "id": "s" + uuid.uuid4().hex[:8],
        "title": title[:200],
        "description": (step.get("description") or "")[:1000],
        "type": stype if stype in _STEP_TYPES else "concept",
        "estimated_minutes": int(step.get("estimated_minutes") or 10),
        "core_question": (step.get("core_question") or "")[:500],
        "learning_objective": (step.get("learning_objective") or "")[:500],
        "chunk_ids": [], "citations": [], "key_facts": [], "quiz_anchors": [],
        "body_md": body, "flags": [],
        "origin": "teacher", "edited_by_teacher": True,
        "build_status": "built" if body else "empty",
    }


def _step_index(steps: list, step_id: str) -> int:
    for i, s in enumerate(steps):
        if s.get("id") == step_id:
            return i
    raise HTTPException(status_code=404, detail={"error": "step_not_found", "message": "Step not found."})


def _edit_draft(ctx: SchoolCtx, journey_id: str, expected_revision, mutate, audit_action: str,
                audit_meta: Optional[dict] = None) -> dict:
    """Apply `mutate(cur, meta, steps) -> (meta, steps)` to the draft under a row
    lock + revision check, bump the revision, and audit the change."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    _load_course(ctx.school_id, journey_id)   # 404s cross-school / unknown courses
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT revision, meta, steps FROM course_versions "
                "WHERE journey_id = %s AND state = 'draft' FOR UPDATE",
                (journey_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail={
                    "error": "no_draft", "message": "This course has no editable draft."})
            status = (row["meta"] or {}).get("status")
            if status in _BUSY_STATUSES:
                raise HTTPException(status_code=409, detail={
                    "error": "course_busy", "message": "The course is still generating. Wait for it to finish."})
            if expected_revision is not None and row["revision"] != expected_revision:
                raise HTTPException(status_code=409, detail={
                    "error": "draft_conflict",
                    "message": "Someone else changed this course. Reload and try again.",
                    "current_revision": row["revision"]})
            meta, steps = mutate(cur, row["meta"] or {}, list(row["steps"] or []))
            cur.execute(
                """UPDATE course_versions
                      SET meta = %s::jsonb, steps = %s::jsonb, revision = revision + 1, updated_at = now()
                    WHERE journey_id = %s AND state = 'draft'""",
                (json.dumps(meta), json.dumps(steps), journey_id))
            school_audit(cur, ctx.school_id, ctx.uid, audit_action, "course", journey_id, audit_meta)
    return get_course(ctx, journey_id)


# ── Regenerate one step (SC-405) ──────────────────────────────────────────────

def regenerate_step(ctx: SchoolCtx, journey_id: str, step_id: str, expected_revision=None,
                    instruction=None, overwrite_teacher_edits: bool = False) -> dict:
    """Re-generate a single step's body from its cited chunks, optionally with a
    teacher instruction. Refuses to clobber a teacher-edited step unless
    `overwrite_teacher_edits` is set. Runs as an async job."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] == "archived":
        raise HTTPException(status_code=409, detail={
            "error": "course_archived", "message": "Restore the course before regenerating it."})
    # Budget check first, with its own connection, so we never nest get_db under
    # the draft row lock below.
    allowed, reason = subscription_service.check_school_budget(ctx.school_id)
    if not allowed:
        raise HTTPException(status_code=402, detail=subscription_service.budget_error_detail(reason))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT revision, meta, steps FROM course_versions "
                        "WHERE journey_id = %s AND state = 'draft' FOR UPDATE", (journey_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail={"error": "no_draft", "message": "This course has no editable draft."})
            if (row["meta"] or {}).get("status") in _BUSY_STATUSES:
                raise HTTPException(status_code=409, detail={"error": "course_busy", "message": "The course is still generating. Wait for it to finish."})
            if expected_revision is not None and row["revision"] != expected_revision:
                raise HTTPException(status_code=409, detail={
                    "error": "draft_conflict", "message": "Someone else changed this course. Reload and try again.",
                    "current_revision": row["revision"]})
            step = next((s for s in (row["steps"] or []) if s.get("id") == step_id), None)
            if step is None:
                raise HTTPException(status_code=404, detail={"error": "step_not_found", "message": "Step not found."})
            if not step.get("chunk_ids"):
                raise HTTPException(status_code=409, detail={
                    "error": "step_not_grounded",
                    "message": "This step has no source material to regenerate from. Edit it by hand instead."})
            if step.get("edited_by_teacher") and not overwrite_teacher_edits:
                raise HTTPException(status_code=409, detail={
                    "error": "teacher_edits_protected",
                    "message": "This step has your edits. Regenerate anyway to replace them with a fresh AI draft."})
            cur.execute("UPDATE course_versions SET meta = %s::jsonb, updated_at = now() "
                        "WHERE journey_id = %s AND state = 'draft'",
                        (json.dumps({**(row["meta"] or {}), "status": "building"}), journey_id))
            school_audit(cur, ctx.school_id, ctx.uid, "course.step_regenerate_started", "course", journey_id,
                         {"step_id": step_id})
    job_id = school_jobs.enqueue(ctx.school_id, "regenerate_step",
                                 {"journey_id": journey_id, "step_id": step_id, "instruction": instruction},
                                 created_by=ctx.uid)
    return {"job_id": job_id, "status": "regenerating", "step_id": step_id}


# ── Publish + version history (SC-406 / SC-407) ───────────────────────────────
# Students only ever see the published version: `journeys.steps` + locked
# `step_content` are written in the publish transaction, nothing else writes
# them (invariant I5). Drafts live in `course_versions`; publishing promotes the
# draft to `published` and supersedes the previous one.

# Only these fields reach students — never body flags, citations or chunk ids.
_PUBLIC_STEP_FIELDS = ("id", "title", "description", "type", "estimated_minutes", "core_question")


def publish_course(ctx: SchoolCtx, journey_id: str, expected_revision=None, change_summary=None) -> dict:
    """Publish the built draft: write the student-facing journey + locked step
    content, promote the version, supersede the prior one — all in one txn."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] == "archived":
        raise HTTPException(status_code=409, detail={
            "error": "course_archived", "message": "Restore the course before publishing."})
    model = get_config("school_step_content")["model"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version, meta, steps, revision FROM course_versions "
                "WHERE journey_id = %s AND state = 'draft' FOR UPDATE", (journey_id,))
            draft = cur.fetchone()
            if not draft:
                raise HTTPException(status_code=409, detail={
                    "error": "no_draft", "message": "There's nothing to publish — the course has no draft."})
            meta = draft["meta"] or {}
            steps = draft["steps"] or []
            if meta.get("status") in _BUSY_STATUSES:
                raise HTTPException(status_code=409, detail={
                    "error": "course_busy", "message": "The course is still generating. Wait for it to finish."})
            if expected_revision is not None and draft["revision"] != expected_revision:
                raise HTTPException(status_code=409, detail={
                    "error": "draft_conflict",
                    "message": "Someone else changed this course. Reload and try again.",
                    "current_revision": draft["revision"]})
            if not steps:
                raise HTTPException(status_code=409, detail={
                    "error": "empty_course", "message": "Add at least one step before publishing."})
            incomplete = [s["id"] for s in steps if not (s.get("body_md") or "").strip()]
            if incomplete:
                raise HTTPException(status_code=409, detail={
                    "error": "steps_incomplete",
                    "message": "Every step needs content before you can publish. Build or write the remaining steps.",
                    "steps": incomplete[:20]})

            version = draft["version"]
            cur.execute("UPDATE course_versions SET state = 'superseded', updated_at = now() "
                        "WHERE journey_id = %s AND state = 'published'", (journey_id,))
            cur.execute(
                """UPDATE course_versions
                      SET state = 'published', revision = revision + 1, meta = %s::jsonb,
                          published_by = %s, published_at = now(), change_summary = %s, updated_at = now()
                    WHERE id = %s""",
                (json.dumps({**meta, "status": "published"}), ctx.uid, change_summary, draft["id"]))

            public_steps = [{k: s.get(k) for k in _PUBLIC_STEP_FIELDS} for s in steps]
            cur.execute(
                """UPDATE journeys
                      SET title = %s, description = %s, estimated_hours = %s, steps = %s::jsonb,
                          hero_image_url = COALESCE(%s, hero_image_url)
                    WHERE id = %s AND school_id = %s""",
                (meta.get("title") or course["title"], meta.get("description") or "",
                 float(meta.get("estimated_hours") or 0), json.dumps(public_steps),
                 meta.get("hero_image_url"), journey_id, ctx.school_id))

            # Locked published content; drop content for steps that no longer exist.
            step_ids = [s["id"] for s in steps]
            cur.execute("DELETE FROM step_content WHERE journey_id = %s AND NOT (step_id = ANY(%s))",
                        (journey_id, step_ids))
            for s in steps:
                cur.execute(
                    """INSERT INTO step_content
                           (journey_id, step_id, content, quiz_anchors, model, source, locked)
                       VALUES (%s, %s, %s, %s::jsonb, %s, 'school_published', true)
                       ON CONFLICT (journey_id, step_id) DO UPDATE SET
                           content = EXCLUDED.content, quiz_anchors = EXCLUDED.quiz_anchors,
                           model = EXCLUDED.model, source = 'school_published', locked = true,
                           generated_at = now()""",
                    (journey_id, s["id"], s.get("body_md") or "", json.dumps(s.get("quiz_anchors") or []), model))

            cur.execute("UPDATE school_courses SET status = 'published', published_version = %s, updated_at = now() "
                        "WHERE journey_id = %s AND school_id = %s", (version, journey_id, ctx.school_id))
            school_audit(cur, ctx.school_id, ctx.uid, "course.published", "course", journey_id,
                         {"version": version, "steps": len(steps)})
    invalidate_journey_access(journey_id=journey_id)
    return get_course(ctx, journey_id)


def list_versions(ctx: SchoolCtx, journey_id: str) -> list:
    journey_id = uuid_or_404(journey_id, "course_not_found")
    _load_course(ctx.school_id, journey_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT version, state, revision, change_summary, created_by, created_at,
                          published_by, published_at, base_version,
                          jsonb_array_length(COALESCE(steps, '[]'::jsonb)) AS step_count
                     FROM course_versions WHERE journey_id = %s ORDER BY version DESC""",
                (journey_id,))
            return [{
                "version": r["version"], "state": r["state"], "revision": r["revision"],
                "change_summary": r["change_summary"], "step_count": r["step_count"] or 0,
                "base_version": r["base_version"],
                "created_at": _iso(r["created_at"]), "published_at": _iso(r["published_at"]),
            } for r in cur.fetchall()]


def restore_version(ctx: SchoolCtx, journey_id: str, version: int) -> dict:
    """Copy an old version's steps + meta into a NEW draft (history is never
    rewritten). Refuses while an editable draft already exists."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] == "archived":
        raise HTTPException(status_code=409, detail={
            "error": "course_archived", "message": "Restore the course from the archive first."})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM course_versions WHERE journey_id = %s AND state = 'draft' FOR UPDATE", (journey_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "draft_exists", "message": "You already have a working draft. Edit or publish it first."})
            cur.execute("SELECT meta, steps FROM course_versions WHERE journey_id = %s AND version = %s",
                        (journey_id, version))
            src = cur.fetchone()
            if not src:
                raise HTTPException(status_code=404, detail={"error": "version_not_found", "message": "Version not found."})
            cur.execute("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM course_versions WHERE journey_id = %s", (journey_id,))
            new_version = cur.fetchone()["v"]
            meta = {**(src["meta"] or {}), "status": "built"}
            meta.pop("error", None)
            cur.execute(
                """INSERT INTO course_versions (journey_id, version, state, revision, meta, steps, base_version, created_by)
                   VALUES (%s, %s, 'draft', 0, %s::jsonb, %s::jsonb, %s, %s)""",
                (journey_id, new_version, json.dumps(meta), json.dumps(src["steps"] or []), version, ctx.uid))
            school_audit(cur, ctx.school_id, ctx.uid, "course.version_restored", "course", journey_id,
                         {"from_version": version, "new_version": new_version})
    return get_course(ctx, journey_id)


def duplicate_course(ctx: SchoolCtx, journey_id: str) -> dict:
    """A fresh draft course copying this course's latest steps + source links."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    src = _load_course(ctx.school_id, journey_id)
    new_jid = str(uuid.uuid4())
    title = ((src["title"] or "Course") + " (copy)")[:200]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT meta, steps FROM course_versions WHERE journey_id = %s ORDER BY version DESC LIMIT 1",
                        (journey_id,))
            v = cur.fetchone() or {"meta": {}, "steps": []}
            cur.execute(
                "INSERT INTO journeys (id, uid, school_id, question, title, description, estimated_hours, steps) "
                "VALUES (%s, NULL, %s, %s, %s, '', 0, '[]'::jsonb)",
                (new_jid, ctx.school_id, title, title))
            cur.execute(
                "INSERT INTO school_courses (journey_id, school_id, status, created_by) VALUES (%s, %s, 'draft', %s)",
                (new_jid, ctx.school_id, ctx.uid))
            meta = {**(v["meta"] or {}), "status": "built", "title": title}
            meta.pop("error", None)
            cur.execute(
                "INSERT INTO course_versions (journey_id, version, state, revision, meta, steps, created_by) "
                "VALUES (%s, 1, 'draft', 0, %s::jsonb, %s::jsonb, %s)",
                (new_jid, json.dumps(meta), json.dumps(v["steps"] or []), ctx.uid))
            cur.execute(
                "INSERT INTO course_sources (journey_id, document_id, school_id) "
                "SELECT %s, document_id, school_id FROM course_sources WHERE journey_id = %s",
                (new_jid, journey_id))
            school_audit(cur, ctx.school_id, ctx.uid, "course.duplicated", "course", new_jid,
                         {"from": journey_id})
    return get_course(ctx, new_jid)


async def generate_hero(ctx: SchoolCtx, journey_id: str) -> dict:
    """Generate an optional hero image for the course via `image_service`, billed
    to the school. Stored on the draft meta (publish copies it to the journey)
    and on the live journey when already published (SC-409)."""
    from types import SimpleNamespace
    from app.services import image_service
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if not image_service.images_enabled():
        raise HTTPException(status_code=503, detail={
            "error": "image_unavailable", "message": "Image generation isn't configured."})
    allowed, reason = subscription_service.check_school_budget(ctx.school_id)
    if not allowed:
        raise HTTPException(status_code=402, detail=subscription_service.budget_error_detail(reason))

    draft = _draft_version(journey_id)
    meta = (draft["meta"] if draft else {}) or {}
    j = SimpleNamespace(id=journey_id, title=meta.get("title") or course["title"],
                        description=meta.get("description") or "", tags=[], age_group="all")
    data, model, content_type = await image_service.generate_hero_image(j)
    url = await image_service.upload_journey_image(journey_id, data, content_type)
    subscription_service.record_school_image_usage(ctx.school_id, model, journey_id=journey_id)

    if draft:
        _set_meta(journey_id, {**meta, "hero_image_url": url})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE journeys SET hero_image_url = %s WHERE id = %s AND school_id = %s",
                        (url, journey_id, ctx.school_id))
            school_audit(cur, ctx.school_id, ctx.uid, "course.hero_generated", "course", journey_id)
    return {"hero_image_url": url}


def archive_course(ctx: SchoolCtx, journey_id: str) -> dict:
    """Hide a course from students (progress is kept). Reversible via restore."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    _load_course(ctx.school_id, journey_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE school_courses SET status = 'archived', archived_at = now(), updated_at = now() "
                        "WHERE journey_id = %s AND school_id = %s", (journey_id, ctx.school_id))
            school_audit(cur, ctx.school_id, ctx.uid, "course.archived", "course", journey_id)
    invalidate_journey_access(journey_id=journey_id)
    return {"journey_id": journey_id, "status": "archived"}


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
