import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not settings.DB_HOST or not settings.DB_PASSWORD:
            raise HTTPException(status_code=503, detail="Database not configured (DB_HOST / DB_PASSWORD missing)")
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                sslmode="require",
            )
            logger.info("PostgreSQL connection pool created → %s:%s/%s", settings.DB_HOST, settings.DB_PORT, settings.DB_NAME)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    return _pool


@contextmanager
def get_db():
    """
    Yield a psycopg2 connection from the pool.
    Commits on success, rolls back on error, always returns the connection.
    Cursors default to RealDictCursor (rows come back as dicts).
    """
    pool = _get_pool()
    conn = pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error("DB error: %s", e)
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        pool.putconn(conn)
