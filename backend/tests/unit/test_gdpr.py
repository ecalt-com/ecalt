"""
Unit tests for GDPR data rights: erasure (DELETE /me) and export (GET /me/export).
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user

    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


def _make_db_mock(fetchone_val=None, fetchall_val=None):
    """Build a reusable mock get_db context manager."""
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: mock_cur
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = fetchone_val
    mock_cur.fetchall.return_value = fetchall_val or []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_get_db = MagicMock()
    mock_get_db.return_value.__enter__ = lambda s: mock_conn
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    return mock_get_db, mock_cur


# ── DELETE /me ────────────────────────────────────────────────────────────────

def test_delete_account_returns_204(client):
    mock_get_db, mock_cur = _make_db_mock(fetchone_val=None)

    with (
        patch("app.api.v1.endpoints.users.get_db", mock_get_db),
    ):
        resp = client.delete("/api/v1/users/me")

    assert resp.status_code == 204


def test_delete_account_executes_cascade(client):
    """Verify that DELETE runs deletes across all expected tables."""
    executed_queries = []

    class TrackingCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, *args): executed_queries.append(sql.strip())
        def fetchone(self): return None
        def fetchall(self): return []

    class TrackingConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return TrackingCursor()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    from contextlib import contextmanager

    @contextmanager
    def fake_get_db():
        yield TrackingConn()

    with patch("app.api.v1.endpoints.users.get_db", fake_get_db):
        resp = client.delete("/api/v1/users/me")

    assert resp.status_code == 204

    # Must delete users row
    assert any("DELETE FROM users" in q for q in executed_queries)
    # Must delete conversations
    assert any("DELETE FROM conversations" in q for q in executed_queries)
    # Must delete conversation_messages (or equivalent subquery)
    assert any("conversation_messages" in q for q in executed_queries)
    # Must delete knowledge_nodes
    assert any("DELETE FROM knowledge_nodes" in q for q in executed_queries)
    # Must delete mind_signatures
    assert any("DELETE FROM mind_signatures" in q for q in executed_queries)
    # Must audit via deletion_requests
    assert any("INSERT INTO deletion_requests" in q for q in executed_queries)


def test_delete_continues_if_stripe_cancel_fails(client):
    """Stripe cancellation failure must not abort the deletion."""
    mock_get_db, mock_cur = _make_db_mock(
        fetchone_val={"stripe_subscription_id": "sub_test123"}
    )

    with (
        patch("app.api.v1.endpoints.users.get_db", mock_get_db),
        patch("stripe.Subscription.cancel", side_effect=Exception("stripe down")),
    ):
        resp = client.delete("/api/v1/users/me")

    assert resp.status_code == 204


# ── GET /me/export ────────────────────────────────────────────────────────────

def test_export_returns_json_with_all_sections(client):
    user_row = {
        "uid": TEST_UID,
        "email": "user@example.com",
        "display_name": "Test User",
        "photo_url": None,
        "onboarding_done": True,
        "streak_days": 3,
        "account_status": "active",
        "consent_given_at": None,
        "consent_version": "1.0",
        "created_at": None,
    }

    class ExportCursor:
        def __init__(self):
            self._calls = 0
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, *a): self._calls += 1
        def fetchone(self): return user_row
        def fetchall(self): return []

    class ExportConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return ExportCursor()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    from contextlib import contextmanager

    @contextmanager
    def fake_get_db():
        yield ExportConn()

    with patch("app.api.v1.endpoints.users.get_db", fake_get_db):
        resp = client.get("/api/v1/users/me/export")

    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body
    assert "journeys" in body
    assert "conversations" in body
    assert "knowledge_nodes" in body
    assert "mind_signatures" in body
    assert "exported_at" in body


def test_export_has_attachment_header(client):
    user_row = {
        "uid": TEST_UID, "email": None, "display_name": None,
        "photo_url": None, "onboarding_done": False, "streak_days": 0,
        "account_status": "active", "consent_given_at": None,
        "consent_version": "1.0", "created_at": None,
    }

    class MinCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return user_row
        def fetchall(self): return []

    class MinConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return MinCursor()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    from contextlib import contextmanager

    @contextmanager
    def fake_get_db():
        yield MinConn()

    with patch("app.api.v1.endpoints.users.get_db", fake_get_db):
        resp = client.get("/api/v1/users/me/export")

    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "ecalt-data-export.json" in resp.headers.get("content-disposition", "")
