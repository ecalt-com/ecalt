from supabase import create_client, Client
from fastapi import HTTPException
from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise HTTPException(status_code=503, detail="Database not configured")
        try:
            _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database client error: {e}")
    return _client
