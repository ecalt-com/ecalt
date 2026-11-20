"""One leader process per container for in-process background work.

uvicorn starts one process per worker (WEB_CONCURRENCY). The APScheduler jobs
and the school job worker must run in exactly one of them, or emails are
sent twice and AI job concurrency multiplies. The first process to take an
exclusive lock on a file in the container's temp dir becomes the leader and
holds the lock for its lifetime. The OS releases it when that process exits,
and uvicorn's replacement worker takes it over.
"""
import fcntl
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_LOCK_PATH = os.path.join(tempfile.gettempdir(), "ecalt-api-leader.lock")
_lock_fd: Optional[int] = None


def acquire_leadership(path: str = _LOCK_PATH) -> bool:
    """True if this process is (now) the leader. Never raises: if the lock
    can't be used at all, behave as a single process and lead."""
    global _lock_fd
    if _lock_fd is not None:
        return True
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        logger.warning("leader lock unavailable at %s; running background work here", path)
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    _lock_fd = fd
    return True


def release_leadership() -> None:
    global _lock_fd
    if _lock_fd is not None:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(_lock_fd)
            _lock_fd = None
