"""
Unit tests for COPPA age verification in the upsert_user endpoint.
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user, get_admin_user

    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


CURRENT_YEAR = date.today().year


# ── Under-13 hard block ───────────────────────────────────────────────────────

def test_under_13_returns_403(client):
    birth_year = CURRENT_YEAR - 10  # age 10
    with patch("app.core.database.get_db") as mock_get_db:
        mock_conn = MagicMock()
        mock_get_db.return_value.__enter__ = lambda s: mock_conn
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post("/api/v1/users", json={"birth_year": birth_year})

    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"] == "under_13"


def test_under_13_does_not_write_to_db(client):
    """COPPA absolute requirement: no DB row written for under-13."""
    birth_year = CURRENT_YEAR - 12  # age 12
    execute_calls = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): execute_calls.append(a)
        def fetchone(self): return None

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return FakeCursor()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    with patch("app.core.database.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda s: FakeConn()
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post("/api/v1/users", json={"birth_year": birth_year})

    assert resp.status_code == 403
    # No INSERT should have been executed
    insert_calls = [c for c in execute_calls if "INSERT" in str(c[0]).upper()]
    assert len(insert_calls) == 0


# ── 13-17: parental consent required ─────────────────────────────────────────

def test_teen_without_parent_email_returns_400(client):
    birth_year = CURRENT_YEAR - 15  # age 15
    with patch("app.core.database.get_db") as mock_get_db:
        mock_conn = MagicMock()
        mock_get_db.return_value.__enter__ = lambda s: mock_conn
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post("/api/v1/users", json={"birth_year": birth_year})

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "parent_email_required"


def test_teen_with_parent_email_creates_consent_record(client):
    birth_year = CURRENT_YEAR - 14  # age 14
    db_row = {
        "uid": TEST_UID,
        "email": "teen@example.com",
        "display_name": "Teen User",
        "photo_url": None,
        "onboarding_done": False,
        "streak_days": 0,
        "whatsapp_opted_in": False,
        "has_notification_prefs": False,
        "account_status": "parental_consent_pending",
        "consent_given_at": None,
    }

    with (
        patch("app.api.v1.endpoints.users.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.users.asyncio.ensure_future"),
        patch("app.services.email_service.send_parental_consent_email", new_callable=AsyncMock),
    ):
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: mock_cur
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = db_row

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        mock_get_db.return_value.__enter__ = lambda s: mock_conn
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/v1/users",
            json={
                "birth_year": birth_year,
                "parent_email": "parent@example.com",
                "email": "teen@example.com",
                "display_name": "Teen User",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["account_status"] == "parental_consent_pending"


# ── 18+: standard flow ────────────────────────────────────────────────────────

def test_adult_gets_active_account(client):
    birth_year = CURRENT_YEAR - 20  # age 20
    db_row = {
        "uid": TEST_UID,
        "email": "adult@example.com",
        "display_name": "Adult User",
        "photo_url": None,
        "onboarding_done": False,
        "streak_days": 0,
        "whatsapp_opted_in": False,
        "has_notification_prefs": False,
        "account_status": "active",
        "consent_given_at": "2026-05-23T00:00:00+00:00",
    }

    with patch("app.api.v1.endpoints.users.get_db") as mock_get_db:
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: mock_cur
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = db_row

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        mock_get_db.return_value.__enter__ = lambda s: mock_conn
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/v1/users",
            json={"birth_year": birth_year, "email": "adult@example.com"},
        )

    assert resp.status_code == 200
    assert resp.json()["account_status"] == "active"


# ── Parental consent confirmation ─────────────────────────────────────────────

def test_consent_confirm_invalid_token(client):
    with patch("app.api.v1.endpoints.users.get_db") as mock_get_db:
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: mock_cur
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        mock_get_db.return_value.__enter__ = lambda s: mock_conn
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/v1/users/consent/confirm?token=nonexistent")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_token"
