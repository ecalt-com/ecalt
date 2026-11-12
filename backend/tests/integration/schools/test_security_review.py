"""SC-801 pre-launch security review (#8) — the tests that came out of it.

- ISO sweep for the M6 (update/proposals) and M7 (analytics, transcripts)
  routes, plus school-B ids smuggled in request bodies.
- Malformed-id fuzz: every school route with a path parameter, fed garbage,
  answers 4xx — never a 500 from a database cast.
- Stored XSS: teacher-written step bodies are shown to students, and the
  renderer injects an inline <svg> as HTML. Unsafe SVG / scripts are dropped
  on write and again at publish.
- D4: tutor transcripts are visible to the class's own teachers and admins
  only (matrix rows carry T2 → 403).
- Upload integrity: extraction parses only the bytes `complete` verified
  (the signed upload URL allows overwrites) and never pulls an oversized
  object into memory.
- Untrusted document headings can't carry HTML or links into step titles.
"""
import hashlib
import json
import re

import pytest

from app.services import school_course_update_service as updates  # noqa: F401 - registers 'propose_update'
from app.services import school_ingest_service  # noqa: F401 - registers 'extract'
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider
from tests.integration.schools.authz_matrix import MATRIX

pytestmark = pytest.mark.schools_db

_SUPPORTED = json.dumps({"supported": True, "flags": []})
_EVIL_SVG = '<svg viewBox="0 0 10 10"><image href="x" onerror="alert(1)"/></svg>'
_SAFE_SVG = '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'


def _sid(w):
    return w.school_a["id"]


# ── ISO: M6 / M7 routes and body-borne ids ────────────────────────────────────

def _digest_b(db, school_id) -> str:
    rows = [
        f.fetch(db, "SELECT id, status, op FROM course_change_proposals WHERE journey_id IN "
                    "(SELECT journey_id FROM school_courses WHERE school_id = %s) ORDER BY id", (school_id,)),
        f.fetch(db, "SELECT id, state, version, revision FROM course_versions WHERE journey_id IN "
                    "(SELECT journey_id FROM school_courses WHERE school_id = %s) ORDER BY id", (school_id,)),
        f.fetch(db, "SELECT journey_id, status, published_version FROM school_courses WHERE school_id = %s "
                    "ORDER BY journey_id", (school_id,)),
        f.fetch(db, "SELECT id, kind, status FROM school_jobs WHERE school_id = %s ORDER BY id", (school_id,)),
    ]
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def test_iso_update_and_analytics_routes_never_reach_another_school(client, world, db):
    a, b = world.school_a["id"], world.school_b["id"]
    pub_a = f.make_published_course(db, world.school_a)
    pub_b = f.make_published_course(db, world.school_b)
    doc_a = f.make_document(db, world.school_a, status="ready")["id"]
    doc_b = f.make_document(db, world.school_b, status="ready")["id"]
    prop_b = f.make_update_proposal(db, world.school_b, journey_id=pub_b, op="modify",
                                    step_id="s1", status="accepted")
    conv_xs = f.fetch(db, "INSERT INTO conversations (uid) VALUES (%s) RETURNING id::text AS id",
                      (world.XS,))[0]["id"]
    before = _digest_b(db, b)
    h = world.headers("SA")
    B1 = world.B1["id"]
    A1 = world.A1["id"]

    calls = [
        # M6: school B's course / proposals through school A's routes
        ("POST", f"/api/v1/schools/{a}/courses/{pub_b}/update", {"document_id": doc_a, "mode": "revise"}),
        ("GET", f"/api/v1/schools/{a}/courses/{pub_b}/proposals", None),
        ("POST", f"/api/v1/schools/{a}/courses/{pub_b}/proposals/apply", {}),
        ("POST", f"/api/v1/schools/{a}/courses/{pub_b}/proposals/{prop_b}/decide", {"decision": "reject"}),
        # school A's own course, school B's proposal / document
        ("POST", f"/api/v1/schools/{a}/courses/{pub_a}/proposals/{prop_b}/decide", {"decision": "reject"}),
        ("POST", f"/api/v1/schools/{a}/courses/{pub_a}/update", {"document_id": doc_b, "mode": "revise"}),
        # school B's document in a new course's body
        ("POST", f"/api/v1/schools/{a}/courses", {"title": "x", "document_ids": [doc_b]}),
        # M7: school B's class / student through school A's routes
        ("GET", f"/api/v1/schools/{a}/classes/{B1}/progress", None),
        ("GET", f"/api/v1/schools/{a}/classes/{B1}/progress/export", None),
        ("GET", f"/api/v1/schools/{a}/classes/{B1}/students/{world.XS}/progress", None),
        ("GET", f"/api/v1/schools/{a}/classes/{B1}/students/{world.XS}/transcripts", None),
        ("GET", f"/api/v1/schools/{a}/classes/{B1}/students/{world.XS}/transcripts/{conv_xs}", None),
        # school A's class, school B's student / conversation
        ("GET", f"/api/v1/schools/{a}/classes/{A1}/students/{world.XS}/progress", None),
        ("GET", f"/api/v1/schools/{a}/classes/{A1}/students/{world.XS}/transcripts", None),
        ("GET", f"/api/v1/schools/{a}/classes/{A1}/students/{world.S}/transcripts/{conv_xs}", None),
    ]
    for method, path, body in calls:
        r = client.request(method, path, json=body, headers=h)
        assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"
    assert _digest_b(db, b) == before


# ── Malformed ids never 500 ───────────────────────────────────────────────────

_PARAM_RE = re.compile(r"{(\w+)}")
_PERSONA_FOR_KIND = {"ecalt_admin": "ADM", "public": "ANON", "public_401": "ANON", "account": "OUT",
                     "any_authed": "SA"}
_GARBAGE = ["not-a-uuid", "1' OR '1'='1", "00000000-0000-0000-0000-00000000000g", "%00"]


@pytest.mark.parametrize("case", [c for c in MATRIX if set(_PARAM_RE.findall(c.template)) - {"school_id"}],
                         ids=lambda c: f"{c.method} {c.template}")
def test_malformed_path_ids_are_4xx_never_500(client, world, db, case):
    persona = _PERSONA_FOR_KIND.get(case.kind, "SA")
    body = case.body(world, db) if case.body else None
    for junk in _GARBAGE:
        def fill(m, junk=junk):
            return _sid(world) if m.group(1) == "school_id" else junk
        path = _PARAM_RE.sub(fill, case.template)
        r = client.request(case.method, path, json=body, headers=world.headers(persona))
        assert r.status_code < 500, f"{case.method} {path}: {r.status_code} {r.text}"


# ── Stored XSS: teacher bodies → students ─────────────────────────────────────

def _patch_step(client, world, jid, body_md, step="s1"):
    return client.patch(f"/api/v1/schools/{_sid(world)}/courses/{jid}/draft/steps/{step}",
                        json={"body_md": body_md}, headers=world.headers("T"))


def _draft_step(client, world, jid, step_id):
    d = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()["draft"]
    return next(s for s in d["steps"] if s["id"] == step_id)


def test_teacher_body_drops_unsafe_svg_and_scripts(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = _patch_step(client, world, jid, f"Intro {_EVIL_SVG} middle <script>alert(2)</script> end")
    assert r.status_code == 200, r.text
    body = _draft_step(client, world, jid, "s1")["body_md"]
    assert "onerror" not in body and "<script" not in body and "<svg" not in body
    assert "Intro" in body and "end" in body


def test_teacher_body_keeps_a_safe_diagram(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    assert _patch_step(client, world, jid, f"Look:\n\n{_SAFE_SVG}").status_code == 200
    assert _SAFE_SVG in _draft_step(client, world, jid, "s1")["body_md"]


def test_teacher_added_step_body_is_sanitized(client, world, db):
    jid = f.make_outlined_draft(db, world.school_a)
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/draft/steps",
                    json={"title": "Extra", "body_md": f"Hi {_EVIL_SVG}"}, headers=world.headers("T"))
    assert r.status_code in (200, 201), r.text
    added = [s for s in r.json()["draft"]["steps"] if s["title"] == "Extra"][0]
    assert "onerror" not in (added["body_md"] or "")


def test_publish_strips_unsafe_svg_already_in_a_draft(client, world, db):
    """A body stored before the fix (or restored from an old version) is
    cleaned at the door to students."""
    jid = f.make_built_draft(db, world.school_a)
    row = f.fetch(db, "SELECT id, steps FROM course_versions WHERE journey_id = %s AND state = 'draft'", (jid,))[0]
    steps = row["steps"]
    steps[0]["body_md"] = f"Legacy body {_EVIL_SVG}"
    f.fetch(db, "UPDATE course_versions SET steps = %s::jsonb WHERE id = %s RETURNING id",
            (json.dumps(steps), row["id"]))
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/publish", json={}, headers=world.headers("SA"))
    assert r.status_code == 200, r.text
    content = f.fetch(db, "SELECT content FROM step_content WHERE journey_id = %s AND step_id = %s",
                      (jid, steps[0]["id"]))[0]["content"]
    assert "onerror" not in content and "Legacy body" in content


# ── D4 transcripts ────────────────────────────────────────────────────────────

def test_transcript_with_malformed_conversation_id_is_404(client, world):
    r = client.get(f"/api/v1/schools/{_sid(world)}/classes/{world.A1['id']}/students/{world.S}/transcripts/not-a-uuid",
                   headers=world.headers("SA"))
    assert r.status_code == 404


def test_teacher_of_another_class_cannot_read_transcripts(client, world, db):
    conv = f.fetch(db, "INSERT INTO conversations (uid) VALUES (%s) RETURNING id::text AS id", (world.S,))[0]["id"]
    base = f"/api/v1/schools/{_sid(world)}/classes/{world.A1['id']}/students/{world.S}/transcripts"
    for path in (base, f"{base}/{conv}"):
        r = client.get(path, headers=world.headers("T2"))
        assert r.status_code == 403 and r.json()["detail"]["error"] == "school_role_required"
    # …and nothing was audited for the refused read
    assert not f.fetch(db, "SELECT 1 FROM school_audit_log WHERE action = 'student.transcript_viewed' AND actor_uid = %s",
                       (world.T2,))


# ── Upload integrity ──────────────────────────────────────────────────────────

def _uploaded_doc(db, school, verified: bytes):
    doc = f.make_document(db, school, filename="notes.pdf", status="uploaded")
    f.fetch(db, "UPDATE source_documents SET sha256 = %s WHERE id = %s RETURNING id",
            (hashlib.sha256(verified).hexdigest(), doc["id"]))
    return doc


def _status(db, doc_id):
    return f.fetch(db, "SELECT status, error_code FROM source_documents WHERE id = %s", (doc_id,))[0]


def test_extract_refuses_a_file_swapped_after_verification(db, world, fake_storage):
    doc = _uploaded_doc(db, world.school_a, b"%PDF-1.4 the verified bytes")
    fake_storage.put(doc["storage_path"], b"%PDF-1.4 different bytes swapped in later")
    sj.enqueue(world.school_a["id"], "extract", {"document_id": doc["id"]})
    assert sj.process_one("w1") is True
    row = _status(db, doc["id"])
    assert row["status"] == "failed" and row["error_code"] == "changed_after_upload"
    assert not f.fetch(db, "SELECT 1 FROM document_chunks WHERE document_id = %s", (doc["id"],))


def test_extract_refuses_an_oversized_object(db, world, fake_storage, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SCHOOL_DOC_MAX_MB", 1)
    big = b"%PDF-1.4" + b"0" * (1024 * 1024 + 10)
    doc = _uploaded_doc(db, world.school_a, big)
    fake_storage.put(doc["storage_path"], big)
    sj.enqueue(world.school_a["id"], "extract", {"document_id": doc["id"]})
    assert sj.process_one("w1") is True
    assert _status(db, doc["id"])["error_code"] == "changed_after_upload"


# ── Untrusted headings → step titles (update path) ────────────────────────────

def _body_response(system, user):
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", user)]
    return json.dumps({"body_md": "## New\n\nGrounded text.", "citations": ids[:1] or [0],
                       "key_facts": ["a fact"]})


def test_update_add_titles_from_document_headings_are_sanitized(client, world, db, monkeypatch):
    (FakeProvider()
        .respond("school_step_content", _body_response)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    jid = f.make_published_course(db, world.school_a)
    doc = f.make_document(db, world.school_a, filename="evil.pdf", status="ready")
    heading = 'Volcanoes <img src=x onerror="alert(1)"> [click](https://evil.example)'
    f.fetch(db, """INSERT INTO document_chunks (document_id, ordinal, heading_path, text, char_count)
                   VALUES (%s, 0, %s, %s, 60) RETURNING id""",
            (doc["id"], [heading], "Volcanoes form when magma rises through the crust and erupts"))
    r = client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/update",
                    json={"document_id": doc["id"], "mode": "supplement"}, headers=world.headers("SA"))
    assert r.status_code == 200, r.text
    assert sj.process_one("w1") is True
    props = client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}/proposals",
                       headers=world.headers("SA")).json()["proposals"]
    add = next(p for p in props if p["op"] == "add")
    assert "<img" not in add["title"] and "evil.example" not in add["title"] and "onerror" not in add["title"]
    assert add["title"].startswith("Volcanoes")
