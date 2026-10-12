"""The authorization matrix as data (TESTING.md §4).

One Case per route. `expect` maps persona → outcome; personas not listed get
the defaults of the case's `kind`. Outcomes:
  "ok"       any 2xx
  401        no token
  404        hidden (cross-tenant, not a member, unknown object)
  "role"     403 school_role_required
  "student"  403 school_student_not_allowed (route allowlist)
  "profile"  403 parent_profile_required (family-profile header on an account route)
  "admin"    403 ECALT admin required
  "mismatch" 403 invite_email_mismatch

AUTHZ-COV (test_authz_matrix.py) fails when a /schools, /school-invites,
/school-login, /school-student or /admin/schools route has no Case here.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from tests.factories import schools as f
from tests.schools import identity

PERSONAS = ["ANON", "OUT", "PRF", "SA", "T", "T2", "S", "S2", "SX", "XA", "XS", "ADM"]
STUDENTS = ("S", "S2", "SX", "XS")

_KIND_DEFAULTS = {
    # any active member of school A
    "member": {"ANON": 401, "OUT": 404, "PRF": "profile", "SA": "ok", "T": "ok", "T2": "ok",
               "XA": 404, "ADM": 404, **{s: "student" for s in STUDENTS}},
    # owner/admin of school A
    "school_admin": {"ANON": 401, "OUT": 404, "PRF": "profile", "SA": "ok", "T": "role", "T2": "role",
                     "XA": 404, "ADM": 404, **{s: "student" for s in STUDENTS}},
    # owner of school A
    "owner": {"ANON": 401, "OUT": 404, "PRF": "profile", "SA": "ok", "T": "role", "T2": "role",
              "XA": 404, "ADM": 404, **{s: "student" for s in STUDENTS}},
    # any signed-in adult account
    "account": {"ANON": 401, "OUT": "ok", "PRF": "profile", "SA": "ok", "T": "ok", "T2": "ok",
                "XA": "ok", "ADM": "ok", **{s: "student" for s in STUDENTS}},
    # no identity at all
    "public": {p: "ok" for p in PERSONAS},
    # ECALT admin
    "ecalt_admin": {"ANON": 401, "OUT": "admin", "PRF": "admin", "SA": "admin", "T": "admin", "T2": "admin",
                    "XA": "admin", "ADM": "ok", **{s: "student" for s in STUDENTS}},
}


@dataclass
class Case:
    method: str
    template: str                      # route template as in app.routes
    kind: str
    path: Callable                     # (world, db) -> concrete path
    body: Optional[Callable] = None    # (world, db) -> json body
    expect: dict = field(default_factory=dict)

    def outcome(self, persona: str):
        return {**_KIND_DEFAULTS[self.kind], **self.expect}[persona]


def _sid(w):
    return w.school_a["id"]


def _open_invite(w, db) -> str:
    rows = f.fetch(
        db,
        """
        INSERT INTO school_invites (school_id, email, role, token_hash, expires_at)
        VALUES (%s, 'pending@school.example', 'teacher', md5(random()::text), now() + interval '1 day')
        RETURNING id::text
        """,
        (w.school_a["id"],),
    )
    return rows[0]["id"]


def _invite_token_for_out(w, db) -> dict:
    """An invite to OUT's verified email — only OUT may accept it."""
    from app.services.school_service import create_invite
    email = f.fetch(db, "SELECT email FROM users WHERE uid = %s", (w.OUT,))[0]["email"]
    identity.register(w.OUT, email=email, email_verified=True)
    for persona in ("SA", "T", "T2", "XA", "ADM", "PARENT"):
        uid = getattr(w, persona)
        identity.register(uid, email=f"{persona.lower()}@someone.example", email_verified=True)
    _, token, _ = create_invite(w.school_a["id"], w.SA, "owner", email, "teacher")
    return {"token": token}


MATRIX: list[Case] = [
    Case("GET", "/api/v1/schools/mine", "account", lambda w, db: "/api/v1/schools/mine"),
    Case("GET", "/api/v1/schools/{school_id}", "member", lambda w, db: f"/api/v1/schools/{_sid(w)}"),
    Case("PATCH", "/api/v1/schools/{school_id}", "school_admin", lambda w, db: f"/api/v1/schools/{_sid(w)}",
         body=lambda w, db: {"settings": {"login_roster_visible": False}}),
    Case("POST", "/api/v1/schools/{school_id}/dpa/accept", "owner",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/dpa/accept", body=lambda w, db: {"dpa_version": "2026-10"}),
    Case("GET", "/api/v1/schools/{school_id}/staff", "member", lambda w, db: f"/api/v1/schools/{_sid(w)}/staff"),
    Case("POST", "/api/v1/schools/{school_id}/staff/invites", "school_admin",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/staff/invites",
         body=lambda w, db: {"email": "new@school.example", "role": "teacher"}),
    Case("DELETE", "/api/v1/schools/{school_id}/staff/invites/{invite_id}", "school_admin",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/staff/invites/{_open_invite(w, db)}"),
    Case("PATCH", "/api/v1/schools/{school_id}/staff/{member_uid}", "school_admin",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/staff/{w.T2}", body=lambda w, db: {"role": "admin"}),
    # Removing T2: admins may, T may not, T2 may (leaving).
    Case("DELETE", "/api/v1/schools/{school_id}/staff/{member_uid}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/staff/{w.T2}", expect={"T": "role"}),
    Case("POST", "/api/v1/school-invites/preview", "public", lambda w, db: "/api/v1/school-invites/preview",
         body=_invite_token_for_out),
    Case("POST", "/api/v1/school-invites/accept", "account", lambda w, db: "/api/v1/school-invites/accept",
         body=_invite_token_for_out,
         expect={"SA": "mismatch", "T": "mismatch", "T2": "mismatch", "XA": "mismatch", "ADM": "mismatch"}),
    Case("POST", "/api/v1/admin/schools", "ecalt_admin", lambda w, db: "/api/v1/admin/schools",
         body=lambda w, db: {"name": "New School"}),
    Case("GET", "/api/v1/admin/schools", "ecalt_admin", lambda w, db: "/api/v1/admin/schools"),
    Case("GET", "/api/v1/admin/schools/{school_id}", "ecalt_admin",
         lambda w, db: f"/api/v1/admin/schools/{_sid(w)}"),
    Case("PATCH", "/api/v1/admin/schools/{school_id}", "ecalt_admin",
         lambda w, db: f"/api/v1/admin/schools/{_sid(w)}", body=lambda w, db: {"seat_limit": 10}),
    Case("POST", "/api/v1/admin/schools/{school_id}/owner-invite", "ecalt_admin",
         lambda w, db: f"/api/v1/admin/schools/{_sid(w)}/owner-invite",
         body=lambda w, db: {"email": "owner2@school.example"}),
]
