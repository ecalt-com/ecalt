"""Pytest fixtures for school tests. Import with `from tests.schools.fixtures import *`
in a conftest (tests/integration/schools, tests/api/schools).

DB fixtures need TEST_DATABASE_URL (local ecalt_test only, see harness.py) and
skip otherwise. Each DB test gets the app's connection pool pointed at
ecalt_test, real commits (so nested get_db() calls and row locks behave as in
production), and every table truncated afterwards.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock

import psycopg2.pool
import pytest
from fastapi.testclient import TestClient

from tests.factories import schools as f
from tests.schools import harness, identity

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

__all__ = [
    "World", "clear_caches", "client", "db", "school_db_url", "sent_emails", "world",
    "_db_tables", "_no_real_email", "_school_test_env",
]


def clear_caches() -> None:
    from app.core import auth, school_auth
    from app.services import journey_access
    for cache in (
        auth._identity_cache, auth._status_cache, auth._admin_cache,
        auth._profile_access_cache, auth._has_profiles_cache,
        school_auth._member_cache, journey_access._school_cache, journey_access._access_cache,
    ):
        cache.clear()


@pytest.fixture(autouse=True)
def _school_test_env(monkeypatch):
    """Every school test: test identities, schools flag on, no real email,
    fresh caches and rate-limit counters."""
    from app.core.config import settings
    from app.core.limiter import limiter
    monkeypatch.setattr("app.core.auth._decode_firebase_token", identity.fake_decode)
    monkeypatch.setattr(settings, "SCHOOLS_ENABLED", True)
    monkeypatch.setattr(settings, "VISUAL_TELEMETRY_ENABLED", False)
    identity.reset()
    clear_caches()
    limiter.reset()
    yield
    identity.reset()
    clear_caches()


@pytest.fixture
def sent_emails(monkeypatch):
    """Records transactional emails instead of sending them (.env holds real
    Brevo credentials)."""
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.email_service.send_email", mock)
    return mock


@pytest.fixture(autouse=True)
def _no_real_email(sent_emails):
    return sent_emails


@pytest.fixture(scope="session")
def school_db_url():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set — run tests/db/docker-compose.yml (TESTING.md §3)")
    harness.build_database(TEST_DATABASE_URL)
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def _db_tables(school_db_url):
    conn = harness.connect(school_db_url)
    try:
        return harness.table_names(conn)
    finally:
        conn.close()


@pytest.fixture
def db(school_db_url, _db_tables, monkeypatch):
    """Autocommit connection to ecalt_test for factories and assertions; the
    app's pool points at the same database for this test only."""
    from app.core import database
    from app.core.config import settings
    pool = psycopg2.pool.ThreadedConnectionPool(1, 8, dsn=school_db_url, connect_timeout=5, sslmode="disable")
    monkeypatch.setattr(database, "_pool", pool)
    # If anything rebuilds the pool it must still land on ecalt_test.
    monkeypatch.setattr(settings, "DATABASE_URL", school_db_url)
    monkeypatch.setitem(database._CONNECT_KWARGS, "sslmode", "disable")
    conn = harness.connect(school_db_url)
    try:
        yield conn
    finally:
        harness.truncate_all(conn, _db_tables)
        conn.close()
        pool.closeall()


@pytest.fixture
def client():
    from app.main import app
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


# ── The standard world (TESTING.md §4 personas) ─────────────────────────────

@dataclass
class World:
    school_a: dict
    school_b: dict
    SA: str           # owner of A
    T: str            # teacher in A, lead of A1, creator of C1
    T2: str           # teacher in A, not on A1
    S: str            # student of A in A1
    S2: str           # student of A in A2 only
    SX: str           # student of A, removed from A1
    XA: str           # owner of B
    XS: str           # student of B in B1
    OUT: str          # adult account, no school
    PARENT: str       # adult account with a family profile
    PRF: str          # family profile of PARENT
    ADM: str          # ECALT admin
    A1: dict
    A2: dict
    B1: dict
    C1: str           # published course of A, assigned to A1
    C_DRAFT: str      # draft course of A (never published)
    CB: str           # published course of B, assigned to B1
    N1: str           # ordinary journey owned by OUT
    extra: dict = field(default_factory=dict)

    def headers(self, persona: Optional[str]) -> dict:
        if persona is None or persona == "ANON":
            return {}
        if persona == "PRF":
            return identity.bearer(self.PARENT, x_profile_id=self.PRF)
        return identity.bearer(getattr(self, persona))


@pytest.fixture
def world(db) -> World:
    a = f.make_school(db, name="School A")
    b = f.make_school(db, name="School B")
    sa = f.make_staff(db, a, "owner")
    t = f.make_staff(db, a, "teacher")
    t2 = f.make_staff(db, a, "teacher")
    xa = f.make_staff(db, b, "owner")
    s = f.make_student(db, a, display_name="Asha K")
    s2 = f.make_student(db, a, display_name="Ben L")
    sx = f.make_student(db, a, display_name="Chen M")
    xs = f.make_student(db, b, display_name="Dia N")
    a1 = f.make_class(db, a, name="6A", teachers=(t,))
    a2 = f.make_class(db, a, name="6B")
    b1 = f.make_class(db, b, name="7A", teachers=(xa,))
    f.enroll(db, a1, s)
    f.enroll(db, a2, s2)
    f.enroll(db, a1, sx, removed=True)
    f.enroll(db, b1, xs)
    c1 = f.make_course(db, a, t, title="Photosynthesis")
    c_draft = f.make_course(db, a, t, title="Draft course", published=False)
    cb = f.make_course(db, b, xa, title="Fractions")
    f.assign(db, a1, c1)
    f.assign(db, b1, cb)
    out = f.make_user(db)
    parent = f.make_user(db)
    prf = f.make_family_profile(db, parent)
    adm = f.make_user(db, admin=True)
    n1 = f.make_journey(db, out)
    return World(a, b, sa, t, t2, s, s2, sx, xa, xs, out, parent, prf, adm, a1, a2, b1, c1, c_draft, cb, n1)
