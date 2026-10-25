"""Update a published course from a new document (M6 SC-601..604).

A teacher whose source material changed (a new edition, or extra material)
re-uploads the document, then runs an **update**: the `propose_update` job aligns
the new document's chunks to the course's published steps
(`school_course_align`), and for every step whose source changed — and for every
new section no step covers — generates a grounded replacement/new body (reusing
the course builder's step generation + faithfulness critic) and records a
reviewable **proposal** in `course_change_proposals`. The teacher accepts or
rejects each proposal; accepting then applying them produces a **new draft
version** based on the published one, with step ids preserved so student
progress survives. The teacher reviews and publishes that draft through the
normal publish path.

Modes:
  * ``revise``     — reclassify every step (modify / remove) and add new sections.
  * ``supplement`` — only add new sections; existing steps are left untouched.
  * ``replace``    — outline and build a fresh course from the new document
    alone, keeping a published step's id wherever a new step's title matches it
    (so that step's progress survives). There is nothing to review item by item,
    so the job lands a complete new draft directly; the teacher reviews and
    publishes it like any other draft.

Teacher-authored steps are never auto-modified or auto-removed: a change to one
is flagged ``suggestion_only`` so the teacher decides explicitly.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import uuid
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_db
from app.core.school_auth import SchoolCtx, uuid_or_404
from app.services import provider_service, school_jobs, subscription_service
from app.services import school_course_align as align
from app.services import school_course_builder as builder
from app.services import school_course_service as courses
from app.services.school_service import school_audit

logger = logging.getLogger(__name__)

_MODES = ("revise", "supplement", "replace")

# Fields of a generated/replacement step that we persist in a proposal and later
# copy into the new draft. Mirrors what the builder produces.
_STEP_FIELDS = ("id", "title", "description", "type", "estimated_minutes", "core_question",
                "learning_objective", "chunk_ids", "citations", "key_facts", "quiz_anchors",
                "body_md", "flags", "origin")


# ── Kick off an update ────────────────────────────────────────────────────────

def start_update(ctx: SchoolCtx, journey_id: str, document_id: str, mode: str = "revise") -> dict:
    """Validate, attach the new document, clear any prior proposals, and enqueue
    the propose-update job."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    document_id = uuid_or_404(document_id, "document_not_found")
    if mode not in _MODES:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_mode",
            "message": "Update mode must be 'revise', 'supplement' or 'replace'."})
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] != "published":
        raise HTTPException(status_code=409, detail={
            "error": "course_not_published",
            "message": "Publish the course before updating it from a new document."})

    allowed, reason = subscription_service.check_school_budget(ctx.school_id)
    if not allowed:
        raise HTTPException(status_code=402, detail=subscription_service.budget_error_detail(reason))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM course_versions WHERE journey_id = %s AND state = 'draft'", (journey_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "draft_exists",
                    "message": "Finish or discard the current draft before updating from a document."})
            cur.execute("SELECT status FROM source_documents WHERE id = %s AND school_id = %s",
                        (document_id, ctx.school_id))
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail={"error": "document_not_found", "message": "Document not found."})
            if doc["status"] != "ready":
                raise HTTPException(status_code=409, detail={
                    "error": "document_not_ready",
                    "message": "That document is still being read. Wait until it's ready, then try again."})
            # Make the new document part of the course's sources so its chunks are
            # available to the builder when a proposal is applied + published.
            cur.execute(
                "INSERT INTO course_sources (journey_id, document_id, school_id) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING", (journey_id, document_id, ctx.school_id))
            # Fresh run: drop any proposals left from a previous update attempt.
            cur.execute("DELETE FROM course_change_proposals WHERE journey_id = %s", (journey_id,))
            school_audit(cur, ctx.school_id, ctx.uid, "course.update_started", "course", journey_id,
                         {"document_id": document_id, "mode": mode})

    job_id = school_jobs.enqueue(ctx.school_id, "propose_update",
                                 {"journey_id": journey_id, "document_id": document_id, "mode": mode},
                                 created_by=ctx.uid)
    return {"job_id": job_id, "status": "proposing", "mode": mode}


# ── Propose-update job ────────────────────────────────────────────────────────

def propose_update_handler(job: dict) -> dict:
    journey_id = job["payload"]["journey_id"]
    document_id = job["payload"]["document_id"]
    mode = job["payload"].get("mode", "revise")
    school_id = job["school_id"]
    job_id = str(job["id"])

    published = _published_version(journey_id)
    if not published or not (published["steps"] or []):
        return {"status": "update_failed", "reason": "not_published"}
    allowed, reason = subscription_service.check_school_budget(school_id)
    if not allowed:
        return {"status": "update_failed", "reason": reason}

    steps = published["steps"]
    new_chunks = _document_chunks(document_id)
    if not new_chunks:
        return {"status": "update_failed", "reason": "no_source_text"}

    if mode == "replace":
        return _replace_from_document(job, published, new_chunks)

    old_text, old_heads = _old_sources(steps)
    step_views = [align.StepView(
        id=s["id"], title=s.get("title") or "", origin=s.get("origin") or "ai",
        source_text=old_text.get(s["id"], ""), top_headings=old_heads.get(s["id"], set()),
        body_md=s.get("body_md")) for s in steps]
    chunk_views = [align.ChunkView(cite_id=c["cite_id"], chunk_id=c["chunk_id"],
                                   heading_path=c["heading_path"], text=c["text"]) for c in new_chunks]
    plan = align.plan_update(step_views, chunk_views, mode=mode)

    chunks_by_id = {c["chunk_id"]: c for c in new_chunks}
    steps_by_id = {s["id"]: s for s in steps}
    cfg_body = provider_service.get_config("school_step_content")
    cfg_critic = provider_service.get_config("school_faithfulness_critic")

    changes = plan["changes"]
    rows: list = []
    built = {"modify": 0, "add": 0, "remove": 0, "skipped": 0}
    total = len(changes)

    # Every modify / add needs a freshly generated, grounded body. They are all
    # generated in ONE event loop (see `_build_bodies`).
    synths: dict = {}
    for i, ch in enumerate(changes):
        if ch.op == "remove":
            continue
        if ch.op == "modify":
            base = steps_by_id.get(ch.step_id, {})
            synths[i] = {**{k: base.get(k) for k in ("title", "description", "type", "estimated_minutes",
                                                     "core_question", "learning_objective")},
                         "id": ch.step_id, "chunk_ids": ch.matched_chunk_ids}
        else:  # add
            synths[i] = {"id": "s" + uuid.uuid4().hex[:8],
                         # the heading comes from the uploaded document: untrusted
                         "title": builder._sanitize_md(ch.title)[:200] or "New section", "description": "",
                         "type": "concept", "estimated_minutes": 10, "core_question": "",
                         "learning_objective": "", "chunk_ids": ch.matched_chunk_ids}
    bodies = _build_bodies(synths, chunks_by_id, school_id, journey_id, cfg_body, cfg_critic,
                           job_id, total)

    for i, ch in enumerate(changes):
        school_jobs.raise_if_cancelled(job_id)

        if ch.op == "remove":
            rows.append(("remove", ch.step_id, {"suggestion_only": ch.suggestion_only}, ch.reason))
            built["remove"] += 1
            continue

        new_step = bodies.get(i)
        if not new_step or not (new_step.get("body_md") or "").strip():
            built["skipped"] += 1
            continue
        new_step["origin"] = "ai"

        if ch.op == "modify":
            old_body = (steps_by_id.get(ch.step_id, {}) or {}).get("body_md") or ""
            payload = {"step": _step_payload(new_step), "old_body": old_body,
                       "new_body": new_step["body_md"], "diff": _diff_summary(old_body, new_step["body_md"]),
                       "old_title": (steps_by_id.get(ch.step_id, {}) or {}).get("title"),
                       "suggestion_only": ch.suggestion_only}
            rows.append(("modify", ch.step_id, payload, ch.reason))
            built["modify"] += 1
        else:
            payload = {"after_step_id": ch.after_step_id, "step": _step_payload(new_step)}
            rows.append(("add", new_step["id"], payload, ch.reason))
            built["add"] += 1

    _write_proposals(journey_id, job_id, published["version"], rows)
    school_jobs.update_progress(job_id, {"steps_done": total, "steps_total": total})
    logger.info("proposed update for %s: %s", journey_id, built)
    return {"status": "proposed", "proposed": len(rows), **built,
            "unchanged": plan["summary"]["unchanged"]}


def _build_bodies(synths: dict, chunks_by_id: dict, school_id: str, journey_id: str,
                  cfg_body: dict, cfg_critic: dict, job_id: str, total: int) -> dict:
    """Generate the grounded step bodies for ``{key: step}``, bounded-concurrently.

    All of them share **one** event loop: the provider's async clients are
    module-level singletons bound to the loop that first used them, so one
    `asyncio.run` per step would reuse a closed loop and every later body would
    fail to generate. A single bad body yields None for that key and never sinks
    the run.
    """
    if not synths:
        return {}
    done = {"n": 0}

    async def _run() -> dict:
        sem = asyncio.Semaphore(builder._BUILD_CONCURRENCY)

        async def _one(key, step):
            async with sem:
                school_jobs.raise_if_cancelled(job_id)
                try:
                    built = await builder._build_step(step, chunks_by_id, school_id, journey_id,
                                                      cfg_body, cfg_critic)
                except school_jobs.JobCancelled:
                    raise
                except Exception:
                    logger.warning("update body generation failed for a step in %s",
                                   journey_id, exc_info=True)
                    built = None
                done["n"] += 1   # single-threaded event loop → safe between awaits
                school_jobs.update_progress(job_id, {"steps_done": done["n"], "steps_total": total})
                return key, built

        return dict(await asyncio.gather(*[_one(k, v) for k, v in synths.items()]))

    return asyncio.run(_run())


# ── Replace mode (SC-605) ─────────────────────────────────────────────────────

def _replace_from_document(job: dict, published: dict, new_chunks: list) -> dict:
    """Outline + build a fresh course from the new document alone and land it as
    a new draft, keeping published step ids wherever titles match.

    The whole pipeline runs in **one** event loop: the provider's async clients
    are module-level singletons bound to the loop that first used them, so a
    second `asyncio.run` in the same job would reuse a closed loop and every
    later step would fail to generate.
    """
    school_id, job_id = job["school_id"], str(job["id"])
    journey_id = job["payload"]["journey_id"]
    old_steps = published["steps"] or []
    cfg_outline = provider_service.get_config("school_course_outline")
    cfg_body = provider_service.get_config("school_step_content")
    cfg_critic = provider_service.get_config("school_faithfulness_critic")
    chunks_by_id = {c["chunk_id"]: c for c in new_chunks}
    inputs = (published["meta"] or {}).get("inputs") or {}
    state: dict = {"error": None, "steps": None}

    async def _outline() -> Optional[dict]:
        user, last_err = builder._outline_user(inputs, new_chunks), None
        for _ in range(2):
            school_jobs.raise_if_cancelled(job_id)
            try:
                text, in_tok, out_tok, _ = await provider_service.complete_text(
                    "school_course_outline", cfg_outline["style_prompt"], user, max_tokens=2000)
                subscription_service.record_school_usage(school_id, in_tok, out_tok,
                                                         cfg_outline["model"], journey_id=journey_id)
                data = builder._parse_outline(text, len(new_chunks))
                builder._check_coverage(data, new_chunks)
                return data
            except school_jobs.JobCancelled:
                raise
            except Exception as exc:
                last_err = str(exc)[:300]
                logger.warning("replace outline rejected for %s: %s", journey_id, last_err)
                user += (f"\n\nYour previous answer was rejected: {last_err}. Return valid JSON that "
                         "follows the schema exactly and cites only real chunk ids.")
        state["error"] = last_err
        return None

    async def _run() -> Optional[list]:
        data = await _outline()
        if not data:
            return None
        steps = _reuse_step_ids(builder._materialize_steps(data, new_chunks), old_steps)
        state["steps"] = len(steps)
        done = {"n": 0}
        sem = asyncio.Semaphore(builder._BUILD_CONCURRENCY)

        async def _one(step: dict) -> dict:
            async with sem:
                school_jobs.raise_if_cancelled(job_id)
                try:
                    built = await builder._build_step(step, chunks_by_id, school_id, journey_id,
                                                      cfg_body, cfg_critic)
                except school_jobs.JobCancelled:
                    raise
                except Exception:
                    logger.warning("replace body generation failed for a step in %s",
                                   journey_id, exc_info=True)
                    built = builder._failed_step(step, "the step body could not be generated")
                done["n"] += 1   # single-threaded event loop → safe between awaits
                school_jobs.update_progress(job_id, {"steps_done": done["n"], "steps_total": len(steps)})
                return built

        return list(await asyncio.gather(*[_one(s) for s in steps]))

    built = asyncio.run(_run())
    if built is None:
        return {"status": "update_failed", "reason": "outline_invalid", "error": state["error"]}

    old_ids = {s["id"] for s in old_steps}
    kept = sum(1 for s in built if s["id"] in old_ids)
    _write_replacement_draft(journey_id, school_id, published, built, kept, job.get("created_by"))
    n_failed = sum(1 for s in built if s.get("build_status") == "failed")
    logger.info("replaced %s from a new document: %s steps, %s ids kept, %s failed",
                journey_id, len(built), kept, n_failed)
    return {"status": "replaced", "steps": len(built), "kept_step_ids": kept, "failed": n_failed}


def _reuse_step_ids(new_steps: list, old_steps: list) -> list:
    """Give each freshly outlined step the id of the published step with the same
    title, so progress on that step survives the replace. An unmatched step gets
    a fresh id that collides with no published one — a removed step's id is never
    handed to different material."""
    old_by_title: dict = {}
    for o in old_steps:
        old_by_title.setdefault(builder._norm(o.get("title")), o["id"])
    reserved = {o["id"] for o in old_steps}
    out, taken = [], set()
    for step in new_steps:
        match = old_by_title.get(builder._norm(step.get("title")))
        out.append({**step, "id": match if match and match not in taken else None})
        if out[-1]["id"]:
            taken.add(out[-1]["id"])
    for step in out:
        if step["id"]:
            continue
        sid = "s" + uuid.uuid4().hex[:8]
        while sid in reserved:
            sid = "s" + uuid.uuid4().hex[:8]
        step["id"] = sid
        reserved.add(sid)
    return out


def _write_replacement_draft(journey_id: str, school_id: str, published: dict, steps: list,
                             kept: int, created_by) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM course_versions WHERE journey_id = %s AND state = 'draft' FOR UPDATE",
                        (journey_id,))
            if cur.fetchone():
                raise RuntimeError("a draft appeared while the replacement was building")
            cur.execute("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM course_versions WHERE journey_id = %s",
                        (journey_id,))
            new_version = cur.fetchone()["v"]
            meta = {**(published["meta"] or {}), "status": "built",
                    "updated_from_version": published["version"], "rebuilt_from_document": True}
            meta.pop("error", None)
            summary = f"Rebuilt from a new document ({len(steps)} steps, {kept} kept from v{published['version']})"
            cur.execute(
                """INSERT INTO course_versions
                       (journey_id, version, state, revision, meta, steps, base_version, change_summary, created_by)
                   VALUES (%s, %s, 'draft', 0, %s::jsonb, %s::jsonb, %s, %s, %s)""",
                (journey_id, new_version, json.dumps(meta), json.dumps(steps),
                 published["version"], summary, created_by))
            school_audit(cur, school_id, created_by, "course.update_applied", "course", journey_id,
                         {"from_version": published["version"], "new_version": new_version,
                          "mode": "replace", "steps": len(steps), "kept_step_ids": kept})


# ── Review + apply ────────────────────────────────────────────────────────────

def list_proposals(ctx: SchoolCtx, journey_id: str) -> dict:
    journey_id = uuid_or_404(journey_id, "course_not_found")
    _load_course(ctx.school_id, journey_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, op, step_id, payload, reason, status, created_at
                     FROM course_change_proposals
                    WHERE journey_id = %s AND status IN ('pending', 'accepted')
                    ORDER BY created_at, id""",
                (journey_id,))
            proposals = [_proposal_view(r) for r in cur.fetchall()]
    accepted = sum(1 for p in proposals if p["status"] == "accepted")
    return {"proposals": proposals, "pending": len(proposals) - accepted, "accepted": accepted}


def decide_proposal(ctx: SchoolCtx, journey_id: str, proposal_id: str, decision: str) -> dict:
    journey_id = uuid_or_404(journey_id, "course_not_found")
    proposal_id = uuid_or_404(proposal_id, "proposal_not_found")
    if decision not in ("accept", "reject"):
        raise HTTPException(status_code=422, detail={
            "error": "invalid_decision", "message": "Decision must be 'accept' or 'reject'."})
    _load_course(ctx.school_id, journey_id)
    status = "accepted" if decision == "accept" else "rejected"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE course_change_proposals
                      SET status = %s, decided_by = %s, decided_at = now()
                    WHERE id = %s AND journey_id = %s AND status IN ('pending', 'accepted', 'rejected')
                    RETURNING id""",
                (status, ctx.uid, proposal_id, journey_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail={"error": "proposal_not_found", "message": "Proposal not found."})
            school_audit(cur, ctx.school_id, ctx.uid, "course.proposal_decided", "course", journey_id,
                         {"proposal_id": proposal_id, "decision": decision})
    return {"id": proposal_id, "status": status}


def apply_update(ctx: SchoolCtx, journey_id: str) -> dict:
    """Turn the accepted proposals into a NEW draft version based on the
    published one — step ids preserved so student progress survives. The teacher
    then reviews and publishes the draft."""
    journey_id = uuid_or_404(journey_id, "course_not_found")
    course = _load_course(ctx.school_id, journey_id)
    if course["status"] != "published":
        raise HTTPException(status_code=409, detail={
            "error": "course_not_published", "message": "The course must be published to apply an update."})
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM course_versions WHERE journey_id = %s AND state = 'draft' FOR UPDATE", (journey_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail={
                    "error": "draft_exists", "message": "You already have a working draft. Edit or publish it first."})
            cur.execute(
                "SELECT version, meta, steps FROM course_versions WHERE journey_id = %s AND state = 'published'",
                (journey_id,))
            pub = cur.fetchone()
            if not pub:
                raise HTTPException(status_code=409, detail={"error": "not_published", "message": "No published version to update."})
            cur.execute(
                """SELECT id, op, step_id, payload FROM course_change_proposals
                    WHERE journey_id = %s AND status = 'accepted' ORDER BY created_at, id""",
                (journey_id,))
            accepted = cur.fetchall()
            if not accepted:
                raise HTTPException(status_code=409, detail={
                    "error": "nothing_to_apply", "message": "Accept at least one proposed change first."})

            steps = list(pub["steps"] or [])
            n_mod, n_add, n_rem = _apply_changes(steps, accepted)

            cur.execute("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM course_versions WHERE journey_id = %s", (journey_id,))
            new_version = cur.fetchone()["v"]
            meta = {**(pub["meta"] or {}), "status": "built", "updated_from_version": pub["version"]}
            meta.pop("error", None)
            summary = f"Updated from a new document (+{n_add} / ~{n_mod} / -{n_rem})"
            cur.execute(
                """INSERT INTO course_versions
                       (journey_id, version, state, revision, meta, steps, base_version, change_summary, created_by)
                   VALUES (%s, %s, 'draft', 0, %s::jsonb, %s::jsonb, %s, %s, %s)""",
                (journey_id, new_version, json.dumps(meta), json.dumps(steps), pub["version"], summary, ctx.uid))
            # The proposals are now represented in the draft; clear them.
            cur.execute("DELETE FROM course_change_proposals WHERE journey_id = %s", (journey_id,))
            school_audit(cur, ctx.school_id, ctx.uid, "course.update_applied", "course", journey_id,
                         {"from_version": pub["version"], "new_version": new_version,
                          "modified": n_mod, "added": n_add, "removed": n_rem})
    return courses.get_course(ctx, journey_id)


def _apply_changes(steps: list, accepted: list) -> tuple:
    """Mutate ``steps`` in place from accepted proposal rows. Returns
    ``(modified, added, removed)`` counts. Added/modified steps are marked
    ``updated`` for the student 'updated since you finished' badge (SC-604)."""
    by_id = {s["id"]: i for i, s in enumerate(steps)}
    n_mod = n_add = n_rem = 0
    # Apply modifies + removes first (they reference existing ids), then adds.
    for p in accepted:
        payload = p["payload"] or {}
        if p["op"] == "modify" and p["step_id"] in by_id:
            idx = by_id[p["step_id"]]
            new_step = {**steps[idx], **(payload.get("step") or {})}
            new_step["id"] = steps[idx]["id"]      # id is never changed by a modify
            new_step["updated"] = True
            steps[idx] = new_step
            n_mod += 1
        elif p["op"] == "remove" and p["step_id"] in by_id:
            steps[by_id[p["step_id"]]] = None
            n_rem += 1
    steps[:] = [s for s in steps if s is not None]
    # Re-index after removals, then insert adds.
    for p in accepted:
        if p["op"] != "add":
            continue
        step = dict((p["payload"] or {}).get("step") or {})
        if not step:
            continue
        step["updated"] = True
        existing = {s["id"] for s in steps}
        if step.get("id") in existing or not step.get("id"):
            step["id"] = "s" + uuid.uuid4().hex[:8]
        after = (p["payload"] or {}).get("after_step_id")
        idx = len(steps)
        for i, s in enumerate(steps):
            if s["id"] == after:
                idx = i + 1
                break
        steps.insert(idx, step)
        n_add += 1
    return n_mod, n_add, n_rem


# ── Shaping + helpers ─────────────────────────────────────────────────────────

def _proposal_view(r: dict) -> dict:
    payload = r["payload"] or {}
    step = payload.get("step") or {}
    return {
        "id": str(r["id"]), "op": r["op"], "step_id": r["step_id"], "status": r["status"],
        "reason": r["reason"], "suggestion_only": bool(payload.get("suggestion_only")),
        "title": step.get("title") or payload.get("old_title"),
        "old_title": payload.get("old_title"),
        "old_body": payload.get("old_body"), "new_body": payload.get("new_body") or step.get("body_md"),
        "diff": payload.get("diff"), "after_step_id": payload.get("after_step_id"),
    }


def _step_payload(step: dict) -> dict:
    return {k: step.get(k) for k in _STEP_FIELDS}


def _diff_summary(old: str, new: str) -> dict:
    sm = difflib.SequenceMatcher(a=(old or "").splitlines(), b=(new or "").splitlines())
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return {"added": added, "removed": removed}


def _old_sources(steps: list) -> tuple:
    """For each published step, the text + top headings of the chunks it was
    built from (from `document_chunks`), so the planner can compare old vs new."""
    wanted: set = set()
    for s in steps:
        for cid in (s.get("citations") or s.get("chunk_ids") or []):
            wanted.add(cid)
    chunk_map: dict = {}
    if wanted:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id::text AS id, heading_path, text FROM document_chunks WHERE id = ANY(%s::uuid[])",
                            (list(wanted),))
                chunk_map = {r["id"]: {"text": r["text"], "heading_path": r["heading_path"] or []}
                             for r in cur.fetchall()}
    text_by_step: dict = {}
    heads_by_step: dict = {}
    for s in steps:
        cids = s.get("citations") or s.get("chunk_ids") or []
        texts = [chunk_map[c]["text"] for c in cids if c in chunk_map]
        heads = {align._top_heading(chunk_map[c]["heading_path"]) for c in cids if c in chunk_map}
        text_by_step[s["id"]] = "\n".join(texts)
        heads_by_step[s["id"]] = {h for h in heads if h}
    return text_by_step, heads_by_step


def _document_chunks(document_id: str) -> list:
    """The new document's chunks, ordered, each with a 0-based ``cite_id`` for
    grounding (same shape the builder expects)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT dc.id, dc.ordinal, dc.heading_path, dc.page_start, dc.page_end,
                          dc.text, dc.char_count, sd.filename
                     FROM document_chunks dc JOIN source_documents sd ON sd.id = dc.document_id
                    WHERE dc.document_id = %s AND sd.status <> 'deleted'
                    ORDER BY dc.ordinal""",
                (document_id,))
            rows = cur.fetchall()
    return [{
        "cite_id": i, "chunk_id": str(r["id"]), "document_id": document_id,
        "heading_path": r["heading_path"] or [], "page_start": r["page_start"], "page_end": r["page_end"],
        "text": r["text"], "char_count": r["char_count"], "filename": r["filename"],
    } for i, r in enumerate(rows)]


def _write_proposals(journey_id: str, job_id: str, version: int, rows: list) -> None:
    if not rows:
        return
    with get_db() as conn:
        with conn.cursor() as cur:
            for op, step_id, payload, reason in rows:
                cur.execute(
                    """INSERT INTO course_change_proposals
                           (journey_id, job_id, version, op, step_id, payload, reason, status)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')""",
                    (journey_id, job_id, version, op, step_id, json.dumps(payload), reason))


def _published_version(journey_id: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version, meta, steps FROM course_versions "
                        "WHERE journey_id = %s AND state = 'published'", (journey_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def _load_course(school_id: str, journey_id: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT journey_id, status FROM school_courses WHERE journey_id = %s AND school_id = %s",
                        (journey_id, school_id))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "course_not_found", "message": "Course not found."})
    return dict(row)


school_jobs.register_handler("propose_update", propose_update_handler)
