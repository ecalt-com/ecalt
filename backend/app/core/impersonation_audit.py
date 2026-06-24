import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import _resolve_impersonation_session

logger = logging.getLogger(__name__)


class ImpersonationAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("x-impersonate-session")
        if session_id:
            try:
                result = _resolve_impersonation_session(session_id)
                if result:
                    target_uid, admin_uid = result
                    _write_audit(session_id, admin_uid, target_uid, request.url.path, request.method)
            except Exception:
                logger.warning("Impersonation audit write failed for session %s", session_id)
        return await call_next(request)


def _write_audit(session_id: str, admin_uid: str, target_uid: str, endpoint: str, method: str) -> None:
    from app.core.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_impersonation_audit
                  (session_id, admin_uid, target_uid, endpoint, method)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, admin_uid, target_uid, endpoint, method),
            )
