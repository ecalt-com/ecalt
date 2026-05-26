import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
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

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _make_raw_conn() -> psycopg2.extensions.connection:
    if settings.DATABASE_URL:
        return psycopg2.connect(settings.DATABASE_URL, **_CONNECT_KWARGS)
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        **_CONNECT_KWARGS,
    )


def warm_pool() -> None:
    """Pre-create all remaining pool slots in parallel so the first burst of
    requests never blocks waiting for serial TLS handshakes."""
    pool = _get_pool()
    with pool._lock:
        existing = len(pool._pool) + len(pool._used)
        to_create = pool.maxconn - existing
    if to_create <= 0:
        return

    def _try_connect(_):
        try:
            return _make_raw_conn()
        except Exception as e:
            logger.warning("pool warm-up: connection failed: %s", e)
            return None

    with ThreadPoolExecutor(max_workers=to_create) as ex:
        futures = [ex.submit(_try_connect, i) for i in range(to_create)]
        conns = [f.result() for f in as_completed(futures)]

    conns = [c for c in conns if c is not None]
    with pool._lock:
        pool._pool.extend(conns)
    logger.info("DB pool warmed up (%d/%d connections ready)", len(pool._pool), pool.maxconn)


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            if settings.DATABASE_URL:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=5, maxconn=10, dsn=settings.DATABASE_URL, **_CONNECT_KWARGS
                )
            elif settings.DB_HOST and settings.DB_PASSWORD:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=5,
                    maxconn=10,
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
            logger.info("DB connection pool created (minconn=5, maxconn=10)")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("DB pool creation failed (%s): %s", type(e).__name__, e)
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    return _pool


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
    except Exception as e:
        conn.rollback()
        logger.error("DB error (%s): %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    finally:
        pool.putconn(conn)
