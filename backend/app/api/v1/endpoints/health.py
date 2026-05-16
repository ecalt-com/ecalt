from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get(
    "/",
    summary="Health check",
    response_description="Service liveness status with UTC timestamp",
)
async def health():
    """
    Liveness probe used by Railway and load balancers.

    Returns `status: ok` plus the current UTC timestamp when the service is up.
    """
    return {
        "status": "ok",
        "service": "ecalt-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
