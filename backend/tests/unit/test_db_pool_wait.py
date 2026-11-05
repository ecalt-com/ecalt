"""SC-802: an empty DB pool makes requests wait (then 503), not 500."""
import threading
import time

import pytest
from fastapi import HTTPException

from app.core import database


class _Conn:
    closed = 0
    cursor_factory = None

    def cursor(self):
        class C:
            def execute(self, *a):
                pass
        return C()

    def rollback(self):
        pass

    def commit(self):
        pass


class _Pool:
    """Mimics psycopg2's pool: raises PoolError when every connection is out."""
    def __init__(self, maxconn):
        self.maxconn, self.used = maxconn, 0
        self.lock = threading.Lock()

    def getconn(self):
        import psycopg2.pool
        with self.lock:
            if self.used >= self.maxconn:
                raise psycopg2.pool.PoolError("connection pool exhausted")
            self.used += 1
            return _Conn()

    def putconn(self, conn, close=False):
        with self.lock:
            self.used -= 1


@pytest.fixture
def pool(monkeypatch):
    p = _Pool(2)
    monkeypatch.setattr(database, "_pool", p)
    monkeypatch.setattr(database.settings, "DB_POOL_WAIT_SECONDS", 2.0)
    yield p
    database._slots.pop(id(p), None)


def test_waits_for_a_free_connection_instead_of_failing(pool):
    held = [database.get_db(), database.get_db()]
    for cm in held:
        cm.__enter__()
    got = []

    def third():
        with database.get_db():
            got.append(True)
    t = threading.Thread(target=third)
    t.start()
    time.sleep(0.3)
    assert not got                      # waiting, not failed
    held[0].__exit__(None, None, None)  # a connection comes back
    t.join(2)
    assert got == [True]
    held[1].__exit__(None, None, None)
    assert pool.used == 0


def test_answers_503_busy_after_the_wait(pool, monkeypatch):
    monkeypatch.setattr(database.settings, "DB_POOL_WAIT_SECONDS", 0.2)
    held = [database.get_db(), database.get_db()]
    for cm in held:
        cm.__enter__()
    with pytest.raises(HTTPException) as e:
        with database.get_db():
            pass
    assert e.value.status_code == 503 and e.value.detail["error"] == "server_busy"
    for cm in held:
        cm.__exit__(None, None, None)
    with database.get_db():             # slots were all given back
        pass
