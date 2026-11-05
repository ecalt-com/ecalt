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


def _max_conn() -> int:
    return max(5, int(settings.DB_POOL_MAX))


# psycopg2's pool raises PoolError the moment it's empty. Under a burst (a whole
# class signing in at once) that turned into 500s (SC-802 load test). A
# semaphore per pool makes callers wait for a free connection instead, up to
# DB_POOL_WAIT_SECONDS, then answer 503 "busy".
_slots: dict[int, threading.BoundedSemaphore] = {}


def _slot(pool) -> threading.BoundedSemaphore:
    sem = _slots.get(id(pool))
    if sem is None:
        with _pool_lock:
            sem = _slots.setdefault(id(pool), threading.BoundedSemaphore(pool.maxconn))
    return sem


def _busy() -> HTTPException:
    return HTTPException(status_code=503, detail={
        "error": "server_busy", "message": "We're busy right now. Please try again in a moment."})


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
                    minconn=5, maxconn=_max_conn(), dsn=settings.DATABASE_URL, **_CONNECT_KWARGS
                )
            elif settings.DB_HOST and settings.DB_PASSWORD:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=5,
                    maxconn=_max_conn(),
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
            logger.info("DB connection pool created (minconn=5, maxconn=%d)", _max_conn())
        except HTTPException:
            raise
        except Exception as e:
            logger.error("DB pool creation failed (%s): %s", type(e).__name__, e)
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    return _pool


def _is_conn_alive(conn) -> bool:
    """Ping the server to confirm the connection is still usable.

    Supabase's pgBouncer closes idle connections after its server_idle_timeout,
    but psycopg2's pool doesn't know — it hands out the dead socket and the
    first real query raises 'server closed the connection unexpectedly'.
    """
    if conn.closed:
        return False
    try:
        conn.cursor().execute("SELECT 1")
        conn.rollback()  # clear the implicit BEGIN so the caller starts clean
        return True
    except Exception:
        return False


@contextmanager
def get_db():
    pool = _get_pool()
    slot = _slot(pool)
    if not slot.acquire(timeout=float(settings.DB_POOL_WAIT_SECONDS)):
        logger.error("DB pool: no free connection after %ss (maxconn=%d)", settings.DB_POOL_WAIT_SECONDS, pool.maxconn)
        raise _busy()
    try:
        conn = pool.getconn()
    except psycopg2.pool.PoolError:
        slot.release()
        logger.error("DB pool exhausted despite a free slot (maxconn=%d)", pool.maxconn)
        raise _busy()
    except Exception:
        slot.release()
        raise

    # Replace stale connections before handing them to the caller.
    if not _is_conn_alive(conn):
        logger.warning("stale DB connection detected — replacing with fresh one")
        pool.putconn(conn, close=True)
        try:
            conn = pool.getconn()
        except Exception:
            slot.release()
            raise

    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        # A NUL byte in a path or body string can never be stored in Postgres
        # text: that's bad input, not a server fault.
        if isinstance(e, ValueError) and "NUL (0x00)" in str(e):
            raise HTTPException(status_code=400, detail={
                "error": "invalid_input", "message": "The request contains an invalid character."})
        logger.error("DB error (%s): %s", type(e).__name__, e)
        # Details stay in the log: the client never sees SQL or constraint names.
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # Discard broken connections so the pool never reuses a dead socket.
        try:
            pool.putconn(conn, close=bool(conn.closed))
        finally:
            slot.release()
