"""
API tests for admin marketplace moderation:

GET  /api/v1/admin/marketplace-queue
POST /api/v1/admin/marketplace-queue/{id}/approve
POST /api/v1/admin/marketplace-queue/{id}/reject
POST /api/v1/admin/marketplace-queue/{id}/reset
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_ADMIN_UID


@pytest.fixture
def admin_client():
    from app.main import app
    from app.core.auth import get_admin_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_admin_user] = lambda: TEST_ADMIN_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture
def anon_client():
    from app.main import app

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def _db(fetchone=(), fetchall=()):
    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchone.side_effect = list(fetchone)
        cur.fetchall.side_effect = list(fetchall)
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)

        yield conn

    return _get_db


class TestQueueListing:
    def test_lists_pending_journeys(self, admin_client):
        rows = [{"id": "j1", "uid": "u1", "title": "T", "popularity_score": 10, "like_count": 5}]
        db = _db(fetchall=[rows])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.get("/api/v1/admin/marketplace-queue")
        assert r.status_code == 200
        assert r.json() == {"queue": rows}

    def test_requires_admin(self, anon_client):
        r = anon_client.get("/api/v1/admin/marketplace-queue")
        assert r.status_code == 401

    def test_status_all_lets_admin_browse_and_search_everything(self, admin_client):
        rows = [{"id": "j1", "uid": "u1", "title": "Quantum Basics", "marketplace_status": "private", "popularity_score": 0, "like_count": 0}]
        db = _db(fetchall=[rows])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.get("/api/v1/admin/marketplace-queue?status=all&search=quantum")
        assert r.status_code == 200
        assert r.json() == {"queue": rows}


class TestApproveRejectReset:
    def test_approve_publishes(self, admin_client):
        db = _db(fetchone=[{"id": "j1", "marketplace_status": "published"}])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.post("/api/v1/admin/marketplace-queue/j1/approve")
        assert r.status_code == 200
        assert r.json()["marketplace_status"] == "published"

    def test_reject_rejects(self, admin_client):
        db = _db(fetchone=[{"id": "j1", "marketplace_status": "rejected"}])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.post("/api/v1/admin/marketplace-queue/j1/reject")
        assert r.status_code == 200
        assert r.json()["marketplace_status"] == "rejected"

    def test_reset_returns_to_private(self, admin_client):
        db = _db(fetchone=[{"id": "j1", "marketplace_status": "private"}])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.post("/api/v1/admin/marketplace-queue/j1/reset")
        assert r.status_code == 200
        assert r.json()["marketplace_status"] == "private"

    def test_approve_missing_journey_404(self, admin_client):
        db = _db(fetchone=[None])
        with patch("app.api.v1.endpoints.admin.get_db", db):
            r = admin_client.post("/api/v1/admin/marketplace-queue/nope/approve")
        assert r.status_code == 404

    def test_approve_requires_admin(self, anon_client):
        r = anon_client.post("/api/v1/admin/marketplace-queue/j1/approve")
        assert r.status_code == 401
