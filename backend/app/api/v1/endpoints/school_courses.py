"""AI course builder endpoints (M4 SC-402/403): create a course from uploaded
documents, estimate the cost, and kick off / track the outline generation job.
All staff-only (students are blocked by the route allowlist). Build, editing,
publish and versions land in later increments.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.school_auth import SchoolCtx, school_member, uuid_or_404
from app.services import school_course_service as courses, school_jobs

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
