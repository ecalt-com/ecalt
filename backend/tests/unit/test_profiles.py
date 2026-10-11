"""
Unit tests for family profiles (plans/family-profiles): X-Profile-Id resolution,
account-holder guards, parent PIN + unlock tokens, and the claim flow.
Every DB touch is mocked — backend/.env points at production.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

PARENT = "parent-uid"
PROFILE = "prof_abc123"


@pytest.fixture(autouse=True)
def _clear_caches():
    from app.core import auth
    auth._profile_access_cache.clear()
    auth._has_profiles_cache.clear()
    auth._identity_cache.clear()
    yield
    auth._profile_access_cache.clear()
    auth._has_profiles_cache.clear()
    auth._identity_cache.clear()


def _fake_db(fetchone=None, fetchall=None, raise_exc=None):
    cur = MagicMock()
    if isinstance(fetchone, list):
        cur.fetchone.side_effect = fetchone
    else:
        cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    if raise_exc:
        cur.execute.side_effect = raise_exc
    cur.__enter__ = lambda s: cur
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur

    @contextmanager
    def get_db():
        yield conn

    return get_db, cur


# ── Profile resolution ───────────────────────────────────────────────────────

def test_no_header_resolves_to_signed_in_account():
    from app.core.auth import get_optional_user
    assert get_optional_user(real_uid=PARENT, x_profile_id=None, x_impersonate_session=None) == PARENT
    assert get_optional_user(real_uid=PARENT, x_profile_id=PARENT, x_impersonate_session=None) == PARENT


def test_unauthenticated_ignores_profile_header():
    from app.core.auth import get_optional_user
    assert get_optional_user(real_uid=None, x_profile_id=PROFILE, x_impersonate_session=None) is None


def test_linked_profile_resolves():
    from app.core.auth import get_optional_user
    get_db, _ = _fake_db(fetchone={"?column?": 1})
    with patch("app.core.database.get_db", get_db):
        assert get_optional_user(real_uid=PARENT, x_profile_id=PROFILE,
                                 x_impersonate_session=None) == PROFILE


def test_unlinked_profile_rejected_never_falls_back():
    from app.core.auth import get_optional_user
    get_db, _ = _fake_db(fetchone=None)
    with patch("app.core.database.get_db", get_db):
        with pytest.raises(HTTPException) as exc:
            get_optional_user(real_uid=PARENT, x_profile_id="prof_someone_else",
                              x_impersonate_session=None)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "profile_not_allowed"


def test_profile_check_fails_closed_on_db_error():
    from app.core.auth import get_optional_user
    get_db, _ = _fake_db(raise_exc=RuntimeError("db down"))
    with patch("app.core.database.get_db", get_db):
        with pytest.raises(HTTPException) as exc:
            get_optional_user(real_uid=PARENT, x_profile_id=PROFILE, x_impersonate_session=None)
    assert exc.value.status_code == 403


def test_profile_query_requires_profile_type_and_active_link():
    from app.core.auth import _verify_profile_access
    get_db, cur = _fake_db(fetchone={"?column?": 1})
    with patch("app.core.database.get_db", get_db):
        _verify_profile_access(PARENT, PROFILE)
    sql = cur.execute.call_args[0][0]
    assert "profile_type = 'profile'" in sql and "status = 'active'" in sql
    assert cur.execute.call_args[0][1] == (PARENT, PROFILE)


def test_profile_header_with_impersonation_is_rejected():
    from app.core.auth import get_optional_user
    with pytest.raises(HTTPException) as exc:
        get_optional_user(real_uid=PARENT, x_profile_id=PROFILE, x_impersonate_session="sess-1")
    assert exc.value.status_code == 400


def test_invalidate_profile_cache_forces_recheck():
    from app.core.auth import _verify_profile_access, invalidate_profile_cache
    get_db, _ = _fake_db(fetchone={"?column?": 1})
    with patch("app.core.database.get_db", get_db):
        _verify_profile_access(PARENT, PROFILE)
    invalidate_profile_cache(profile_uid=PROFILE)
    get_db2, _ = _fake_db(fetchone=None)
    with patch("app.core.database.get_db", get_db2):
        with pytest.raises(HTTPException):
            _verify_profile_access(PARENT, PROFILE)


# ── Identity mapping (claimed profiles) ──────────────────────────────────────

def test_identity_maps_claimed_login_to_profile_uid():
    from app.core.auth import _map_identity
    get_db, _ = _fake_db(fetchone={"uid": PROFILE})
    with patch("app.core.database.get_db", get_db):
        assert _map_identity("firebase-xyz") == PROFILE


def test_identity_passthrough_for_ordinary_accounts():
    from app.core.auth import _map_identity
    get_db, _ = _fake_db(fetchone=None)
    with patch("app.core.database.get_db", get_db):
        assert _map_identity("firebase-xyz") == "firebase-xyz"


def test_identity_lookup_fails_closed():
    from app.core.auth import _map_identity
    get_db, _ = _fake_db(raise_exc=RuntimeError("db down"))
    with patch("app.core.database.get_db", get_db):
        with pytest.raises(HTTPException) as exc:
            _map_identity("firebase-xyz")
    assert exc.value.status_code == 503


# ── Account-holder guards ────────────────────────────────────────────────────

def test_account_holder_rejects_child_profile_header():
    from app.core.auth import get_account_holder
    with pytest.raises(HTTPException) as exc:
        get_account_holder(real_uid=PARENT, x_profile_id=PROFILE)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "parent_profile_required"
    assert get_account_holder(real_uid=PARENT, x_profile_id=None) == PARENT
    assert get_account_holder(real_uid=PARENT, x_profile_id=PARENT) == PARENT


def test_account_holder_requires_auth():
    from app.core.auth import get_account_holder
    with pytest.raises(HTTPException) as exc:
        get_account_holder(real_uid=None, x_profile_id=None)
    assert exc.value.status_code == 401


def test_unlock_not_required_without_profiles():
    from app.core.auth import require_parent_unlock
    with patch("app.core.auth.account_has_profiles", return_value=False):
        require_parent_unlock(PARENT, None)  # no raise


def test_unlock_required_with_profiles():
    from app.core.auth import require_parent_unlock
    from app.services.profile_service import make_unlock_token
    with patch("app.core.auth.account_has_profiles", return_value=True):
        with pytest.raises(HTTPException) as exc:
            require_parent_unlock(PARENT, None)
        assert exc.value.detail["error"] == "parent_unlock_required"
        require_parent_unlock(PARENT, make_unlock_token(PARENT))  # no raise


def test_has_profiles_fails_closed():
    from app.core.auth import account_has_profiles
    get_db, _ = _fake_db(raise_exc=RuntimeError("db down"))
    with patch("app.core.database.get_db", get_db):
        assert account_has_profiles(PARENT) is True


# ── Unlock tokens ────────────────────────────────────────────────────────────

def test_unlock_token_roundtrip_and_binding():
    from app.services.profile_service import make_unlock_token, verify_unlock_token
    tok = make_unlock_token(PARENT)
    assert verify_unlock_token(tok, PARENT)
    assert not verify_unlock_token(tok, "other-parent")
    assert not verify_unlock_token(None, PARENT)
    assert not verify_unlock_token("garbage", PARENT)


def test_unlock_token_expires():
    import time
    from app.services.profile_service import UNLOCK_TTL_SECONDS, make_unlock_token, verify_unlock_token
    tok = make_unlock_token(PARENT, now=time.time() - UNLOCK_TTL_SECONDS - 1)
    assert not verify_unlock_token(tok, PARENT)


def test_unlock_token_tamper_detected():
    import base64
    from app.services.profile_service import make_unlock_token, verify_unlock_token
    tok = make_unlock_token(PARENT)
    raw = base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)).decode()
    uid, exp, sig = raw.rsplit("|", 2)
    forged = base64.urlsafe_b64encode(f"{uid}|{int(exp) + 99999}|{sig}".encode()).decode().rstrip("=")
    assert not verify_unlock_token(forged, PARENT)


# ── PIN ──────────────────────────────────────────────────────────────────────

def test_pin_hash_roundtrip():
    from app.services.profile_service import check_pin, hash_pin
    h = hash_pin("4821")
    assert h.startswith("scrypt$") and "4821" not in h
    assert check_pin("4821", h)
    assert not check_pin("4822", h)
    assert hash_pin("4821") != h  # salted


def test_pin_format():
    from app.services.profile_service import is_valid_pin_format
    assert is_valid_pin_format("1234") and is_valid_pin_format("123456")
    assert not is_valid_pin_format("123") and not is_valid_pin_format("1234567")
    assert not is_valid_pin_format("12a4")


def test_verify_pin_ok_resets_attempts():
    from app.services import profile_service as ps
    get_db, cur = _fake_db(fetchone={"pin_hash": ps.hash_pin("1234"),
                                     "failed_attempts": 2, "locked_until": None})
    with patch("app.services.profile_service.get_db", get_db):
        assert ps.verify_pin(PARENT, "1234") == ("ok", None)
    assert "failed_attempts = 0" in cur.execute.call_args[0][0]


def test_verify_pin_wrong_counts_down():
    from app.services import profile_service as ps
    get_db, _ = _fake_db(fetchone={"pin_hash": ps.hash_pin("1234"),
                                   "failed_attempts": 1, "locked_until": None})
    with patch("app.services.profile_service.get_db", get_db):
        result, info = ps.verify_pin(PARENT, "9999")
    assert result == "invalid" and info["attempts_left"] == ps.MAX_PIN_ATTEMPTS - 2


def test_verify_pin_locks_after_max_attempts():
    from app.services import profile_service as ps
    get_db, _ = _fake_db(fetchone={"pin_hash": ps.hash_pin("1234"),
                                   "failed_attempts": ps.MAX_PIN_ATTEMPTS - 1, "locked_until": None})
    with patch("app.services.profile_service.get_db", get_db):
        result, info = ps.verify_pin(PARENT, "9999")
    assert result == "locked" and "locked_until" in info


def test_verify_pin_while_locked_rejects_even_correct_pin():
    from app.services import profile_service as ps
    until = datetime.now(timezone.utc) + timedelta(minutes=5)
    get_db, _ = _fake_db(fetchone={"pin_hash": ps.hash_pin("1234"),
                                   "failed_attempts": 0, "locked_until": until})
    with patch("app.services.profile_service.get_db", get_db):
        result, _ = ps.verify_pin(PARENT, "1234")
    assert result == "locked"


def test_verify_pin_no_pin():
    from app.services import profile_service as ps
    get_db, _ = _fake_db(fetchone=None)
    with patch("app.services.profile_service.get_db", get_db):
        assert ps.verify_pin(PARENT, "1234") == ("no_pin", None)


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_active_account_holder, get_parent_session, get_signed_in_uid
    app.dependency_overrides[get_active_account_holder] = lambda: PARENT
    app.dependency_overrides[get_parent_session] = lambda: PARENT
    app.dependency_overrides[get_signed_in_uid] = lambda: PARENT
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_pin_verify_endpoint_returns_unlock_token(client):
    from app.services.profile_service import verify_unlock_token
    with patch("app.services.profile_service.verify_pin", return_value=("ok", None)):
        resp = client.post("/api/v1/family/pin/verify", json={"pin": "1234"})
    assert resp.status_code == 200
    assert verify_unlock_token(resp.json()["unlock_token"], PARENT)


def test_pin_verify_endpoint_wrong_pin(client):
    with patch("app.services.profile_service.verify_pin",
               return_value=("invalid", {"attempts_left": 3})):
        resp = client.post("/api/v1/family/pin/verify", json={"pin": "1234"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "invalid_pin"
    assert resp.json()["detail"]["attempts_left"] == 3


def test_pin_verify_endpoint_locked(client):
    with patch("app.services.profile_service.verify_pin",
               return_value=("locked", {"locked_until": "2026-01-01T00:00:00+00:00"})):
        resp = client.post("/api/v1/family/pin/verify", json={"pin": "1234"})
    assert resp.status_code == 423


def test_set_pin_first_time(client):
    get_db, _ = _fake_db(fetchone={"uid": PARENT, "email": "p@x.com", "display_name": "P",
                                   "age_group_flag": "adult", "account_status": "active",
                                   "jurisdiction": "US"})
    with (
        patch("app.api.v1.endpoints.family.get_db", get_db),
        patch("app.services.profile_service.has_pin", return_value=False),
        patch("app.services.profile_service.set_pin") as mock_set,
    ):
        resp = client.post("/api/v1/family/pin", json={"pin": "2468"})
    assert resp.status_code == 200
    mock_set.assert_called_once_with(PARENT, "2468")


def test_change_pin_requires_current(client):
    get_db, _ = _fake_db(fetchone={"uid": PARENT, "email": "p@x.com", "display_name": "P",
                                   "age_group_flag": "adult", "account_status": "active",
                                   "jurisdiction": "US"})
    with (
        patch("app.api.v1.endpoints.family.get_db", get_db),
        patch("app.services.profile_service.has_pin", return_value=True),
        patch("app.services.profile_service.set_pin") as mock_set,
    ):
        resp = client.post("/api/v1/family/pin", json={"pin": "2468"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "current_pin_required"
    mock_set.assert_not_called()


def test_pin_reset_requires_recent_sign_in(client):
    import time
    with patch("app.core.auth.token_auth_time", return_value=int(time.time()) - 3600):
        resp = client.post("/api/v1/family/pin/reset", json={"pin": "2468"},
                           headers={"Authorization": "Bearer x"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "recent_login_required"


def test_pin_reset_with_fresh_sign_in(client):
    import time
    with (
        patch("app.core.auth.token_auth_time", return_value=int(time.time()) - 30),
        patch("app.services.profile_service.set_pin") as mock_set,
    ):
        resp = client.post("/api/v1/family/pin/reset", json={"pin": "2468"},
                           headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200
    mock_set.assert_called_once_with(PARENT, "2468")


def test_list_profiles(client):
    get_db, _ = _fake_db(
        fetchone={"uid": PARENT, "display_name": "Parent", "photo_url": None,
                  "avatar": None, "profile_type": "account"},
        fetchall=[{"uid": PROFILE, "display_name": "Kid", "avatar": "fox",
                   "age_group": "child", "account_status": "active", "paused": False,
                   "onboarding_done": False, "chat_enabled": False,
                   "verification_required": False}],
    )
    with (
        patch("app.api.v1.endpoints.family.get_db", get_db),
        patch("app.services.profile_service.has_pin", return_value=True),
    ):
        resp = client.get("/api/v1/family/profiles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["uid"] == PARENT
    assert body["profiles"][0]["uid"] == PROFILE
    assert body["pin_set"] is True


def test_claim_invite_rejects_under_13(client):
    year = datetime.now(timezone.utc).year
    get_db, _ = _fake_db(fetchone={"profile_type": "profile", "birth_year": year - 10,
                                   "birth_month": None, "account_status": "active"})
    with (
        patch("app.api.v1.endpoints.family.verify_parent_of"),
        patch("app.api.v1.endpoints.family.get_db", get_db),
    ):
        resp = client.post(f"/api/v1/family/children/{PROFILE}/claim-invite")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "too_young_to_claim"


def test_claim_invite_for_teen_profile(client):
    year = datetime.now(timezone.utc).year
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    get_db, _ = _fake_db(fetchone=[
        {"profile_type": "profile", "birth_year": year - 15, "birth_month": None,
         "account_status": "active"},
        {"expires_at": expires},
    ])
    with (
        patch("app.api.v1.endpoints.family.verify_parent_of"),
        patch("app.api.v1.endpoints.family.get_db", get_db),
    ):
        resp = client.post(f"/api/v1/family/children/{PROFILE}/claim-invite")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["code"]) == 8 and body["claim_url"].endswith(body["code"])


# ── Claim ────────────────────────────────────────────────────────────────────

def _claim(client_, fetchone):
    get_db, cur = _fake_db(fetchone=fetchone)
    with (
        patch("app.core.auth.token_claims",
              return_value={"sub": "fb-new", "email": "teen@x.com", "picture": None}),
        patch("app.api.v1.endpoints.users.get_db", get_db),
        patch("app.api.v1.endpoints.users.record_consent_event") as mock_event,
    ):
        resp = client_.post("/api/v1/users/claim", json={"code": "ABCD2345"},
                            headers={"Authorization": "Bearer x"})
    return resp, cur, mock_event


def _invite(**kw):
    row = {"uid": PROFILE, "parent_uid": PARENT,
           "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
           "claimed_at": None, "profile_type": "profile", "jurisdiction": "US"}
    row.update(kw)
    return row


def test_claim_maps_login_onto_profile(client):
    resp, cur, mock_event = _claim(client, [_invite(), None, None])
    assert resp.status_code == 200
    assert resp.json() == {"status": "claimed", "uid": PROFILE}
    executed = [str(c[0][0]) for c in cur.execute.call_args_list]
    assert any("INSERT INTO auth_identities" in q for q in executed)
    assert any("profile_type = 'account'" in q for q in executed)
    assert mock_event.call_args[0][:2] == (PROFILE, "granted")


def test_claim_replaces_sign_in_stub_row(client):
    resp, cur, _ = _claim(client, [_invite(), None, {"birth_year": None}])
    assert resp.status_code == 200
    executed = [str(c[0][0]) for c in cur.execute.call_args_list]
    assert any("DELETE FROM users" in q for q in executed)


def test_claim_refuses_existing_real_account(client):
    resp, cur, _ = _claim(client, [_invite(), None, {"birth_year": 2000}])
    assert resp.status_code == 409
    executed = [str(c[0][0]) for c in cur.execute.call_args_list]
    assert not any("INSERT INTO auth_identities" in q for q in executed)


def test_claim_rejects_expired_code(client):
    resp, _, _ = _claim(client, [_invite(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_claim_code"


def test_claim_rejects_used_code(client):
    resp, _, _ = _claim(client, [_invite(claimed_at=datetime.now(timezone.utc))])
    assert resp.status_code == 400


# ── Login purge ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_purge_login_unclaimed_profile_has_nothing_to_delete():
    from app.services import firebase_admin
    get_db, _ = _fake_db(fetchone=None)
    with (
        patch("app.core.database.get_db", get_db),
        patch.object(firebase_admin, "delete_firebase_user", new_callable=AsyncMock) as mock_del,
    ):
        assert await firebase_admin.purge_login(PROFILE) is True
    mock_del.assert_not_called()


@pytest.mark.asyncio
async def test_purge_login_claimed_profile_deletes_mapped_login():
    from app.services import firebase_admin
    get_db, _ = _fake_db(fetchone={"firebase_uid": "fb-teen"})
    with (
        patch("app.core.database.get_db", get_db),
        patch.object(firebase_admin, "delete_firebase_user",
                     new_callable=AsyncMock, return_value=True) as mock_del,
    ):
        assert await firebase_admin.purge_login(PROFILE) is True
    mock_del.assert_awaited_once_with("fb-teen")


@pytest.mark.asyncio
async def test_purge_login_ordinary_account():
    from app.services import firebase_admin
    with patch.object(firebase_admin, "delete_firebase_user",
                      new_callable=AsyncMock, return_value=True) as mock_del:
        await firebase_admin.purge_login("fb-adult")
    mock_del.assert_awaited_once_with("fb-adult")
