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
    # owner/admin, or a teacher when the school lets teachers manage students (off in the world)
    "manage_students": {"ANON": 401, "OUT": 404, "PRF": "profile", "SA": "ok", "T": "role", "T2": "role",
                        "XA": 404, "ADM": 404, **{s: "student" for s in STUDENTS}},
    # owner/admin, or a teacher of the class (T leads A1; T2 doesn't teach it)
    "class_staff": {"ANON": 401, "OUT": 404, "PRF": "profile", "SA": "ok", "T": "ok", "T2": "role",
                    "XA": 404, "ADM": 404, **{s: "student" for s in STUDENTS}},
    # student sign-in: no identity, a wrong secret / badge → 401 for everyone
    "public_401": {p: 401 for p in PERSONAS},
    # ECALT admin
    "ecalt_admin": {"ANON": 401, "OUT": "admin", "PRF": "admin", "SA": "admin", "T": "admin", "T2": "admin",
                    "XA": "admin", "ADM": "ok", **{s: "student" for s in STUDENTS}},
    # any signed-in caller, including school students (student home); anon → 401
    "any_authed": {p: ("ok" if p != "ANON" else 401) for p in PERSONAS},
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


def _a1_c1_assignment(w, db) -> str:
    """The active A1 → C1 assignment the world seeds (for PATCH/DELETE)."""
    return f.fetch(
        db,
        "SELECT id::text AS id FROM course_assignments "
        "WHERE class_id = %s AND journey_id = %s AND status = 'active'",
        (w.A1["id"], w.C1),
    )[0]["id"]


def _s_conversation(w, db) -> str:
    """A tutor conversation owned by student S (for the transcript-read route)."""
    return f.fetch(db, "INSERT INTO conversations (uid) VALUES (%s) RETURNING id::text AS id", (w.S,))[0]["id"]


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
    # ── M2: students ──
    Case("GET", "/api/v1/schools/{school_id}/students", "member", lambda w, db: f"/api/v1/schools/{_sid(w)}/students"),
    Case("POST", "/api/v1/schools/{school_id}/students", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students", body=lambda w, db: {"display_name": "New Kid", "grade": 3}),
    Case("POST", "/api/v1/schools/{school_id}/students/import", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/import",
         body=lambda w, db: {"csv": "name,grade\nNew Kid,3\n"}),
    Case("POST", "/api/v1/schools/{school_id}/students/archive", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/archive", body=lambda w, db: {"student_uids": [w.S2]}),
    Case("GET", "/api/v1/schools/{school_id}/students/{student_uid}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S}"),
    Case("PATCH", "/api/v1/schools/{school_id}/students/{student_uid}", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S}", body=lambda w, db: {"grade": 7}),
    Case("DELETE", "/api/v1/schools/{school_id}/students/{student_uid}", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S2}"),
    Case("POST", "/api/v1/schools/{school_id}/students/{student_uid}/reset-secret", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S}/reset-secret", body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/students/{student_uid}/rotate-badge", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S}/rotate-badge"),
    Case("POST", "/api/v1/schools/{school_id}/students/{student_uid}/archive", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S2}/archive"),
    Case("POST", "/api/v1/schools/{school_id}/students/{student_uid}/restore", "manage_students",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S2}/restore"),
    Case("GET", "/api/v1/schools/{school_id}/students/{student_uid}/export", "school_admin",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/students/{w.S}/export"),
    # ── M2: classes ──
    Case("GET", "/api/v1/schools/{school_id}/classes", "member", lambda w, db: f"/api/v1/schools/{_sid(w)}/classes"),
    Case("POST", "/api/v1/schools/{school_id}/classes", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes", body=lambda w, db: {"name": "7C", "grade": 7}),
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}"),
    Case("PATCH", "/api/v1/schools/{school_id}/classes/{class_id}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}", body=lambda w, db: {"subject": "Science"}),
    Case("DELETE", "/api/v1/schools/{school_id}/classes/{class_id}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}"),
    Case("POST", "/api/v1/schools/{school_id}/classes/{class_id}/teachers", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/teachers", body=lambda w, db: {"uid": w.T2}),
    # T may remove themselves from their own class
    Case("DELETE", "/api/v1/schools/{school_id}/classes/{class_id}/teachers/{uid}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/teachers/{w.T}"),
    Case("POST", "/api/v1/schools/{school_id}/classes/{class_id}/students", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/students",
         body=lambda w, db: {"student_uids": [w.S2]}),
    Case("DELETE", "/api/v1/schools/{school_id}/classes/{class_id}/students/{student_uid}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/students/{w.S}"),
    Case("POST", "/api/v1/schools/{school_id}/classes/{class_id}/rotate-code", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/rotate-code"),
    Case("POST", "/api/v1/schools/{school_id}/classes/{class_id}/login-cards", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/login-cards", body=lambda w, db: {}),
    # ── M5: course assignments ──
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/courses", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/courses"),
    Case("POST", "/api/v1/schools/{school_id}/classes/{class_id}/courses", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/courses",
         body=lambda w, db: {"journey_id": f.make_published_course(db, w.school_a)}),
    Case("PATCH", "/api/v1/schools/{school_id}/classes/{class_id}/courses/{assignment_id}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/courses/{_a1_c1_assignment(w, db)}",
         body=lambda w, db: {"tutor_enabled": False}),
    Case("DELETE", "/api/v1/schools/{school_id}/classes/{class_id}/courses/{assignment_id}", "class_staff",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/courses/{_a1_c1_assignment(w, db)}"),
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/progress", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/progress"),
    # ── M7: teacher analytics ──
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/students/{student_uid}/progress", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/students/{w.S}/progress"),
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/progress/export", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/progress/export"),
    Case("GET", "/api/v1/schools/{school_id}/usage", "school_admin",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/usage"),
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/students/{student_uid}/transcripts", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/students/{w.S}/transcripts"),
    Case("GET", "/api/v1/schools/{school_id}/classes/{class_id}/students/{student_uid}/transcripts/{conversation_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/classes/{w.A1['id']}/students/{w.S}/transcripts/{_s_conversation(w, db)}"),
    # ── M3: documents (any staff member) ──
    Case("POST", "/api/v1/schools/{school_id}/documents/upload-url", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/documents/upload-url",
         body=lambda w, db: {"filename": "notes.pdf", "size_bytes": 2048, "mime": "application/pdf"}),
    Case("POST", "/api/v1/schools/{school_id}/documents/{document_id}/complete", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/documents/{f.make_document(db, w.school_a, status='pending_upload')['id']}/complete"),
    Case("GET", "/api/v1/schools/{school_id}/documents", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/documents"),
    Case("GET", "/api/v1/schools/{school_id}/documents/{document_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/documents/{f.make_document(db, w.school_a)['id']}"),
    Case("DELETE", "/api/v1/schools/{school_id}/documents/{document_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/documents/{f.make_document(db, w.school_a)['id']}"),
    # ── M4: courses + jobs (any staff member) ──
    Case("GET", "/api/v1/schools/{school_id}/courses", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses"),
    Case("POST", "/api/v1/schools/{school_id}/courses", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses",
         body=lambda w, db: {"title": "New Course", "document_ids": [f.make_document(db, w.school_a, status="ready")["id"]]}),
    Case("GET", "/api/v1/schools/{school_id}/courses/{journey_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_course_draft(db, w.school_a)}"),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/estimate", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_course_draft(db, w.school_a)}/estimate"),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/outline", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_course_draft(db, w.school_a)}/outline", body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/build", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/build", body=lambda w, db: {}),
    Case("PATCH", "/api/v1/schools/{school_id}/courses/{journey_id}/draft", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/draft",
         body=lambda w, db: {"title": "Edited"}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/draft/steps", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/draft/steps",
         body=lambda w, db: {"title": "New step"}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/draft/steps/reorder", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/draft/steps/reorder",
         body=lambda w, db: {"order": ["s2", "s1"]}),
    Case("PATCH", "/api/v1/schools/{school_id}/courses/{journey_id}/draft/steps/{step_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/draft/steps/s1",
         body=lambda w, db: {"title": "Edited step"}),
    Case("DELETE", "/api/v1/schools/{school_id}/courses/{journey_id}/draft/steps/{step_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/draft/steps/s1"),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/draft/steps/{step_id}/regenerate", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_built_draft(db, w.school_a)}/draft/steps/s1/regenerate",
         body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/publish", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_built_draft(db, w.school_a)}/publish", body=lambda w, db: {}),
    Case("GET", "/api/v1/schools/{school_id}/courses/{journey_id}/versions", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_published_course(db, w.school_a)}/versions"),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/versions/{version}/restore", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_published_course(db, w.school_a)}/versions/1/restore", body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/duplicate", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/duplicate", body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/archive", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/archive", body=lambda w, db: {}),
    Case("POST", "/api/v1/schools/{school_id}/courses/{journey_id}/hero-image", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/courses/{f.make_outlined_draft(db, w.school_a)}/hero-image", body=lambda w, db: {}),
    Case("GET", "/api/v1/schools/{school_id}/jobs/{job_id}", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/jobs/{f.enqueue_job(db, w.school_a)}"),
    Case("POST", "/api/v1/schools/{school_id}/jobs/{job_id}/cancel", "member",
         lambda w, db: f"/api/v1/schools/{_sid(w)}/jobs/{f.enqueue_job(db, w.school_a)}/cancel", body=lambda w, db: {}),
    # ── M2: student sign-in (public) ──
    Case("GET", "/api/v1/school-login/classes/{code}", "public",
         lambda w, db: f"/api/v1/school-login/classes/{w.A1['join_code']}"),
    Case("POST", "/api/v1/school-login/sessions", "public_401", lambda w, db: "/api/v1/school-login/sessions",
         body=lambda w, db: {"class_code": w.A1["join_code"], "student_uid": w.S,
                             "secret": {"kind": "pin", "value": "000000"}}),
    Case("POST", "/api/v1/school-login/badge", "public_401", lambda w, db: "/api/v1/school-login/badge",
         body=lambda w, db: {"token": "not-a-real-badge-token-123"}),
    # ── M5: student home (any signed-in caller; students included) ──
    Case("GET", "/api/v1/school-student/home", "any_authed", lambda w, db: "/api/v1/school-student/home"),
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
