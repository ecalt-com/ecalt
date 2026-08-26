"""
API tests for the course marketplace: browse, like toggle, and fork.

GET  /api/v1/journeys/marketplace         - public listing, published only
POST /api/v1/journeys/{id}/like           - toggle like, requires auth
POST /api/v1/journeys/{id}/fork           - copy a published journey into caller's own list
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID

STEPS = [{"id": "s1", "title": "Step 1", "description": "d", "type": "concept", "estimated_minutes": 10}]

SOURCE_JOURNEY_ROW = {
    "id": "src-journey",
    "uid": "creator-uid",
    "question": "How does X work?",
    "title": "X Explained",
    "description": "desc",
    "age_group": "all",
    "difficulty": "beginner",
    "estimated_hours": 1.0,
    "steps": STEPS,
    "tags": ["x"],
    "icon": "🎯",
    "hero_image_url": None,
    "learner_purpose": None,
    "topic_expertise": None,
    "created_at": "2026-08-01T00:00:00+00:00",
    "marketplace_status": "published",
    "popularity_score": 20,
    "like_count": 3,
    "forked_from_id": None,
}

FORKED_JOURNEY_ROW = {
    **SOURCE_JOURNEY_ROW,
    "id": "new-forked-id",
    "uid": TEST_UID,
    "marketplace_status": "private",
    "popularity_score": 0,
    "like_count": 0,
    "forked_from_id": "src-journey",
}


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID

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


def _db(fetchone=(), fetchall=(), rowcount=0):
    """get_db mock whose fetchone/fetchall iterators are shared across
    successive `with get_db()` blocks (the fork endpoint opens several)."""
    fetchone_iter = iter(fetchone)
    fetchall_iter = iter(fetchall)

    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchone.side_effect = fetchone_iter
        cur.fetchall.side_effect = fetchall_iter
        cur.rowcount = rowcount
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)

        yield conn

    return _get_db


class TestMarketplaceListing:
    def test_returns_published_journeys(self, anon_client):
        db = _db(fetchone=[{"n": 1}], fetchall=[[SOURCE_JOURNEY_ROW]])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = anon_client.get("/api/v1/journeys/marketplace")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["journeys"][0]["id"] == "src-journey"
        assert body["journeys"][0]["marketplace_status"] == "published"

    def test_empty_marketplace(self, anon_client):
        db = _db(fetchone=[{"n": 0}], fetchall=[[]])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = anon_client.get("/api/v1/journeys/marketplace")
        assert r.status_code == 200
        assert r.json() == {"journeys": [], "total": 0, "limit": 20, "offset": 0}


class TestLikeToggle:
    def test_like_new_journey(self, client):
        db = _db(fetchone=[{"id": 1}, {"like_count": 1}], rowcount=0)
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/src-journey/like")
        assert r.status_code == 200
        assert r.json() == {"liked": True, "like_count": 1}

    def test_unlike_existing(self, client):
        db = _db(fetchone=[{"id": 1}, {"like_count": 0}], rowcount=1)
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/src-journey/like")
        assert r.status_code == 200
        assert r.json() == {"liked": False, "like_count": 0}

    def test_like_missing_journey_404(self, client):
        db = _db(fetchone=[None])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/nope/like")
        assert r.status_code == 404

    def test_like_requires_auth(self, anon_client):
        r = anon_client.post("/api/v1/journeys/src-journey/like")
        assert r.status_code == 401


class TestFork:
    def test_fork_published_journey(self, client):
        db = _db(fetchone=[SOURCE_JOURNEY_ROW, FORKED_JOURNEY_ROW])
        with patch("app.api.v1.endpoints.journeys.get_db", db), \
             patch("app.api.v1.endpoints.journeys.invalidate_profile"), \
             patch("app.api.v1.endpoints.journeys._invalidate_recommendation_cache"):
            r = client.post("/api/v1/journeys/src-journey/fork")
        assert r.status_code == 200
        journey = r.json()["journey"]
        assert journey["id"] == "new-forked-id"
        assert journey["forked_from_id"] == "src-journey"
        assert journey["marketplace_status"] == "private"

    def test_fork_unpublished_journey_404(self, client):
        db = _db(fetchone=[None])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/private-journey/fork")
        assert r.status_code == 404

    def test_fork_requires_auth(self, anon_client):
        r = anon_client.post("/api/v1/journeys/src-journey/fork")
        assert r.status_code == 401


class TestSubmitToMarketplace:
    def test_owner_can_submit_private_journey(self, client):
        db = _db(fetchone=[{"uid": TEST_UID, "marketplace_status": "private"},
                            {"marketplace_status": "pending_review"}])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/mine/submit-to-marketplace")
        assert r.status_code == 200
        assert r.json() == {"marketplace_status": "pending_review"}

    def test_owner_can_resubmit_rejected_journey(self, client):
        db = _db(fetchone=[{"uid": TEST_UID, "marketplace_status": "rejected"},
                            {"marketplace_status": "pending_review"}])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/mine/submit-to-marketplace")
        assert r.status_code == 200
        assert r.json() == {"marketplace_status": "pending_review"}

    def test_already_published_is_a_noop(self, client):
        db = _db(fetchone=[{"uid": TEST_UID, "marketplace_status": "published"}])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/mine/submit-to-marketplace")
        assert r.status_code == 200
        assert r.json() == {"marketplace_status": "published"}

    def test_non_owner_gets_403(self, client):
        db = _db(fetchone=[{"uid": "someone-else", "marketplace_status": "private"}])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/not-mine/submit-to-marketplace")
        assert r.status_code == 403

    def test_missing_journey_404(self, client):
        db = _db(fetchone=[None])
        with patch("app.api.v1.endpoints.journeys.get_db", db):
            r = client.post("/api/v1/journeys/nope/submit-to-marketplace")
        assert r.status_code == 404

    def test_requires_auth(self, anon_client):
        r = anon_client.post("/api/v1/journeys/mine/submit-to-marketplace")
        assert r.status_code == 401
