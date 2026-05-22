from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_required_user
from app.core.database import get_db

router = APIRouter()


class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    onboarding_done: bool = False
    streak_days: int = 0
    whatsapp_opted_in: bool = False
    has_notification_prefs: bool = False


class UserUpsertRequest(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None


@router.post("", response_model=UserProfile, summary="Upsert user on sign-in")
async def upsert_user(body: UserUpsertRequest, uid: str = Depends(get_required_user)):
    """Called once after Google sign-in to create or update the user row."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (uid, email, display_name, photo_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO UPDATE
                    SET email        = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        photo_url    = EXCLUDED.photo_url
                RETURNING *
                """,
                (uid, body.email, body.display_name, body.photo_url),
            )
            row = cur.fetchone()
    return UserProfile(**dict(row))


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
async def get_me(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*,
                       COALESCE(np.whatsapp_opted_in, FALSE) AS whatsapp_opted_in,
                       (np.uid IS NOT NULL)                  AS has_notification_prefs
                  FROM users u
             LEFT JOIN notification_preferences np ON np.uid = u.uid
                 WHERE u.uid = %s
                """,
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        return UserProfile(uid=uid)
    return UserProfile(**dict(row))


@router.patch("/me/onboarding", response_model=UserProfile, summary="Mark onboarding complete")
async def complete_onboarding(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET onboarding_done = TRUE WHERE uid = %s RETURNING *",
                (uid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**dict(row))


class InterestsRequest(BaseModel):
    topics: list[str]
    age_group: str = "all"


@router.patch("/me/interests", summary="Save user interest topics")
async def save_interests(body: InterestsRequest, uid: str = Depends(get_required_user)):
    topics = [t.lower()[:50] for t in body.topics[:12]]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_interests (uid, topics, age_group)
                VALUES (%s, %s, %s)
                ON CONFLICT (uid) DO UPDATE SET
                    topics = EXCLUDED.topics,
                    age_group = EXCLUDED.age_group,
                    last_updated = now()
                """,
                (uid, topics, body.age_group),
            )
    # Invalidate daily spark cache so it regenerates with new topics
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_sparks WHERE uid = %s", (uid,))
    return {"saved": True}
