"""Students and classes (SC-201..SC-204, SC-209).

API-STU-*   create / list / update / archive / restore / delete / export, seat limit, DPA gate
API-CLS-*   classes, teachers, enrollments, join codes, login cards
DBI-IMP-*   CSV import dry run + commit (PERF-03: 2,000 rows)
INV-13b     deleting a student removes their data and Firebase login
"""
import time

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _url(w, path=""):
    return f"/api/v1/schools/{w.school_a['id']}{path}"


def _audit(db, school_id):
    return [r["action"] for r in f.fetch(db, "SELECT action FROM school_audit_log WHERE school_id = %s ORDER BY id",
                                         (school_id,))]


# ── API-STU ───────────────────────────────────────────────────────────────────

def test_api_stu_create_returns_secret_once(client, world, db):
    r = client.post(_url(world, "/students"), headers=world.headers("SA"), json={
        "display_name": "Ravi Kumar", "grade": 3, "external_ref": "R-17", "class_ids": [world.A1["id"]],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["uid"].startswith("stu_")
    assert body["secret_kind"] == "picture"            # grade ≤ 4 → picture password
    assert len(body["secret"]) == 3 and all(0 <= i < 16 for i in body["secret"])
    assert len(body["badge_token"]) >= 30
    assert body["classes"] == [{"id": world.A1["id"], "name": "6A"}]

    # never again: reads expose no secret or hash
    again = client.get(_url(world, f"/students/{body['uid']}"), headers=world.headers("SA")).json()
    assert "secret" not in again and "secret_hash" not in again and again["has_secret"] is True
    listed = client.get(_url(world, "/students?q=ravi"), headers=world.headers("T")).json()
    assert [s["uid"] for s in listed["students"]] == [body["uid"]]
    assert "secret_hash" not in str(listed)

    user = f.fetch(db, "SELECT profile_type, email, account_status, onboarding_done FROM users WHERE uid = %s",
                   (body["uid"],))
    assert user == [{"profile_type": "school_student", "email": None, "account_status": "active",
                     "onboarding_done": True}]
    consent = f.fetch(db, "SELECT action, method, details->>'school_id' AS sid FROM consent_events WHERE uid = %s",
                      (body["uid"],))
    assert consent == [{"action": "granted", "method": "school_authorization", "sid": world.school_a["id"]}]
    assert "student.created" in _audit(db, world.school_a["id"])


def test_api_stu_pin_for_older_students_and_explicit_kind(client, world):
    r = client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "Meera", "grade": 9})
    assert r.json()["secret_kind"] == "pin" and len(r.json()["secret"]) == 6 and r.json()["secret"].isdigit()
    r = client.post(_url(world, "/students"), headers=world.headers("SA"),
                    json={"display_name": "Kabir", "grade": 9, "secret_kind": "picture"})
    assert r.json()["secret_kind"] == "picture"


def test_api_stu_gates(client, world, db):
    # seats
    f.fetch(db, "UPDATE schools SET seat_limit = 4 WHERE id = %s", (world.school_a["id"],))  # 3 active already
    assert client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "A"}).status_code == 201
    r = client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "B"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "seat_limit_reached"
    # DPA
    f.fetch(db, "UPDATE schools SET seat_limit = 100, dpa_version = NULL WHERE id = %s", (world.school_a["id"],))
    r = client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "C"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "dpa_required"
    # teachers only when the school allows it
    f.fetch(db, "UPDATE schools SET dpa_version = '2026-10' WHERE id = %s", (world.school_a["id"],))
    r = client.post(_url(world, "/students"), headers=world.headers("T"), json={"display_name": "D"})
    assert r.status_code == 403
    f.fetch(db, """UPDATE schools SET settings = '{"teachers_can_create_students": true}' WHERE id = %s""",
            (world.school_a["id"],))
    r = client.post(_url(world, "/students"), headers=world.headers("T"),
                    json={"display_name": "D", "class_ids": [world.A1["id"]]})
    assert r.status_code == 201
    # …but only into their own classes
    r = client.post(_url(world, "/students"), headers=world.headers("T"),
                    json={"display_name": "E", "class_ids": [world.A2["id"]]})
    assert r.status_code == 403
    # another school's class is invisible
    r = client.post(_url(world, "/students"), headers=world.headers("SA"),
                    json={"display_name": "F", "class_ids": [world.B1["id"]]})
    assert r.status_code == 404


def test_api_stu_external_ref_unique(client, world):
    client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "A", "external_ref": "7"})
    r = client.post(_url(world, "/students"), headers=world.headers("SA"), json={"display_name": "B", "external_ref": "7"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "external_ref_taken"


def test_api_stu_reset_secret_and_badge(client, world, db):
    f.fetch(db, "UPDATE school_students SET failed_attempts = 3, locked_until = now() + interval '5 minutes' "
                "WHERE uid = %s", (world.S,))
    r = client.post(_url(world, f"/students/{world.S}/reset-secret"), headers=world.headers("T"),
                    json={"secret_kind": "pin"})
    assert r.status_code == 200 and r.json()["secret_kind"] == "pin" and len(r.json()["secret"]) == 6
    row = f.fetch(db, "SELECT failed_attempts, locked_until, secret_hash IS NOT NULL AS has FROM school_students "
                      "WHERE uid = %s", (world.S,))[0]
    assert row == {"failed_attempts": 0, "locked_until": None, "has": True}
    r = client.post(_url(world, f"/students/{world.S}/rotate-badge"), headers=world.headers("T"))
    assert r.status_code == 200 and len(r.json()["badge_token"]) >= 30
    # T2 doesn't teach S
    assert client.post(_url(world, f"/students/{world.S}/reset-secret"), headers=world.headers("T2"),
                       json={}).status_code == 403


def test_api_stu_archive_restore(client, world, db):
    r = client.post(_url(world, "/students/archive"), headers=world.headers("SA"),
                    json={"student_uids": [world.S, world.S2]})
    assert r.json() == {"changed": 2}
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 404
    listed = client.get(_url(world, "/students?status=archived"), headers=world.headers("SA")).json()
    assert {s["uid"] for s in listed["students"]} == {world.S, world.S2}
    f.fetch(db, "UPDATE schools SET seat_limit = 1 WHERE id = %s", (world.school_a["id"],))
    r = client.post(_url(world, f"/students/{world.S}/restore"), headers=world.headers("SA"))
    assert r.status_code == 409 and r.json()["detail"]["error"] == "seat_limit_reached"
    f.fetch(db, "UPDATE schools SET seat_limit = 100 WHERE id = %s", (world.school_a["id"],))
    assert client.post(_url(world, f"/students/{world.S}/restore"), headers=world.headers("SA")).json() == {"changed": 1}
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 200


def test_inv13b_delete_student_removes_everything(client, world, db, firebase_deletes):
    step = f.step_ids(db, world.C1)[0]
    f.fetch(db, "INSERT INTO user_progress (uid, journey_id, step_id) VALUES (%s, %s, %s)", (world.S, world.C1, step))
    r = client.delete(_url(world, f"/students/{world.S}"), headers=world.headers("SA"))
    assert r.status_code == 204
    for table, col in (("users", "uid"), ("school_students", "uid"), ("class_enrollments", "student_uid"),
                       ("user_progress", "uid")):
        assert f.fetch(db, f"SELECT 1 FROM {table} WHERE {col} = %s", (world.S,)) == [], table
    firebase_deletes.assert_awaited_once_with(world.S)
    # consent proof survives, pseudonymised
    assert f.fetch(db, "SELECT 1 FROM consent_events WHERE uid = %s", (world.S,)) == []
    assert len(f.fetch(db, "SELECT 1 FROM consent_events WHERE method = 'school_deletion'")) == 1
    assert "student.deleted" in _audit(db, world.school_a["id"])
    # the course and everyone else are untouched
    assert len(f.fetch(db, "SELECT 1 FROM step_content WHERE journey_id = %s", (world.C1,))) == 2


def test_api_stu_export(client, world):
    r = client.get(_url(world, f"/students/{world.S}/export"), headers=world.headers("SA"))
    assert r.status_code == 200
    assert r.json()["student"]["uid"] == world.S and r.json()["data"]["user"]["uid"] == world.S


# ── API-CLS ───────────────────────────────────────────────────────────────────

def test_api_cls_create_list_detail(client, world, db):
    r = client.post(_url(world, "/classes"), headers=world.headers("T2"), json={"name": "7B Maths", "grade": 7})
    assert r.status_code == 201
    cls = r.json()
    assert cls["is_mine"] and len(cls["join_code"]) == 8 and cls["can_manage"]
    assert [t["uid"] for t in cls["teachers"]] == [world.T2] and cls["students"] == []
    listed = client.get(_url(world, "/classes"), headers=world.headers("T")).json()["classes"]
    assert {c["name"]: c["is_mine"] for c in listed} == {"6A": True, "6B": False, "7B Maths": False}
    a1 = next(c for c in listed if c["name"] == "6A")
    assert a1["student_count"] == 1   # SX's enrollment was removed


def test_api_cls_manage(client, world, db):
    a1 = world.A1["id"]
    h = world.headers("T")
    assert client.patch(_url(world, f"/classes/{a1}"), headers=h, json={"subject": "Science"}).json()["subject"] == "Science"
    # teachers: only active staff of this school
    assert client.post(_url(world, f"/classes/{a1}/teachers"), headers=h, json={"uid": world.XA}).status_code == 404
    assert client.post(_url(world, f"/classes/{a1}/teachers"), headers=h, json={"uid": world.T2}).status_code == 200
    # students: only this school's, active
    assert client.post(_url(world, f"/classes/{a1}/students"), headers=h,
                       json={"student_uids": [world.XS]}).status_code == 404
    detail = client.post(_url(world, f"/classes/{a1}/students"), headers=h,
                         json={"student_uids": [world.S2, world.SX]}).json()
    assert {s["uid"] for s in detail["students"]} == {world.S, world.S2, world.SX}
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("SX")).status_code == 200
    assert client.delete(_url(world, f"/classes/{a1}/students/{world.SX}"), headers=h).status_code == 204
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("SX")).status_code == 404
    # join code rotation
    old = world.A1["join_code"]
    new = client.post(_url(world, f"/classes/{a1}/rotate-code"), headers=h).json()["join_code"]
    assert new != old
    assert client.get(f"/api/v1/school-login/classes/{old}").status_code == 404
    assert client.get(f"/api/v1/school-login/classes/{new}").status_code == 200
    # archive hides the course from the class
    assert client.delete(_url(world, f"/classes/{a1}"), headers=h).status_code == 204
    assert client.get(f"/api/v1/journeys/{world.C1}", headers=world.headers("S")).status_code == 404
    assert client.post(_url(world, f"/classes/{a1}/students"), headers=h,
                       json={"student_uids": [world.S2]}).status_code == 409


def test_api_cls_login_cards(client, world, db):
    a1 = world.A1["id"]
    first = client.post(_url(world, f"/classes/{a1}/login-cards"), headers=world.headers("T"),
                        json={"reset": False}).json()
    assert first["class"]["join_code"] == world.A1["join_code"] and first["school_name"] == "School A"
    [card] = first["cards"]                     # only S is active in A1
    assert card["uid"] == world.S and card["secret"] is not None and card["badge_token"]
    # without reset, a student who already has a secret gets a card without one
    second = client.post(_url(world, f"/classes/{a1}/login-cards"), headers=world.headers("T"),
                         json={"reset": False}).json()
    assert second["cards"][0]["secret"] is None
    # reset issues new ones
    third = client.post(_url(world, f"/classes/{a1}/login-cards"), headers=world.headers("T"), json={}).json()
    assert third["cards"][0]["secret"] is not None and third["cards"][0]["badge_token"] != card["badge_token"]
    r = client.post(_url(world, f"/classes/{a1}/login-cards"), headers=world.headers("T"),
                    json={"student_uids": [world.S2]})
    assert r.status_code == 404


# ── DBI-IMP: CSV import ───────────────────────────────────────────────────────

CSV = """Name,Grade,Roll No,Class,Sign-in
Asha Kumari,5,R1,6A,
Ben Lee,6th,R2,7C,pin
Chen Ma,KG,,7C,
"""


def test_dbi_imp_dry_run_writes_nothing(client, world, db):
    before = len(f.fetch(db, "SELECT 1 FROM school_students"))
    r = client.post(_url(world, "/students/import?dry_run=true"), headers=world.headers("SA"), json={"csv": CSV})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["summary"]["create"] == 3 and report["summary"]["new_classes"] == ["7C"]
    assert [row["grade"] for row in report["rows"]] == [5, 6, 0]
    assert len(f.fetch(db, "SELECT 1 FROM school_students")) == before


def test_dbi_imp_commit_and_idempotent_on_roll_number(client, world, db):
    r = client.post(_url(world, "/students/import?dry_run=false"), headers=world.headers("SA"), json={"csv": CSV})
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["created_classes"] == 1
    rows = f.fetch(db, """
        SELECT s.display_name, s.grade, s.secret_kind, s.secret_hash IS NULL AS no_secret,
               (SELECT string_agg(c.name, ',') FROM class_enrollments e JOIN classes c ON c.id = e.class_id
                 WHERE e.student_uid = s.uid AND e.removed_at IS NULL) AS classes
          FROM school_students s WHERE s.school_id = %s AND s.display_name IN ('Asha Kumari', 'Ben Lee', 'Chen Ma')
         ORDER BY s.display_name
    """, (world.school_a["id"],))
    assert rows == [
        {"display_name": "Asha Kumari", "grade": 5, "secret_kind": "pin", "no_secret": True, "classes": "6A"},
        {"display_name": "Ben Lee", "grade": 6, "secret_kind": "pin", "no_secret": True, "classes": "7C"},
        {"display_name": "Chen Ma", "grade": 0, "secret_kind": "picture", "no_secret": True, "classes": "7C"},
    ]
    # re-import with a corrected name: R1 updates, no duplicate
    again = CSV.replace("Asha Kumari,5", "Asha K Rao,5")
    r = client.post(_url(world, "/students/import?dry_run=false"), headers=world.headers("SA"), json={"csv": again})
    summary = r.json()["summary"]
    assert summary["update"] == 2 and summary["create"] == 1   # Chen has no roll number → created again
    assert f.fetch(db, "SELECT display_name FROM school_students WHERE external_ref = 'R1'") == [{"display_name": "Asha K Rao"}]
    assert "students.imported" in _audit(db, world.school_a["id"])


def test_dbi_imp_errors_block_commit(client, world, db):
    bad = "Name,Grade,Roll No\nGood,3,X1\n,4,X2\nDup,15,X1\n"
    report = client.post(_url(world, "/students/import"), headers=world.headers("SA"), json={"csv": bad}).json()
    errors = {row["line"]: row["errors"] for row in report["rows"]}
    assert errors[2] == [] and errors[3] == ["name is missing"]
    assert "grade must be a number from 0 (KG) to 12" in errors[4] and "roll number repeats line 2" in errors[4]
    r = client.post(_url(world, "/students/import?dry_run=false"), headers=world.headers("SA"), json={"csv": bad})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "import_has_errors"
    assert f.fetch(db, "SELECT 1 FROM school_students WHERE external_ref = 'X1'") == []
    r = client.post(_url(world, "/students/import"), headers=world.headers("SA"), json={"csv": "grade\n3\n"})
    assert r.json()["errors"] and "name" in r.json()["errors"][0]


def test_dbi_imp_seat_limit(client, world, db):
    f.fetch(db, "UPDATE schools SET seat_limit = 4 WHERE id = %s", (world.school_a["id"],))
    report = client.post(_url(world, "/students/import"), headers=world.headers("SA"), json={"csv": CSV}).json()
    assert report["errors"] == ["This adds 3 students but the school has 1 seats left."]


def test_perf03_two_thousand_rows(client, world, db):
    f.fetch(db, "UPDATE schools SET seat_limit = 5000 WHERE id = %s", (world.school_a["id"],))
    csv_text = "name,grade,roll,class\n" + "".join(f"Student {i},{i % 12},P{i},Class {i % 40}\n" for i in range(2000))
    started = time.monotonic()
    r = client.post(_url(world, "/students/import?dry_run=false"), headers=world.headers("SA"), json={"csv": csv_text})
    elapsed = time.monotonic() - started
    assert r.status_code == 200, r.text[:500]
    assert r.json()["summary"]["create"] == 2000 and r.json()["summary"]["created_classes"] == 40
    assert elapsed < 30, f"import took {elapsed:.1f}s"
