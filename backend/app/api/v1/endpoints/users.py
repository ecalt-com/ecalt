from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_required_user
from app.core.supabase import get_supabase

router = APIRouter()


class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    onboarding_done: bool = False


class UserUpsertRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None


@router.post("", response_model=UserProfile, summary="Upsert user on sign-in")
async def upsert_user(body: UserUpsertRequest, uid: str = Depends(get_required_user)):
    """Called once after Google sign-in to create or update the user row."""
    db = get_supabase()
    result = (
        db.table("users")
        .upsert({
            "uid": uid,
            "email": body.email,
            "display_name": body.display_name,
            "photo_url": body.photo_url,
        }, on_conflict="uid")
        .execute()
    )
    row = result.data[0] if result.data else {"uid": uid, "onboarding_done": False}
    return UserProfile(**row)


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
async def get_me(uid: str = Depends(get_required_user)):
    db = get_supabase()
    result = db.table("users").select("*").eq("uid", uid).single().execute()
    return UserProfile(**result.data)


@router.patch("/me/onboarding", response_model=UserProfile, summary="Mark onboarding complete")
async def complete_onboarding(uid: str = Depends(get_required_user)):
    db = get_supabase()
    result = (
        db.table("users")
        .update({"onboarding_done": True})
        .eq("uid", uid)
        .execute()
    )
    return UserProfile(**result.data[0])
