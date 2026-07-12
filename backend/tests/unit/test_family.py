"""
Unit tests for the /family router (parental accounts plan, Phase 1).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID

CHILD_UID = "child-uid-123"


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user, get_active_user

    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID
    app.dependency_overrides[get_active_user] = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


def _mock_db(mock_get_db, fetchone_results=None, fetchall_results=None):
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: mock_cur
    mock_cur.__exit__ = MagicMock(return_value=False)
    if isinstance(fetchone_results, list):
        mock_cur.fetchone.side_effect = fetchone_results
    else:
        mock_cur.fetchone.return_value = fetchone_results
    if fetchall_results is not None:
        mock_cur.fetchall.return_value = fetchall_results

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_get_db.return_value.__enter__ = lambda s: mock_conn
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cur


def _parent_row(**overrides):
    row = {
        "uid": TEST_UID,
        "email": "parent@example.com",
        "display_name": "Parent User",
        "age_group_flag": "adult",
        "account_status": "active",
        "jurisdiction": "US",
    }
    row.update(overrides)
    return row


CURRENT_YEAR = datetime.now(timezone.utc).year


def _create_child_body(**overrides):
    body = {
        "display_name": "Kid",
        "birth_year": CURRENT_YEAR - 15,
        "email": "kid@example.com",
        "password": "supersecret1",
    }
    body.update(overrides)
    return body


# ── POST /family/children (Path A) ────────────────────────────────────────────

def test_create_child_success(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.services.firebase_admin.create_firebase_user",
              new_callable=AsyncMock, return_value=(CHILD_UID, None)),
        patch("app.api.v1.endpoints.family.asyncio.ensure_future"),
    ):
        mock_cur = _mock_db(mock_get_db, [_parent_row(), {"n": 0}])
        resp = client.post("/api/v1/family/children", json=_create_child_body())

    assert resp.status_code == 201
    body = resp.json()
    assert body["child_uid"] == CHILD_UID
    assert body["managed"] is True
    assert body["chat_enabled"] is True  # 13+ default on

    executed = [str(c[0][0]) for c in mock_cur.execute.call_args_list]
    assert any("INSERT INTO family_links" in q for q in executed)
    assert any("INSERT INTO child_settings" in q for q in executed)
    assert any("INSERT INTO consent_events" in q for q in executed)
    assert any("role = 'parent'" in q for q in executed)


def test_create_child_under_13_blocked_by_default(client):
    with patch("app.api.v1.endpoints.family.get_db") as mock_get_db:
        _mock_db(mock_get_db, [_parent_row()])
        resp = client.post(
            "/api/v1/family/children",
            json=_create_child_body(birth_year=CURRENT_YEAR - 10),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "under_13_not_available"


def test_create_child_under_13_allowed_with_flag_and_chat_off(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.family.settings.ENABLE_MANAGED_CHILDREN", True),
        patch("app.services.firebase_admin.create_firebase_user",
              new_callable=AsyncMock, return_value=(CHILD_UID, None)),
        patch("app.api.v1.endpoints.family.asyncio.ensure_future"),
    ):
        mock_cur = _mock_db(mock_get_db, [_parent_row(), {"n": 0}])
        resp = client.post(
            "/api/v1/family/children",
            json=_create_child_body(birth_year=CURRENT_YEAR - 10),
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["age_group"] == "child"
    assert body["chat_enabled"] is False  # AI chat off by default under 13

    settings_calls = [
        c for c in mock_cur.execute.call_args_list
        if "INSERT INTO child_settings" in str(c[0][0])
    ]
    # chat off + card verification tier for under-13s
    assert settings_calls and settings_calls[0][0][1] == (CHILD_UID, False, "card")


def test_create_child_rejects_adults(client):
    with patch("app.api.v1.endpoints.family.get_db") as mock_get_db:
        _mock_db(mock_get_db, [_parent_row()])
        resp = client.post(
            "/api/v1/family/children",
            json=_create_child_body(birth_year=CURRENT_YEAR - 25),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "not_a_minor"


def test_create_child_requires_adult_parent(client):
    with patch("app.api.v1.endpoints.family.get_db") as mock_get_db:
        _mock_db(mock_get_db, [_parent_row(age_group_flag="teen")])
        resp = client.post("/api/v1/family/children", json=_create_child_body())

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "adult_account_required"


def test_create_child_seat_limit(client):
    with patch("app.api.v1.endpoints.family.get_db") as mock_get_db:
        _mock_db(mock_get_db, [_parent_row(), {"n": 5}])
        resp = client.post("/api/v1/family/children", json=_create_child_body())

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "family_full"


def test_create_child_email_exists(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.services.firebase_admin.create_firebase_user",
              new_callable=AsyncMock, return_value=(None, "EMAIL_EXISTS")),
    ):
        _mock_db(mock_get_db, [_parent_row(), {"n": 0}])
        resp = client.post("/api/v1/family/children", json=_create_child_body())

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "email_exists"


# ── GET /family/children ──────────────────────────────────────────────────────

def test_list_children(client):
    rows = [
        {"child_uid": CHILD_UID, "display_name": "Kid", "email": "kid@example.com",
         "account_status": "active", "age_group_flag": "teen", "birth_year": 2011,
         "birth_month": None, "paused": False, "streak_days": 3, "managed": True,
         "chat_enabled": True, "content_age_band": None, "weekly_digest_enabled": True,
         "transcript_visibility": "summaries",
         "linked_at": datetime.now(timezone.utc)},
    ]
    with patch("app.api.v1.endpoints.family.get_db") as mock_get_db:
        _mock_db(mock_get_db, fetchall_results=rows)
        resp = client.get("/api/v1/family/children")

    assert resp.status_code == 200
    children = resp.json()["children"]
    assert len(children) == 1
    assert children[0]["child_uid"] == CHILD_UID
    assert isinstance(children[0]["linked_at"], str)


# ── Path B: authenticated approve / decline ───────────────────────────────────

def _pending_token_row(uid=CHILD_UID):
    return {
        "uid": uid,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=3),
        "status": "pending",
        "parent_email": "parent@example.com",
        "display_name": "Teen User",
    }


def test_approve_link_request_activates_and_links(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.users._load_consent_token", return_value=_pending_token_row()),
        patch("app.api.v1.endpoints.family.asyncio.ensure_future"),
    ):
        mock_cur = _mock_db(mock_get_db, [_parent_row(), {"jurisdiction": "US"}])
        resp = client.post("/api/v1/family/link-requests/sometoken/approve")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["child_uid"] == CHILD_UID

    executed = [str(c[0][0]) for c in mock_cur.execute.call_args_list]
    assert any("account_status = 'active'" in q for q in executed)
    assert any("INSERT INTO family_links" in q for q in executed)
    assert any("INSERT INTO consent_events" in q for q in executed)


def test_approve_link_request_rejects_self_approval(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.users._load_consent_token",
              return_value=_pending_token_row(uid=TEST_UID)),
    ):
        _mock_db(mock_get_db, [_parent_row()])
        resp = client.post("/api/v1/family/link-requests/sometoken/approve")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "self_approval"


def test_decline_link_request(client):
    with (
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.users._load_consent_token", return_value=_pending_token_row()),
    ):
        mock_cur = _mock_db(mock_get_db, [_parent_row(), {"jurisdiction": "US"}])
        resp = client.post("/api/v1/family/link-requests/sometoken/decline")

    assert resp.status_code == 200
    assert resp.json()["status"] == "refused"
    executed = [str(c[0][0]) for c in mock_cur.execute.call_args_list]
    assert any("status = 'refused'" in q for q in executed)
    assert not any("account_status = 'active'" in q for q in executed)


# ── DELETE /family/children/{uid} ─────────────────────────────────────────────

def test_delete_child_authorized(client):
    with (
        patch("app.api.v1.endpoints.family.verify_parent_of"),
        patch("app.api.v1.endpoints.family.get_db") as mock_get_db,
        patch("app.api.v1.endpoints.family.record_consent_event") as mock_event,
        patch("app.services.account_service.delete_user_account") as mock_delete,
        patch("app.services.firebase_admin.delete_firebase_user",
              new_callable=AsyncMock, return_value=True),
    ):
        _mock_db(mock_get_db, [_parent_row()])
        resp = client.delete(f"/api/v1/family/children/{CHILD_UID}")

    assert resp.status_code == 204
    mock_delete.assert_called_once_with(CHILD_UID)
    assert mock_event.call_args[0][:2] == (CHILD_UID, "revoked")


def test_delete_child_forbidden_without_link(client):
    with patch(
        "app.api.v1.endpoints.family.verify_parent_of",
        side_effect=HTTPException(status_code=403, detail="You do not manage this account"),
    ):
        resp = client.delete(f"/api/v1/family/children/{CHILD_UID}")

    assert resp.status_code == 403
