from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.core.auth import get_required_user
from app.core.database import get_db
from app.services.chat_service import stream_chat
from app.services.subscription_service import check_budget

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    interaction_type: str = Field("daily_chat")


@router.post("/stream")
async def chat_stream(body: ChatRequest, uid: str = Depends(get_required_user)):
    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail={"error": reason, "upgrade_url": "/pricing"},
        )
    return StreamingResponse(
        stream_chat(
            uid=uid,
            user_message=body.message,
            conversation_id=body.conversation_id,
            interaction_type=body.interaction_type,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations")
async def list_conversations(uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, started_at, last_active
                FROM conversations WHERE uid = %s
                ORDER BY last_active DESC LIMIT 20
                """,
                (uid,),
            )
            rows = cur.fetchall()
    return {"conversations": [dict(r) for r in rows]}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM conversations WHERE id = %s AND uid = %s",
                (conversation_id, uid),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Conversation not found")
            cur.execute(
                """
                SELECT id, role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            messages = cur.fetchall()
    return {"messages": [dict(m) for m in messages]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, uid: str = Depends(get_required_user)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversations WHERE id = %s AND uid = %s",
                (conversation_id, uid),
            )
    return {"deleted": True}
