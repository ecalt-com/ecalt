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


@router.get("/db-check", summary="Debug: check DB tables exist")
async def db_check():
    """Temporary debug endpoint — shows which tables exist and any errors."""
    tables = ["users", "plan_configs", "subscriptions", "token_usage",
              "conversations", "conversation_messages", "knowledge_nodes"]
    results = {}
    errors = {}

    for table in tables:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    results[table] = cur.fetchone()[0]
        except Exception as e:
            errors[table] = str(e)

    # Also check users columns
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users' ORDER BY column_name"
                )
                results["users_columns"] = [r[0] for r in cur.fetchall()]
    except Exception as e:
        errors["users_columns"] = str(e)

    return {"counts": results, "errors": errors}
