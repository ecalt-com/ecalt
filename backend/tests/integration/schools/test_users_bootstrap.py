"""SC-105: POST /users and GET /users/me for school students (AUTHZ-S*).

Students skip the age, consent and onboarding gates — their school created and
authorised them — and get account_kind 'school_student' plus their school and
classes. Everyone else gets their usual account_kind.
"""
import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


@pytest.mark.parametrize("method,path", [("POST", "/api/v1/users"), ("GET", "/api/v1/users/me")])
def test_student_bootstrap(client, world, db, method, path):
    body = {"email": "spoof@x.example", "display_name": "Spoof", "birth_year": 2001} if method == "POST" else None
    r = client.request(method, path, json=body, headers=world.headers("S"))
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["account_kind"] == "school_student"
    assert me["display_name"] == "Asha K"
    assert me["onboarding_done"] is True and me["needs_birth_year"] is False
    assert me["school"] == {"id": world.school_a["id"], "name": "School A"}
    assert me["student"]["classes"] == [{"id": world.A1["id"], "name": "6A", "grade": 6, "subject": None}]
    assert me["email"] is None
    # nothing the client sent was stored
    assert f.fetch(db, "SELECT email, display_name, birth_year FROM users WHERE uid = %s", (world.S,)) == [
        {"email": None, "display_name": "Asha K", "birth_year": 2012}
    ]


def test_archived_student_bootstrap_is_refused(client, world, db):
    f.fetch(db, "UPDATE school_students SET status = 'archived' WHERE uid = %s", (world.S,))
    r = client.post("/api/v1/users", json={}, headers=world.headers("S"))
    assert r.status_code == 403 and r.json()["detail"]["error"] == "school_access_suspended"


def test_account_kind_for_everyone_else(client, world):
    assert client.get("/api/v1/users/me", headers=world.headers("OUT")).json()["account_kind"] == "account"
    assert client.get("/api/v1/users/me", headers=world.headers("PRF")).json()["account_kind"] == "profile"
    r = client.post("/api/v1/users", json={"display_name": "Teacher T"}, headers=world.headers("T"))
    assert r.status_code == 200 and r.json()["account_kind"] == "account"


def test_students_cannot_use_account_level_routes(client, world):
    for method, path in (("DELETE", "/api/v1/users/me"), ("GET", "/api/v1/users/me/export"),
                         ("POST", "/api/v1/users/me/reconsent"), ("GET", "/api/v1/family/profiles")):
        r = client.request(method, path, headers=world.headers("S"))
        assert r.status_code == 403 and r.json()["detail"]["error"] == "school_student_not_allowed"
