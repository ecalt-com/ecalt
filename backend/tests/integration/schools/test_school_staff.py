"""Schools, staff, invites, settings, DPA, audit (SC-102, SC-106, SC-111..113).

API-01        SCHOOLS_ENABLED off → every school route 404s
API-ADM-*     ECALT admin school management
API-STAFF-*   invites, roles, removal, last-owner guard
API-SET-*     settings + DPA
AUD-*         staff mutations write school_audit_log
UNIT-AUTH-*   suspended / terminated schools
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from tests.factories import schools as f
from tests.schools import identity

pytestmark = pytest.mark.schools_db

H = identity.bearer


def _token_from(sent_emails) -> str:
    body = sent_emails.call_args.kwargs["text_body"]
    return re.search(r"token=([A-Za-z0-9_\-]+)", body).group(1)


def _audit(db, school_id):
    return [r["action"] for r in f.fetch(
        db, "SELECT action FROM school_audit_log WHERE school_id = %s ORDER BY id", (school_id,))]


# ── API-01 ────────────────────────────────────────────────────────────────────

def test_api01_flag_off_hides_every_school_route(client, world, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SCHOOLS_ENABLED", False)
    sid = world.school_a["id"]
    assert client.get("/api/v1/schools/mine", headers=world.headers("SA")).status_code == 404
    assert client.get(f"/api/v1/schools/{sid}", headers=world.headers("SA")).status_code == 404
    assert client.post("/api/v1/school-invites/preview", json={"token": "x" * 30}).status_code == 404
    assert client.get("/api/v1/admin/schools", headers=world.headers("ADM")).status_code == 404


# ── API-ADM ───────────────────────────────────────────────────────────────────

def test_api_adm_create_school_with_owner_invite(client, db, sent_emails):
    adm = f.make_user(db, admin=True)
    r = client.post("/api/v1/admin/schools", headers=H(adm), json={
        "name": "Delhi Public School", "seat_limit": 300, "monthly_ai_budget_cents": 5000,
        "owner_email": "Principal@DPS.example",
    })
    assert r.status_code == 201, r.text
    school = r.json()
    assert school["status"] == "onboarding" and school["slug"] == "delhi-public-school"
    assert school["owner_invite"]["email"] == "principal@dps.example"
    assert school["owner_invite"]["role"] == "owner"
    assert sent_emails.call_args.kwargs["to"] == "principal@dps.example"
    assert "token_hash" not in school["owner_invite"]

    again = client.post("/api/v1/admin/schools", headers=H(adm), json={"name": "Delhi Public School"}).json()
    assert again["slug"] == "delhi-public-school-2"

    listed = client.get("/api/v1/admin/schools?q=delhi", headers=H(adm)).json()
    assert listed["total"] == 2
    assert _audit(db, school["id"]) == ["school.created", "staff.invited"]


def test_api_adm_requires_ecalt_admin(client, world):
    for persona in ("SA", "OUT"):
        assert client.get("/api/v1/admin/schools", headers=world.headers(persona)).status_code == 403
    assert client.get("/api/v1/admin/schools").status_code == 401


def test_api_adm_update_and_terminate(client, world, db):
    sid = world.school_a["id"]
    r = client.patch(f"/api/v1/admin/schools/{sid}", headers=world.headers("ADM"),
                     json={"seat_limit": 40, "monthly_ai_budget_cents": 250})
    assert r.status_code == 200 and r.json()["seat_limit"] == 40
    r = client.patch(f"/api/v1/admin/schools/{sid}", headers=world.headers("ADM"), json={"status": "terminated"})
    assert r.json()["status"] == "terminated" and r.json()["terminated_at"]
    r = client.patch(f"/api/v1/admin/schools/{sid}", headers=world.headers("ADM"), json={"status": "active"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "school_terminated"
    assert client.get(f"/api/v1/admin/schools/not-a-uuid", headers=world.headers("ADM")).status_code == 404


# ── UNIT-AUTH: suspension ────────────────────────────────────────────────────

def test_unit_auth_suspension_and_termination(client, world):
    sid = world.school_a["id"]
    client.patch(f"/api/v1/admin/schools/{sid}", headers=world.headers("ADM"), json={"status": "suspended"})
    r = client.get(f"/api/v1/schools/{sid}", headers=world.headers("SA"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_access_suspended"
    r = client.get("/api/v1/users/me", headers=world.headers("S"))
    assert r.status_code == 200  # GET /users/me stays reachable so the client can explain
    r = client.get(f"/api/v1/progress/{world.C1}", headers=world.headers("S"))
    assert r.status_code == 404
    client.patch(f"/api/v1/admin/schools/{sid}", headers=world.headers("ADM"), json={"status": "terminated"})
    assert client.get(f"/api/v1/schools/{sid}", headers=world.headers("SA")).status_code == 404
    assert client.get("/api/v1/schools/mine", headers=world.headers("SA")).json()["schools"] == []


# ── School detail, settings, DPA ─────────────────────────────────────────────

def test_my_schools_and_detail(client, world):
    mine = client.get("/api/v1/schools/mine", headers=world.headers("T")).json()["schools"]
    assert [(s["name"], s["role"]) for s in mine] == [("School A", "teacher")]
    detail = client.get(f"/api/v1/schools/{world.school_a['id']}", headers=world.headers("T")).json()
    assert detail["my_role"] == "teacher" and "monthly_ai_budget_cents" not in detail
    assert detail["settings"]["teachers_can_create_students"] is False
    owner_view = client.get(f"/api/v1/schools/{world.school_a['id']}", headers=world.headers("SA")).json()
    assert owner_view["monthly_ai_budget_cents"] == 10000.0


def test_api_set_settings(client, world, db):
    sid = world.school_a["id"]
    r = client.patch(f"/api/v1/schools/{sid}", headers=world.headers("SA"),
                     json={"name": "School A Senior", "settings": {"teachers_can_create_students": True}})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "School A Senior"
    assert r.json()["settings"]["teachers_can_create_students"] is True
    assert r.json()["settings"]["login_roster_visible"] is True

    r = client.patch(f"/api/v1/schools/{sid}", headers=world.headers("SA"), json={"settings": {"no_such": 1}})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "invalid_settings"
    r = client.patch(f"/api/v1/schools/{sid}", headers=world.headers("SA"),
                     json={"settings": {"student_daily_tutor_messages": -1}})
    assert r.status_code == 422
    r = client.patch(f"/api/v1/schools/{sid}", headers=world.headers("T"), json={"name": "x"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_role_required"
    assert "school.settings_updated" in _audit(db, sid)


def test_api_set_dpa(client, db):
    school = f.make_school(db, status="onboarding", dpa=False)
    owner = f.make_staff(db, school, "owner")
    admin = f.make_staff(db, school, "admin")
    sid = school["id"]
    r = client.post(f"/api/v1/schools/{sid}/dpa/accept", headers=H(admin), json={"dpa_version": "2026-10"})
    assert r.status_code == 403
    r = client.post(f"/api/v1/schools/{sid}/dpa/accept", headers=H(owner), json={"dpa_version": "2025-01"})
    assert r.status_code == 409 and r.json()["detail"]["current_version"] == "2026-10"
    r = client.post(f"/api/v1/schools/{sid}/dpa/accept", headers=H(owner), json={"dpa_version": "2026-10"})
    assert r.status_code == 200 and r.json()["dpa_accepted"] is True and r.json()["status"] == "active"
    assert _audit(db, sid) == ["school.dpa_accepted"]


# ── Invites ──────────────────────────────────────────────────────────────────

def test_api_staff_invite_preview_accept(client, world, db, sent_emails):
    sid = world.school_a["id"]
    r = client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"),
                    json={"email": "New.Teacher@School.example", "role": "teacher"})
    assert r.status_code == 201, r.text
    token = _token_from(sent_emails)
    assert token not in r.text  # the token only travels by email

    preview = client.post("/api/v1/school-invites/preview", json={"token": token})
    assert preview.json() == {
        "school_name": "School A", "role": "teacher", "email_hint": "n***@school.example",
        "expires_at": preview.json()["expires_at"],
    }

    newcomer = f.make_user(db, email="new.teacher@school.example")
    other = f.make_user(db, email="someone@else.example")
    identity.register(other, email="someone@else.example", email_verified=True)
    r = client.post("/api/v1/school-invites/accept", json={"token": token}, headers=H(other))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "invite_email_mismatch"

    identity.register(newcomer, email="new.teacher@school.example", email_verified=False)
    r = client.post("/api/v1/school-invites/accept", json={"token": token}, headers=H(newcomer))
    assert r.status_code == 403  # unverified email never counts

    identity.register(newcomer, email="NEW.teacher@school.example", email_verified=True)
    r = client.post("/api/v1/school-invites/accept", json={"token": token}, headers=H(newcomer))
    assert r.status_code == 200 and r.json()["role"] == "teacher"
    assert client.get(f"/api/v1/schools/{sid}", headers=H(newcomer)).json()["my_role"] == "teacher"

    r = client.post("/api/v1/school-invites/accept", json={"token": token}, headers=H(newcomer))
    assert r.status_code == 404 and r.json()["detail"]["error"] == "invite_invalid"
    assert _audit(db, sid) == ["staff.invited", "staff.joined"]


def test_api_staff_invite_rules(client, world, db, sent_emails):
    sid = world.school_a["id"]
    admin = f.make_staff(db, world.school_a, "admin")
    r = client.post(f"/api/v1/schools/{sid}/staff/invites", headers=H(admin),
                    json={"email": "boss@school.example", "role": "owner"})
    assert r.status_code == 403
    r = client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("T"),
                    json={"email": "x@school.example"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_role_required"
    teacher_email = f.fetch(db, "SELECT email FROM users WHERE uid = %s", (world.T,))[0]["email"]
    r = client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": teacher_email})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "already_member"
    r = client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": "not-an-email"})
    assert r.status_code == 422

    # re-inviting revokes the earlier link
    client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": "a@b.example"})
    first = _token_from(sent_emails)
    client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": "a@b.example"})
    assert client.post("/api/v1/school-invites/preview", json={"token": first}).status_code == 404
    staff = client.get(f"/api/v1/schools/{sid}/staff", headers=world.headers("SA")).json()
    assert [i["email"] for i in staff["invites"]] == ["a@b.example"]
    assert client.get(f"/api/v1/schools/{sid}/staff", headers=world.headers("T")).json()["invites"] == []

    # revoke
    invite_id = staff["invites"][0]["id"]
    assert client.delete(f"/api/v1/schools/{sid}/staff/invites/{invite_id}",
                         headers=world.headers("SA")).status_code == 204
    assert client.delete(f"/api/v1/schools/{sid}/staff/invites/{invite_id}",
                         headers=world.headers("SA")).status_code == 404


def test_api_staff_invite_expiry_and_adult_only(client, world, db, sent_emails):
    sid = world.school_a["id"]
    client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": "teen@x.example"})
    token = _token_from(sent_emails)
    teen = f.make_user(db, email="teen@x.example", age_group="teen")
    identity.register(teen, email="teen@x.example", email_verified=True)
    r = client.post("/api/v1/school-invites/accept", json={"token": token}, headers=H(teen))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "staff_must_be_adult"

    f.fetch(db, "UPDATE school_invites SET expires_at = %s", (datetime.now(timezone.utc) - timedelta(minutes=1),))
    assert client.post("/api/v1/school-invites/preview", json={"token": token}).status_code == 410


# ── Roles and removal ────────────────────────────────────────────────────────

def test_api_staff_roles_and_last_owner(client, world, db):
    sid = world.school_a["id"]
    r = client.patch(f"/api/v1/schools/{sid}/staff/{world.SA}", headers=world.headers("SA"), json={"role": "teacher"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "last_owner"
    r = client.delete(f"/api/v1/schools/{sid}/staff/{world.SA}", headers=world.headers("SA"))
    assert r.status_code == 409

    r = client.patch(f"/api/v1/schools/{sid}/staff/{world.T2}", headers=world.headers("SA"), json={"role": "admin"})
    assert r.status_code == 200
    # an admin can't touch an owner
    r = client.patch(f"/api/v1/schools/{sid}/staff/{world.SA}", headers=world.headers("T2"), json={"role": "teacher"})
    assert r.status_code == 403
    # a second owner makes the first one removable
    client.patch(f"/api/v1/schools/{sid}/staff/{world.T2}", headers=world.headers("SA"), json={"role": "owner"})
    assert client.delete(f"/api/v1/schools/{sid}/staff/{world.SA}", headers=world.headers("SA")).status_code == 204
    assert _audit(db, sid) == ["staff.role_changed", "staff.role_changed", "staff.left"]


def test_api_staff_removal_and_leaving(client, world, db):
    sid = world.school_a["id"]
    r = client.delete(f"/api/v1/schools/{sid}/staff/{world.T2}", headers=world.headers("T"))
    assert r.status_code == 403
    assert client.get(f"/api/v1/schools/{sid}", headers=world.headers("T")).status_code == 200
    assert client.delete(f"/api/v1/schools/{sid}/staff/{world.T}", headers=world.headers("SA")).status_code == 204
    # access ends immediately, including the school's courses
    assert client.get(f"/api/v1/schools/{sid}", headers=world.headers("T")).status_code == 404
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("T")).status_code == 404
    assert f.fetch(db, "SELECT 1 FROM class_teachers WHERE uid = %s", (world.T,)) == []
    # their course stays with the school
    assert f.fetch(db, "SELECT status FROM school_courses WHERE journey_id = %s", (world.C1,)) == [{"status": "published"}]
    # a teacher may leave on their own
    assert client.delete(f"/api/v1/schools/{sid}/staff/{world.T2}", headers=world.headers("T2")).status_code == 204
    assert _audit(db, sid) == ["staff.removed", "staff.left"]


def test_removed_member_can_be_reinvited(client, world, db, sent_emails):
    sid = world.school_a["id"]
    client.delete(f"/api/v1/schools/{sid}/staff/{world.T}", headers=world.headers("SA"))
    email = f.fetch(db, "SELECT email FROM users WHERE uid = %s", (world.T,))[0]["email"]
    client.post(f"/api/v1/schools/{sid}/staff/invites", headers=world.headers("SA"), json={"email": email, "role": "admin"})
    identity.register(world.T, email=email, email_verified=True)
    r = client.post("/api/v1/school-invites/accept", json={"token": _token_from(sent_emails)}, headers=world.headers("T"))
    assert r.status_code == 200
    assert client.get(f"/api/v1/schools/{sid}", headers=world.headers("T")).json()["my_role"] == "admin"
