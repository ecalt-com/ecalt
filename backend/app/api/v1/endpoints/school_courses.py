"""AI course builder endpoints (M4 SC-402/404): create a course from uploaded
documents, estimate the cost, kick off / track the outline generation job, and
approve the reviewed outline into a build job (grounded step bodies + critic).
All staff-only (students are blocked by the route allowlist). Editing, publish
and versions land in later increments.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.school_auth import SchoolCtx, school_member, uuid_or_404
from app.services import school_course_service as courses, school_jobs
from app.services import school_course_update_service as updates

router = APIRouter()


class CreateCourseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    document_ids: list[str] = Field(..., min_length=1)


class OutlineRequest(BaseModel):
    grade: Optional[int] = Field(None, ge=0, le=12)
    subject: Optional[str] = Field(None, max_length=120)
    goal: Optional[str] = Field(None, max_length=600)
    target_steps: Optional[int] = Field(None, ge=1, le=30)
    session_minutes: Optional[int] = Field(None, ge=5, le=240)
    language: Optional[str] = Field(None, max_length=40)
    follow_document_order: bool = True


class MetaPatchRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    estimated_hours: Optional[float] = Field(None, ge=0, le=1000)


class StepFields(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    type: Optional[str] = Field(None, max_length=20)
    estimated_minutes: Optional[int] = Field(None, ge=1, le=600)
    core_question: Optional[str] = Field(None, max_length=500)
    learning_objective: Optional[str] = Field(None, max_length=500)
    body_md: Optional[str] = Field(None, max_length=50000)


class StepAddRequest(StepFields):
    expected_revision: Optional[int] = Field(None, ge=0)
    title: str = Field(..., min_length=1, max_length=200)
    after_step_id: Optional[str] = Field(None, max_length=64)


class StepPatchRequest(StepFields):
    expected_revision: Optional[int] = Field(None, ge=0)


class ReorderRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)
    order: list[str] = Field(..., min_length=1, max_length=200)


class RegenerateRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)
    instruction: Optional[str] = Field(None, max_length=500)
    overwrite_teacher_edits: bool = False


class PublishRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)
    change_summary: Optional[str] = Field(None, max_length=500)


class UpdateRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=64)
    mode: str = Field("revise", pattern="^(revise|supplement|replace)$")


class DecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(accept|reject)$")


_STEP_EDIT_KEYS = ("title", "description", "type", "estimated_minutes",
                   "core_question", "learning_objective", "body_md")


@router.get("/{school_id}/courses", summary="List the school's courses")
def list_courses(ctx: SchoolCtx = Depends(school_member())):
    return {"courses": courses.list_courses(ctx)}


@router.post("/{school_id}/courses", status_code=201, summary="Create a draft course from uploaded documents")
def create_course(body: CreateCourseRequest, ctx: SchoolCtx = Depends(school_member())):
    return courses.create_course(ctx, body.title, body.document_ids)


@router.get("/{school_id}/courses/{journey_id}", summary="A course with its draft outline/steps")
def get_course(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return courses.get_course(ctx, journey_id)


@router.post("/{school_id}/courses/{journey_id}/estimate", summary="Estimate the generation cost before spending budget")
def estimate(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return courses.estimate(ctx, journey_id)


@router.post("/{school_id}/courses/{journey_id}/outline", summary="Generate the course outline (async job)")
def start_outline(journey_id: str, body: OutlineRequest, ctx: SchoolCtx = Depends(school_member())):
    return courses.start_outline(ctx, journey_id, body.model_dump(exclude_none=True))


@router.post("/{school_id}/courses/{journey_id}/build", summary="Build step content from the reviewed outline (async job)")
def start_build(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return courses.start_build(ctx, journey_id)


# ── Draft editing (SC-403) — optimistic lock via `expected_revision` ──────────

@router.patch("/{school_id}/courses/{journey_id}/draft", summary="Edit the course's title / description / hours")
def patch_draft_meta(journey_id: str, body: MetaPatchRequest, ctx: SchoolCtx = Depends(school_member())):
    patch = body.model_dump(exclude_unset=True)
    patch.pop("expected_revision", None)
    return courses.patch_draft_meta(ctx, journey_id, body.expected_revision, patch)


@router.post("/{school_id}/courses/{journey_id}/draft/steps", summary="Add a teacher-authored step")
def add_step(journey_id: str, body: StepAddRequest, ctx: SchoolCtx = Depends(school_member())):
    data = body.model_dump(exclude_unset=True)
    data.pop("expected_revision", None)
    after = data.pop("after_step_id", None)
    return courses.add_step(ctx, journey_id, body.expected_revision, data, after_step_id=after)


@router.post("/{school_id}/courses/{journey_id}/draft/steps/reorder", summary="Reorder the draft's steps")
def reorder_steps(journey_id: str, body: ReorderRequest, ctx: SchoolCtx = Depends(school_member())):
    return courses.reorder_steps(ctx, journey_id, body.expected_revision, body.order)


@router.patch("/{school_id}/courses/{journey_id}/draft/steps/{step_id}", summary="Edit a step")
def patch_step(journey_id: str, step_id: str, body: StepPatchRequest, ctx: SchoolCtx = Depends(school_member())):
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _STEP_EDIT_KEYS}
    return courses.patch_step(ctx, journey_id, step_id, body.expected_revision, patch)


@router.delete("/{school_id}/courses/{journey_id}/draft/steps/{step_id}", summary="Delete a step")
def delete_step(journey_id: str, step_id: str, revision: Optional[int] = None,
                ctx: SchoolCtx = Depends(school_member())):
    return courses.delete_step(ctx, journey_id, step_id, revision)


@router.post("/{school_id}/courses/{journey_id}/draft/steps/{step_id}/regenerate",
             summary="Regenerate one step's content (async job)")
def regenerate_step(journey_id: str, step_id: str, body: RegenerateRequest,
                    ctx: SchoolCtx = Depends(school_member())):
    return courses.regenerate_step(ctx, journey_id, step_id, body.expected_revision,
                                   body.instruction, body.overwrite_teacher_edits)


# ── Publish + version history (SC-406 / SC-407) ───────────────────────────────

@router.post("/{school_id}/courses/{journey_id}/publish", summary="Publish the built draft to students")
def publish_course(journey_id: str, body: PublishRequest, ctx: SchoolCtx = Depends(school_member())):
    return courses.publish_course(ctx, journey_id, body.expected_revision, body.change_summary)


@router.get("/{school_id}/courses/{journey_id}/versions", summary="Version history")
def list_versions(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return {"versions": courses.list_versions(ctx, journey_id)}


@router.post("/{school_id}/courses/{journey_id}/versions/{version}/restore", summary="Restore a version as a new draft")
def restore_version(journey_id: str, version: int, ctx: SchoolCtx = Depends(school_member())):
    return courses.restore_version(ctx, journey_id, version)


@router.post("/{school_id}/courses/{journey_id}/duplicate", summary="Duplicate the course into a new draft")
def duplicate_course(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return courses.duplicate_course(ctx, journey_id)


# ── Update from a new document (M6 SC-601..604) ───────────────────────────────

@router.post("/{school_id}/courses/{journey_id}/update",
             summary="Propose an update from a new document (async job)")
def start_update(journey_id: str, body: UpdateRequest, ctx: SchoolCtx = Depends(school_member())):
    return updates.start_update(ctx, journey_id, body.document_id, body.mode)


@router.get("/{school_id}/courses/{journey_id}/proposals", summary="List proposed changes to review")
def list_proposals(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return updates.list_proposals(ctx, journey_id)


@router.post("/{school_id}/courses/{journey_id}/proposals/apply",
             summary="Apply the accepted proposals into a new draft")
def apply_update(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return updates.apply_update(ctx, journey_id)


@router.post("/{school_id}/courses/{journey_id}/proposals/{proposal_id}/decide",
             summary="Accept or reject one proposed change")
def decide_proposal(journey_id: str, proposal_id: str, body: DecisionRequest,
                    ctx: SchoolCtx = Depends(school_member())):
    return updates.decide_proposal(ctx, journey_id, proposal_id, body.decision)


@router.post("/{school_id}/courses/{journey_id}/archive", summary="Archive the course (hide from students)")
def archive_course(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return courses.archive_course(ctx, journey_id)


@router.post("/{school_id}/courses/{journey_id}/hero-image", summary="Generate a hero image (school-billed)")
async def generate_hero(journey_id: str, ctx: SchoolCtx = Depends(school_member())):
    return await courses.generate_hero(ctx, journey_id)


@router.get("/{school_id}/jobs/{job_id}", summary="Background job status + progress")
def get_job(job_id: str, ctx: SchoolCtx = Depends(school_member())):
    job = school_jobs.get_job(ctx.school_id, uuid_or_404(job_id, "job_not_found"))
    if not job:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "message": "Job not found."})
    return job


@router.post("/{school_id}/jobs/{job_id}/cancel", summary="Request cancellation of a running/queued job")
def cancel_job(job_id: str, ctx: SchoolCtx = Depends(school_member())):
    status = school_jobs.request_cancel(ctx.school_id, uuid_or_404(job_id, "job_not_found"))
    if status is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "message": "Job not found or already finished."})
    return {"status": status}
