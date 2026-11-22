"""Cross-worker cache invalidation (E1).

Several caches live in each uvicorn worker's memory (account status, profile
access, school membership, journey access, identity mapping) and are evicted
by the invalidate_* helpers after a change. With more than one worker, a helper
only reached its own worker, so the others could serve stale state (including
stale denials) until the 60 s TTL ran out.

publish() records the eviction in `cache_invalidations`; every worker runs a
small poller that applies rows newer than the last one it saw, which brings the
staleness window down to the poll interval (about 2 s). Postgres LISTEN/NOTIFY is
not used because the Supabase transaction pooler doesn't support it.

Disabled with a single worker (nothing to tell): enabled when CACHE_BUS_ENABLED
is true, or unset with WEB_CONCURRENCY > 1.
"""
import json
import logging
import os
import threading
from typing import Callable, Optional

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0
_handlers: dict[str, Callable[..., None]] = {}
_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def enabled() -> bool:
    flag = getattr(settings, "CACHE_BUS_ENABLED", None)
    if flag is not None:
        return bool(flag)
    try:
        return int(os.getenv("WEB_CONCURRENCY", "1") or 1) > 1
    except ValueError:
        return False


def register(kind: str, handler: Callable[..., None]) -> None:
    """handler(**args) evicts from this process's cache only; it must not publish."""
    _handlers[kind] = handler


def publish(kind: str, **args) -> None:
    """Tell the other workers to evict. Best-effort: a failure leaves them on the TTL."""
    if not enabled():
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO cache_invalidations (kind, key) VALUES (%s, %s)",
                            (kind, json.dumps(args, sort_keys=True)))
    except Exception:
        logger.warning("cache invalidation %s not published", kind, exc_info=True)


def apply(kind: str, args: dict) -> bool:
    handler = _handlers.get(kind)
    if handler is None:
        return False
    handler(**args)
    return True


def _max_seq() -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(seq), 0) AS m FROM cache_invalidations")
            return int(cur.fetchone()["m"])


def poll_once(last_seq: int) -> int:
    """Apply invalidations newer than last_seq; returns the new high-water mark."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT seq, kind, key FROM cache_invalidations WHERE seq > %s ORDER BY seq LIMIT 500",
                        (last_seq,))
            rows = cur.fetchall()
    for row in rows:
        try:
            apply(row["kind"], json.loads(row["key"]))
        except Exception:
            logger.warning("cache invalidation %s failed", row["kind"], exc_info=True)
        last_seq = max(last_seq, int(row["seq"]))
    return last_seq


def prune(older_than_hours: int = 24) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cache_invalidations WHERE at < now() - make_interval(hours => %s)",
                        (older_than_hours,))
            return cur.rowcount


def _loop() -> None:
    last = None
    while not _stop.is_set():
        try:
            if last is None:
                last = _max_seq()          # only changes made from now on
            else:
                last = poll_once(last)
        except Exception:
            logger.warning("cache bus poll failed", exc_info=True)
        _stop.wait(POLL_SECONDS)


def start_listener() -> bool:
    global _thread
    if not enabled() or (_thread is not None and _thread.is_alive()):
        return False
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="cache-bus", daemon=True)
    _thread.start()
    logger.info("cache bus listener started (pid %s)", os.getpid())
    return True


def stop_listener() -> None:
    _stop.set()
