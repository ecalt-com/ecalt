import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_CONNECT_KWARGS = {
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "sslmode": "require",
}


def _make_connection() -> psycopg2.extensions.connection:
    try:
        if settings.DATABASE_URL:
            conn = psycopg2.connect(settings.DATABASE_URL, **_CONNECT_KWARGS)
        elif settings.DB_HOST and settings.DB_PASSWORD:
            conn = psycopg2.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                **_CONNECT_KWARGS,
            )
        else:
            raise HTTPException(
                status_code=503,
                detail="Database not configured. Set DATABASE_URL or DB_HOST / DB_PASSWORD.",
            )
        return conn
    except HTTPException:
        raise
    except Exception as e:
        logger.error("DB connect failed (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


@contextmanager
def get_db():
    conn = _make_connection()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error("DB error (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()
