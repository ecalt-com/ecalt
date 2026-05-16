from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_required_user
from app.core.supabase import get_supabase

router = APIRouter()


class ProgressResponse(BaseModel):
    journey_id: str
    step_id: str
    completed: bool
    completed_at: Optional[str] = None


class JourneyProgressResponse(BaseModel):
    journey_id: str
    completed_step_ids: list[str]


@router.get("/{journey_id}", response_model=JourneyProgressResponse)
async def get_progress(journey_id: str, uid: str = Depends(get_required_user)):
    """Return all completed step IDs for a journey."""
    db = get_supabase()
    result = (
        db.table("user_progress")
        .select("step_id")
        .eq("uid", uid)
        .eq("journey_id", journey_id)
        .execute()
    )
    return JourneyProgressResponse(
        journey_id=journey_id,
        completed_step_ids=[r["step_id"] for r in (result.data or [])],
    )


@router.post("/{journey_id}/{step_id}", response_model=ProgressResponse)
async def mark_step_complete(
    journey_id: str, step_id: str, uid: str = Depends(get_required_user)
):
    """Mark a step as complete. Idempotent."""
    db = get_supabase()
    result = (
        db.table("user_progress")
        .upsert(
            {"uid": uid, "journey_id": journey_id, "step_id": step_id},
            on_conflict="uid,journey_id,step_id",
        )
        .execute()
    )
    row = result.data[0] if result.data else {}
    return ProgressResponse(
        journey_id=journey_id,
        step_id=step_id,
        completed=True,
        completed_at=row.get("completed_at"),
    )


@router.delete("/{journey_id}/{step_id}", response_model=ProgressResponse)
async def mark_step_incomplete(
    journey_id: str, step_id: str, uid: str = Depends(get_required_user)
):
    """Unmark a step as complete."""
    db = get_supabase()
    db.table("user_progress").delete().eq("uid", uid).eq("journey_id", journey_id).eq("step_id", step_id).execute()
    return ProgressResponse(journey_id=journey_id, step_id=step_id, completed=False)
