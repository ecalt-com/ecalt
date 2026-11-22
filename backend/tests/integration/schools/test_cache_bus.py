"""E1: invalidations reach other workers through the database. Real SQL."""
import time

import pytest

from app.core import auth, cache_bus, school_auth
from app.services import journey_access

pytestmark = pytest.mark.schools_db

NOW = lambda: time.monotonic()  # noqa: E731


@pytest.fixture
def bus(db, monkeypatch):
    monkeypatch.setattr(cache_bus.settings, "CACHE_BUS_ENABLED", True)
    for cache in (auth._status_cache, auth._identity_cache, auth._profile_access_cache, auth._has_profiles_cache,
                  school_auth._member_cache, journey_access._access_cache):
        cache.clear()
    yield
    cache_bus.stop_listener()


def _rows(db):
    with db.cursor() as cur:
        cur.execute("SELECT kind, key FROM cache_invalidations ORDER BY seq")
        return cur.fetchall()


def test_every_cache_is_evicted_by_a_published_invalidation(bus):
    """Simulates another worker: publish only (no local eviction), then poll."""
    auth._status_cache["u1"] = ("active", NOW())
    auth._identity_cache["fb1"] = ("u1", NOW())
    auth._has_profiles_cache["parent"] = (True, NOW())
    auth._profile_access_cache[("parent", "prof_1")] = (True, NOW())
    school_auth._member_cache[("u1", "s1")] = (None, NOW())
    journey_access._access_cache[("u1", "j1")] = (True, NOW())

    cache_bus.publish("status", uid="u1")
    cache_bus.publish("identity", firebase_uid="fb1")
    cache_bus.publish("profile", parent_uid="parent", profile_uid="prof_1")
    cache_bus.publish("school_member", school_id="s1", uid="u1")
    cache_bus.publish("journey_access", uid="u1", journey_id="j1")
    assert cache_bus.poll_once(0) > 0

    assert "u1" not in auth._status_cache and "fb1" not in auth._identity_cache
    assert "parent" not in auth._has_profiles_cache and ("parent", "prof_1") not in auth._profile_access_cache
    assert ("u1", "s1") not in school_auth._member_cache and ("u1", "j1") not in journey_access._access_cache


def test_the_helpers_evict_locally_and_publish(bus, db):
    auth._status_cache["u1"] = ("active", NOW())
    auth.invalidate_status_cache("u1")
    assert "u1" not in auth._status_cache
    school_auth.invalidate_school_member_cache(school_id="s1")
    journey_access.invalidate_journey_access(uid="u1", journey_id="j1")
    auth.invalidate_profile_cache(parent_uid="p", profile_uid=None)
    auth.invalidate_identity_cache("fb1")
    assert [k for k, _ in _rows(db)] == ["status", "school_member", "journey_access", "profile", "identity"]


def test_disabled_bus_writes_nothing(db, monkeypatch):
    monkeypatch.setattr(cache_bus.settings, "CACHE_BUS_ENABLED", False)
    auth.invalidate_status_cache("u1")
    assert _rows(db) == [] and cache_bus.start_listener() is False


def test_enabled_by_default_only_with_several_workers(monkeypatch):
    monkeypatch.setattr(cache_bus.settings, "CACHE_BUS_ENABLED", None)
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    assert cache_bus.enabled() is False
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    assert cache_bus.enabled() is True
    monkeypatch.setenv("WEB_CONCURRENCY", "lots")
    assert cache_bus.enabled() is False


def test_polling_only_applies_newer_rows_and_survives_junk(bus, db):
    cache_bus.publish("status", uid="old")
    first = cache_bus.poll_once(0)
    with db.cursor() as cur:
        cur.execute("INSERT INTO cache_invalidations (kind, key) VALUES ('nope', '{}'), ('status', 'not json'), "
                    "('status', '{\"uid\": \"new\"}')")
    auth._status_cache["old"] = ("active", NOW())
    auth._status_cache["new"] = ("active", NOW())
    assert cache_bus.poll_once(first) > first
    assert "new" not in auth._status_cache          # the good row after two bad ones still applied
    assert "old" in auth._status_cache              # already seen: not applied again


def test_prune_removes_old_rows_only(bus, db):
    cache_bus.publish("status", uid="u1")
    with db.cursor() as cur:
        cur.execute("INSERT INTO cache_invalidations (kind, key, at) VALUES ('status','{}', now() - interval '3 days')")
    assert cache_bus.prune() == 1 and len(_rows(db)) == 1


def test_the_listener_thread_picks_up_changes_made_after_it_started(bus, monkeypatch):
    monkeypatch.setattr(cache_bus, "POLL_SECONDS", 0.1)
    assert cache_bus.start_listener() is True
    time.sleep(0.4)                                    # let it record its starting point
    auth._status_cache["u9"] = ("active", NOW())
    cache_bus.publish("status", uid="u9")              # as if another worker had changed it
    deadline = time.time() + 5
    while "u9" in auth._status_cache and time.time() < deadline:
        time.sleep(0.1)
    assert "u9" not in auth._status_cache
