import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None

# Keepalive params: detect a dead connection within ~50s instead of waiting
# for the OS default (hours). This prevents the 3-4s hang on stale sockets.
_KEEPALIVE_KWARGS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "connect_timeout": 10,
}


def _build_pool() -> psycopg2.pool.ThreadedConnectionPool:
    if settings.DATABASE_URL:
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.DATABASE_URL,
            **_KEEPALIVE_KWARGS,
        )

    if not settings.DB_HOST or not settings.DB_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Set DATABASE_URL or DB_HOST / DB_PASSWORD.",
        )

    return psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        sslmode="require",
        **_KEEPALIVE_KWARGS,
    )


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        try:
            _pool = _build_pool()
            logger.info("DB pool created")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("DB pool creation failed: %s", e)
            raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    return _pool


def _reset_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
        except Exception:
            pass
        _pool = None


@contextmanager
def get_db():
    pool = _get_pool()
    conn = pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.OperationalError as e:
        # Stale / dropped connection — discard the whole pool and retry once
        conn.rollback()
        pool.putconn(conn)
        logger.warning("Stale connection detected (%s), resetting pool and retrying", e)
        _reset_pool()

        new_pool = _get_pool()
        conn = new_pool.getconn()
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        try:
            yield conn
            conn.commit()
        except Exception as retry_e:
            conn.rollback()
            logger.error("DB error after retry: %s", retry_e)
            raise HTTPException(status_code=500, detail="Database error")
        finally:
            new_pool.putconn(conn)
        return
    except Exception as e:
        conn.rollback()
        logger.error("DB error (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        try:
            pool.putconn(conn)
        except Exception:
            pass
