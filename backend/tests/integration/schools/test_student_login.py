"""Student sign-in security (SC-205..SC-208, TESTING.md §5).

SEC-03 lockout · SEC-04 class-code throttle, no IP keying · SEC-05 uniform errors
SEC-06 badge rotation · SEC-07 session max age · SEC-13 log hygiene
UNIT-FB custom token structure
"""
import logging
import time

import jwt
import pytest

from tests.factories import schools as f
from tests.schools import identity
from tests.schools.fixtures import fake_service_account

pytestmark = pytest.mark.schools_db

PIN = "482915"


@pytest.fixture
def cls(world, db):
    """Class A1 with S (PIN), a picture-password student and a roll-number student."""
    f.fetch(db, "UPDATE school_students SET secret_kind = 'pin', secret_hash = NULL WHERE uid = %s", (world.S,))
    from app.services.profile_service import hash_pin
    f.fetch(db, "UPDATE school_students SET secret_hash = %s WHERE uid = %s", (hash_pin(f"pin:{PIN}"), world.S))
    pic = f.make_student(db, world.school_a, display_name="Priya Sharma Rao", picture=[3, 14, 0])
    roll = f.make_student(db, world.school_a, display_name="Zed Q", pin="111111", external_ref="R-9")
    f.enroll(db, world.A1, pic)
    f.enroll(db, world.A1, roll)
    return {"code": world.A1["join_code"], "pic": pic, "roll": roll}


def _sign_in(client, code, secret, student_uid=None, external_ref=None, kind="pin"):
    body = {"class_code": code, "secret": {"kind": kind, "value": secret}}
    if student_uid:
        body["student_uid"] = student_uid
    if external_ref:
        body["external_ref"] = external_ref
    return client.post("/api/v1/school-login/sessions", json=body)


def test_roster_lookup(client, world, db, cls):
    code = cls["code"]
    formatted = f"{code[:4]}-{code[4:]}".lower()           # dashes and case don't matter
    r = client.get(f"/api/v1/school-login/classes/{formatted}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["class"]["name"] == "6A" and body["school"]["name"] == "School A" and body["roster_visible"]
    names = {s["display_name"]: s["secret_kind"] for s in body["students"]}
    # first name + last initial; students without a secret yet can't sign in, so aren't listed
    assert names == {"Asha K.": "pin", "Priya R.": "picture", "Zed Q.": "pin"}
    assert "secret_hash" not in r.text and "external_ref" not in r.text

    f.fetch(db, """UPDATE schools SET settings = '{"login_roster_visible": false}' WHERE id = %s""",
            (world.school_a["id"],))
    assert client.get(f"/api/v1/school-login/classes/{code}").json()["students"] == []
    assert client.get("/api/v1/school-login/classes/NOPE-NOPE").json()["detail"]["error"] == "class_code_invalid"
    f.fetch(db, "UPDATE schools SET status = 'suspended' WHERE id = %s", (world.school_a["id"],))
    assert client.get(f"/api/v1/school-login/classes/{code}").status_code == 404


def test_sign_in_with_pin_picture_and_roll_number(client, world, cls):
    r = _sign_in(client, cls["code"], PIN, student_uid=world.S)
    assert r.status_code == 200, r.text
    assert r.json()["student"] == {"uid": world.S, "display_name": "Asha K"}
    r = _sign_in(client, cls["code"], [3, 14, 0], student_uid=cls["pic"], kind="picture")
    assert r.status_code == 200
    r = _sign_in(client, cls["code"], "111111", external_ref="R-9")
    assert r.status_code == 200 and r.json()["student"]["uid"] == cls["roll"]
    # picture order matters
    assert _sign_in(client, cls["code"], [14, 3, 0], student_uid=cls["pic"], kind="picture").status_code == 401


def test_unit_fb_custom_token(client, world, cls):
    token = _sign_in(client, cls["code"], PIN, student_uid=world.S).json()["custom_token"]
    sa = fake_service_account()
    claims = jwt.decode(token, sa["public_key"], algorithms=["RS256"],
                        audience="https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit")
    assert claims["iss"] == claims["sub"] == sa["client_email"]
    assert claims["uid"] == world.S
    assert claims["claims"] == {"school_id": world.school_a["id"], "kind": "school_student"}
    assert claims["exp"] - claims["iat"] == 3600
    assert jwt.get_unverified_header(token)["kid"] == "test-key"


def test_sign_in_unavailable_without_service_account(client, world, cls, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    r = _sign_in(client, cls["code"], PIN, student_uid=world.S)
    assert r.status_code == 503 and r.json()["detail"]["error"] == "login_unavailable"


def test_sec03_lockout(client, world, db, cls):
    for _ in range(4):
        r = _sign_in(client, cls["code"], "000000", student_uid=world.S)
        assert r.status_code == 401 and r.json()["detail"]["error"] == "invalid_student_secret"
    r = _sign_in(client, cls["code"], "000000", student_uid=world.S)
    assert r.status_code == 423 and r.json()["detail"]["error"] == "student_locked"
    assert r.json()["detail"]["locked_until"]
    # the right PIN doesn't get through a lock
    assert _sign_in(client, cls["code"], PIN, student_uid=world.S).status_code == 423
    # other students in the class are unaffected
    assert _sign_in(client, cls["code"], "111111", student_uid=cls["roll"]).status_code == 200
    # the lock expires; success resets the counter
    f.fetch(db, "UPDATE school_students SET locked_until = now() - interval '1 second' WHERE uid = %s", (world.S,))
    _sign_in(client, cls["code"], "000000", student_uid=world.S)
    assert _sign_in(client, cls["code"], PIN, student_uid=world.S).status_code == 200
    row = f.fetch(db, "SELECT failed_attempts FROM school_students WHERE uid = %s", (world.S,))
    assert row == [{"failed_attempts": 0}]
    actions = [r["action"] for r in f.fetch(db, "SELECT action FROM school_audit_log ORDER BY id")]
    # 5 wrong + 1 attempt during the lock + 1 wrong after it; tries on a locked
    # student count towards the class throttle too.
    assert actions.count("student.locked") == 1 and actions.count("student.sign_in_failed") == 7


def test_sec04_class_throttle_and_no_ip_keying(client, world, db, cls):
    # 40 classmates behind one school IP all sign in
    from app.services.profile_service import hash_pin
    pin_hash = hash_pin("pin:222222")
    for i in range(40):
        uid = f.make_student(db, world.school_a, display_name=f"Kid {i}")
        f.fetch(db, "UPDATE school_students SET secret_hash = %s WHERE uid = %s", (pin_hash, uid))
        f.enroll(db, world.A1, uid)
        assert _sign_in(client, cls["code"], "222222", student_uid=uid).status_code == 200
    # a flood of failures throttles the code (not the IP)
    f.fetch(db, """
        INSERT INTO school_audit_log (school_id, action, target_type, target_id)
        SELECT %s, 'student.sign_in_failed', 'class', %s FROM generate_series(1, 50)
    """, (world.school_a["id"], world.A1["id"]))
    r = _sign_in(client, cls["code"], PIN, student_uid=world.S)
    assert r.status_code == 429 and r.json()["detail"]["error"] == "class_code_throttled"
    # another class is unaffected
    other = f.make_student(db, world.school_a, display_name="Other", pin="333333")
    f.enroll(db, world.A2, other)
    assert _sign_in(client, world.A2["join_code"], "333333", student_uid=other).status_code == 200


def test_sec05_uniform_errors(client, world, cls):
    wrong_secret = _sign_in(client, cls["code"], "000000", student_uid=cls["roll"])
    unknown_student = _sign_in(client, cls["code"], "000000", student_uid="stu_doesnotexist")
    other_class = _sign_in(client, cls["code"], "000000", student_uid=world.S2)       # S2 is in A2
    unknown_roll = _sign_in(client, cls["code"], "000000", external_ref="nope")
    malformed = _sign_in(client, cls["code"], "12", student_uid=cls["roll"])
    for r in (wrong_secret, unknown_student, other_class, unknown_roll, malformed):
        assert r.status_code == 401 and r.json()["detail"]["error"] == "invalid_student_secret"
    assert wrong_secret.json() == unknown_student.json()
    # the wrong kind of secret is just a wrong secret
    assert _sign_in(client, cls["code"], [1, 2, 3], student_uid=cls["roll"], kind="picture").status_code == 401


def test_sec06_badge_rotation(client, world, db, cls):
    badge = "badge-token-for-asha-0123456789"
    from app.services.school_student_service import hash_badge_token
    f.fetch(db, "UPDATE school_students SET badge_token_hash = %s WHERE uid = %s", (hash_badge_token(badge), world.S))
    r = client.post("/api/v1/school-login/badge", json={"token": badge})
    assert r.status_code == 200 and r.json()["student"]["uid"] == world.S
    new = client.post(f"/api/v1/schools/{world.school_a['id']}/students/{world.S}/rotate-badge",
                      headers=world.headers("T")).json()["badge_token"]
    r = client.post("/api/v1/school-login/badge", json={"token": badge})
    assert r.status_code == 401 and r.json()["detail"]["error"] == "invalid_badge"
    assert client.post("/api/v1/school-login/badge", json={"token": new}).status_code == 200
    f.fetch(db, "UPDATE school_students SET status = 'archived' WHERE uid = %s", (world.S,))
    assert client.post("/api/v1/school-login/badge", json={"token": new}).status_code == 401


def test_sec07_student_session_max_age(client, world):
    from app.core.config import settings
    stale = int(time.time()) - settings.SCHOOL_STUDENT_SESSION_HOURS * 3600 - 60
    fresh = int(time.time()) - 60
    r = client.get("/api/v1/users/me", headers=identity.bearer(world.S, auth_time=stale))
    assert r.status_code == 401 and r.json()["detail"]["error"] == "school_session_expired"
    assert client.get("/api/v1/users/me", headers=identity.bearer(world.S, auth_time=fresh)).status_code == 200
    # staff sessions are not limited
    assert client.get("/api/v1/schools/mine", headers=identity.bearer(world.T, auth_time=stale)).status_code == 200


def test_sec13_logs_hold_no_secrets(client, world, db, cls, caplog):
    caplog.set_level(logging.DEBUG)
    created = client.post(f"/api/v1/schools/{world.school_a['id']}/students", headers=world.headers("SA"),
                          json={"display_name": "Secretive Sam", "grade": 9}).json()
    _sign_in(client, cls["code"], PIN, student_uid=world.S)
    _sign_in(client, cls["code"], "999999", student_uid=world.S)
    client.post(f"/api/v1/schools/{world.school_a['id']}/students/import", headers=world.headers("SA"),
                json={"csv": "name,roll\nHidden Hari,HX1\n"})
    text = caplog.text + repr([r.__dict__ for r in caplog.records])
    for needle in (PIN, "999999", created["secret"], created["badge_token"], "Secretive Sam", "Hidden Hari"):
        assert needle not in text, needle
    audit = repr(f.fetch(db, "SELECT meta FROM school_audit_log"))
    for needle in (PIN, created["secret"], created["badge_token"], "Secretive Sam", "Hidden Hari"):
        assert needle not in audit, needle
