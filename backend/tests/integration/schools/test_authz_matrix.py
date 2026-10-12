"""AUTHZ-* (generated from authz_matrix.MATRIX), AUTHZ-COV, and the ISO IDOR
sweep for M1 staff routes (TESTING.md §4)."""
import hashlib

import pytest
from fastapi.routing import APIRoute

from tests.factories import schools as f
from tests.integration.schools.authz_matrix import MATRIX, PERSONAS

pytestmark = pytest.mark.schools_db

SCHOOL_PREFIXES = ("/api/v1/schools", "/api/v1/school-invites", "/api/v1/school-login",
                   "/api/v1/school-student", "/api/v1/admin/schools")

_ERRORS = {
    "role": "school_role_required",
    "student": "school_student_not_allowed",
    "profile": "parent_profile_required",
    "mismatch": "invite_email_mismatch",
}


def test_authz_cov_every_school_route_has_a_matrix_row():
    from app.main import app
    routes = {(m, r.path_format) for r in app.routes if isinstance(r, APIRoute)
              for m in r.methods if r.path_format.startswith(SCHOOL_PREFIXES)}
    covered = {(c.method, c.template) for c in MATRIX}
    assert routes - covered == set(), f"school routes missing from MATRIX: {sorted(routes - covered)}"
    assert covered - routes == set(), f"MATRIX rows for routes that don't exist: {sorted(covered - routes)}"


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("case", MATRIX, ids=[f"{c.method} {c.template}" for c in MATRIX])
def test_authz(client, world, db, case, persona):
    path = case.path(world, db)
    body = case.body(world, db) if case.body else None
    r = client.request(case.method, path, json=body, headers=world.headers(persona))
    expected = case.outcome(persona)

    if expected == "ok":
        assert 200 <= r.status_code < 300, r.text
    elif expected in (401, 404):
        assert r.status_code == expected, r.text
    else:
        assert r.status_code == 403, r.text
        if expected == "admin":
            assert r.json()["detail"] == "Admin access required"
        else:
            assert r.json()["detail"]["error"] == _ERRORS[expected], r.text


# ── ISO: IDOR sweep — school A's admin aims at school B's objects ─────────────

def _digest(db, school_id) -> str:
    rows = [
        f.fetch(db, "SELECT * FROM schools WHERE id = %s", (school_id,)),
        f.fetch(db, "SELECT * FROM school_members WHERE school_id = %s ORDER BY uid", (school_id,)),
        f.fetch(db, "SELECT * FROM school_invites WHERE school_id = %s ORDER BY id", (school_id,)),
    ]
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def test_iso_staff_routes_never_reach_another_school(client, world, db):
    a, b = world.school_a["id"], world.school_b["id"]
    invite_b = f.fetch(db, """
        INSERT INTO school_invites (school_id, email, role, token_hash, expires_at)
        VALUES (%s, 'b@b.example', 'teacher', 'hash-b', now() + interval '1 day') RETURNING id::text
    """, (b,))[0]["id"]
    before = _digest(db, b)
    h = world.headers("SA")

    calls = [
        ("GET", f"/api/v1/schools/{b}", None),
        ("PATCH", f"/api/v1/schools/{b}", {"name": "pwned"}),
        ("POST", f"/api/v1/schools/{b}/dpa/accept", {"dpa_version": "2026-10"}),
        ("GET", f"/api/v1/schools/{b}/staff", None),
        ("POST", f"/api/v1/schools/{b}/staff/invites", {"email": "x@x.example"}),
        # school A in the path, school B's objects in the rest of it
        ("DELETE", f"/api/v1/schools/{a}/staff/invites/{invite_b}", None),
        ("PATCH", f"/api/v1/schools/{a}/staff/{world.XA}", {"role": "teacher"}),
        ("DELETE", f"/api/v1/schools/{a}/staff/{world.XA}", None),
    ]
    for method, path, body in calls:
        r = client.request(method, path, json=body, headers=h)
        assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"
    assert _digest(db, b) == before


def test_iso_malformed_ids_are_404_not_500(client, world):
    h = world.headers("SA")
    for path in ("/api/v1/schools/not-a-uuid", "/api/v1/schools/not-a-uuid/staff",
                 f"/api/v1/schools/{world.school_a['id']}/staff/invites/not-a-uuid"):
        method = "DELETE" if "invites" in path else "GET"
        assert client.request(method, path, headers=h).status_code == 404
