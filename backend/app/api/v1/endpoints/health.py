from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.database import get_db

router = APIRouter()


@router.get(
    "",
    summary="Health check",
    response_description="Service liveness status with UTC timestamp",
)
async def health():
    db_status = "ok"
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception:
        db_status = "degraded"

    return {
        "status": "ok",
        "db": db_status,
        "service": "ecalt-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
