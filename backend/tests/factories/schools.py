"""Row factories for school DB tests (TESTING.md §3 "Factories").

Every function takes the autocommit connection from the `db` fixture and writes
straight to ecalt_test. Nothing here goes through the API — tests use these to
build state, then exercise the API.
"""
import json
import secrets
import uuid
from typing import Optional

import psycopg2.extras

_JOIN_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def make_user(conn, uid: Optional[str] = None, *, email: Optional[str] = None,
              display_name: Optional[str] = None, admin: bool = False,
              profile_type: str = "account", age_group: str = "adult",
              account_status: str = "active") -> str:
    uid = uid or f"user_{secrets.token_hex(6)}"
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO users (uid, email, display_name, is_admin, profile_type, age_group_flag,
                               account_status, birth_year, onboarding_done)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (uid, email if email is not None else (f"{uid}@example.test" if profile_type == "account" else None),
             display_name or uid, admin, profile_type, age_group, account_status,
             1985 if age_group == "adult" else 2012),
        )
    return uid


def make_school(conn, *, name: str = "Test School", status: str = "active", seats: int = 100,
                budget_cents: float = 10_000, dpa: bool = True, settings: Optional[dict] = None) -> dict:
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO schools (name, slug, status, seat_limit, monthly_ai_budget_cents, settings,
                                 dpa_version, dpa_accepted_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, CASE WHEN %s THEN now() END)
            RETURNING *
            """,
            (name, f"school-{secrets.token_hex(4)}", status, seats, budget_cents,
             json.dumps(settings or {}), "2026-10" if dpa else None, dpa),
        )
        row = dict(cur.fetchone())
    row["id"] = str(row["id"])
    return row


def make_staff(conn, school: dict, role: str = "teacher", uid: Optional[str] = None,
               email: Optional[str] = None, status: str = "active") -> str:
    uid = uid or make_user(conn, email=email)
    with _cur(conn) as cur:
        cur.execute(
            "INSERT INTO school_members (school_id, uid, role, status) VALUES (%s, %s, %s, %s)",
            (school["id"], uid, role, status),
        )
    return uid


def make_student(conn, school: dict, *, display_name: str = "Asha K", grade: int = 6,
                 status: str = "active", uid: Optional[str] = None, pin: Optional[str] = None,
                 picture: Optional[list] = None, badge: Optional[str] = None,
                 external_ref: Optional[str] = None) -> str:
    """pin='123456' or picture=[1, 2, 3] stores a hashed secret; badge stores a badge token."""
    from app.services.profile_service import hash_pin
    from app.services.school_student_service import hash_badge_token
    uid = uid or f"stu_{secrets.token_hex(8)}"
    make_user(conn, uid, email=None, display_name=display_name, profile_type="school_student",
              age_group="child")
    kind, secret_hash = "pin", None
    if pin is not None:
        secret_hash = hash_pin(f"pin:{pin}")
    elif picture is not None:
        kind, secret_hash = "picture", hash_pin("picture:" + "-".join(map(str, picture)))
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO school_students (uid, school_id, display_name, grade, status, secret_kind, secret_hash,
                                         badge_token_hash, external_ref)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (uid, school["id"], display_name, grade, status, kind, secret_hash,
             hash_badge_token(badge) if badge else None, external_ref),
        )
    return uid


def make_class(conn, school: dict, *, name: str = "6A Science", grade: int = 6,
               teachers: tuple = (), archived: bool = False) -> dict:
    """teachers: iterable of uid or (uid, 'lead'|'co')."""
    code = "".join(secrets.choice(_JOIN_ALPHABET) for _ in range(8))
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO classes (school_id, name, grade, join_code, archived_at)
            VALUES (%s, %s, %s, %s, CASE WHEN %s THEN now() END)
            RETURNING *
            """,
            (school["id"], name, grade, code, archived),
        )
        row = dict(cur.fetchone())
        row["id"] = str(row["id"])
        row["school_id"] = str(row["school_id"])
        for t in teachers:
            uid, role = (t, "lead") if isinstance(t, str) else t
            cur.execute(
                "INSERT INTO class_teachers (class_id, school_id, uid, role) VALUES (%s, %s, %s, %s)",
                (row["id"], school["id"], uid, role),
            )
    return row


def enroll(conn, cls: dict, student_uid: str, *, removed: bool = False) -> None:
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO class_enrollments (class_id, school_id, student_uid, removed_at)
            VALUES (%s, %s, %s, CASE WHEN %s THEN now() END)
            """,
            (cls["id"], cls["school_id"], student_uid, removed),
        )


def _steps(n: int, prefix: str) -> list[dict]:
    return [
        {"id": f"{prefix}-{i}", "title": f"Step {i}", "description": f"About step {i}",
         "type": "concept", "estimated_minutes": 10}
        for i in range(1, n + 1)
    ]


def make_course(conn, school: dict, creator: Optional[str], *, title: str = "Photosynthesis",
                published: bool = True, steps: int = 2, locked: bool = True,
                status: Optional[str] = None) -> str:
    """A school course: journeys row (school-owned, uid NULL) + school_courses
    + version 1. Published courses also get locked step_content per step."""
    journey_id = str(uuid.uuid4())
    step_rows = _steps(steps, journey_id[:8])
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO journeys (id, uid, school_id, question, title, description, estimated_hours, steps)
            VALUES (%s, NULL, %s, %s, %s, %s, 1.0, %s::jsonb)
            """,
            (journey_id, school["id"], title, title, f"{title} for class",
             json.dumps(step_rows if published else [])),
        )
        cur.execute(
            """
            INSERT INTO school_courses (journey_id, school_id, status, published_version, created_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (journey_id, school["id"], status or ("published" if published else "draft"),
             1 if published else None, creator),
        )
        cur.execute(
            """
            INSERT INTO course_versions (journey_id, version, state, meta, steps, created_by)
            VALUES (%s, 1, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (journey_id, "published" if published else "draft",
             json.dumps({"title": title}), json.dumps(step_rows), creator),
        )
        if published:
            for s in step_rows:
                cur.execute(
                    """
                    INSERT INTO step_content (journey_id, step_id, content, quiz_anchors, model,
                                              source, locked)
                    VALUES (%s, %s, %s, '[]'::jsonb, 'teacher', 'school_published', %s)
                    """,
                    (journey_id, s["id"], f"Published body of {s['title']}", locked),
                )
    return journey_id


def assign(conn, cls: dict, journey_id: str, *, status: str = "active", due_at=None) -> str:
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO course_assignments (school_id, class_id, journey_id, status, due_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (cls["school_id"], cls["id"], journey_id, status, due_at),
        )
        return str(cur.fetchone()["id"])


def make_journey(conn, owner_uid: Optional[str], *, title: str = "How do volcanoes work?",
                 steps: int = 2, with_content: bool = True, marketplace_status: str = "private") -> str:
    """An ordinary (non-school) journey, optionally with cached AI content."""
    journey_id = str(uuid.uuid4())
    step_rows = _steps(steps, journey_id[:8])
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO journeys (id, uid, question, title, description, estimated_hours, steps,
                                  marketplace_status)
            VALUES (%s, %s, %s, %s, %s, 1.0, %s::jsonb, %s)
            """,
            (journey_id, owner_uid, title, title, title, json.dumps(step_rows), marketplace_status),
        )
        if with_content:
            for s in step_rows:
                cur.execute(
                    """
                    INSERT INTO step_content (journey_id, step_id, content, quiz_anchors, model, prompt_version)
                    VALUES (%s, %s, %s, '[]'::jsonb, 'gpt-test', 999)
                    """,
                    (journey_id, s["id"], f"AI body of {s['title']}"),
                )
    return journey_id


def make_family_profile(conn, parent_uid: str) -> str:
    uid = f"prof_{secrets.token_hex(6)}"
    make_user(conn, uid, email=None, display_name="Kid", profile_type="profile", age_group="child")
    with _cur(conn) as cur:
        cur.execute(
            "INSERT INTO family_links (parent_uid, child_uid, status) VALUES (%s, %s, 'active')",
            (parent_uid, uid),
        )
    return uid


def make_document(conn, school: dict, *, uploaded_by: Optional[str] = None,
                  filename: str = "notes.pdf", status: str = "uploaded",
                  sha256: Optional[str] = None, size_bytes: int = 2048) -> dict:
    """A source_documents row with a storage_path derived from its id."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    mime = ("application/pdf" if ext == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO source_documents (school_id, uploaded_by, filename, mime, size_bytes, sha256, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (school["id"], uploaded_by, filename, mime, size_bytes, sha256, status),
        )
        row = dict(cur.fetchone())
        doc_id = str(row["id"])
        path = f"{school['id']}/{doc_id}.{ext}"
        cur.execute("UPDATE source_documents SET storage_path = %s WHERE id = %s", (path, doc_id))
    row["id"] = doc_id
    row["storage_path"] = path
    return row


def add_chunks(conn, document_id: str, texts: list[str]) -> None:
    """Attach ordered document_chunks to a document (for builder/update tests)."""
    with _cur(conn) as cur:
        for i, text in enumerate(texts):
            cur.execute(
                """INSERT INTO document_chunks (document_id, ordinal, heading_path, text, char_count)
                   VALUES (%s, %s, %s, %s, %s)""",
                (document_id, i, [], text, len(text)),
            )


def make_course_draft(conn, school: dict, *, creator: Optional[str] = None,
                      title: str = "Draft Course", with_source: bool = True) -> str:
    """A draft school course: journey (uid NULL) + school_courses('draft') +
    course_versions('draft'), optionally with a ready source document + chunks."""
    journey_id = str(uuid.uuid4())
    with _cur(conn) as cur:
        cur.execute(
            "INSERT INTO journeys (id, uid, school_id, question, title, description, estimated_hours, steps) "
            "VALUES (%s, NULL, %s, %s, %s, '', 0, '[]'::jsonb)",
            (journey_id, school["id"], title, title),
        )
        cur.execute(
            "INSERT INTO school_courses (journey_id, school_id, status, created_by) VALUES (%s, %s, 'draft', %s)",
            (journey_id, school["id"], creator),
        )
        cur.execute(
            "INSERT INTO course_versions (journey_id, version, state, revision, meta, steps) "
            "VALUES (%s, 1, 'draft', 0, '{\"status\":\"empty\"}'::jsonb, '[]'::jsonb)",
            (journey_id,),
        )
        if with_source:
            cur.execute(
                "INSERT INTO source_documents (school_id, filename, mime, size_bytes, status) "
                "VALUES (%s, 'notes.pdf', 'application/pdf', 4096, 'ready') RETURNING id",
                (school["id"],),
            )
            doc_id = cur.fetchone()["id"]
            for i in range(3):
                cur.execute(
                    "INSERT INTO document_chunks (document_id, ordinal, heading_path, text, char_count) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (doc_id, i, [f"Section {i + 1}"], f"Lesson content about topic {i + 1}. " * 12, 300),
                )
            cur.execute(
                "INSERT INTO course_sources (journey_id, document_id, school_id) VALUES (%s, %s, %s)",
                (journey_id, doc_id, school["id"]),
            )
    return journey_id


def make_outlined_draft(conn, school: dict, *, creator: Optional[str] = None) -> str:
    """A draft course whose outline is reviewed and ready to build: two AI steps
    grounded in the source document's chunk UUIDs (for build/regenerate tests)."""
    journey_id = make_course_draft(conn, school, creator=creator)
    rows = fetch(conn, """
        SELECT dc.id::text AS id FROM course_sources cs
          JOIN document_chunks dc ON dc.document_id = cs.document_id
         WHERE cs.journey_id = %s ORDER BY dc.ordinal
    """, (journey_id,))
    cids = [r["id"] for r in rows]  # 3 chunk uuids, cite_ids 0..2
    steps = [
        {"id": "s1", "title": "Introduction", "description": "", "type": "concept",
         "estimated_minutes": 10, "core_question": "What is topic 1?",
         "learning_objective": "Understand topic 1", "chunk_ids": [cids[0], cids[1]],
         "origin": "ai", "body_md": None, "flags": []},
        {"id": "s2", "title": "Going deeper", "description": "", "type": "practice",
         "estimated_minutes": 10, "core_question": "How does topic 3 work?",
         "learning_objective": "Apply topic 3", "chunk_ids": [cids[2]],
         "origin": "ai", "body_md": None, "flags": []},
    ]
    with _cur(conn) as cur:
        cur.execute(
            "UPDATE course_versions SET steps = %s::jsonb, "
            "meta = '{\"status\":\"outline_ready\"}'::jsonb, revision = 1 "
            "WHERE journey_id = %s AND state = 'draft'",
            (json.dumps(steps), journey_id))
    return journey_id


def make_built_draft(conn, school: dict, *, creator: Optional[str] = None) -> str:
    """A draft whose steps are built (bodies + quiz anchors), ready to publish."""
    journey_id = make_outlined_draft(conn, school, creator=creator)
    steps = fetch(conn, "SELECT steps FROM course_versions WHERE journey_id = %s AND state = 'draft'",
                  (journey_id,))[0]["steps"]
    for i, s in enumerate(steps):
        s["body_md"] = f"## {s['title']}\n\nA grounded lesson body for step {i + 1}."
        s["citations"] = s.get("chunk_ids", [])
        s["key_facts"] = ["Fact A", "Fact B"]
        s["quiz_anchors"] = [{"id": "qa1", "fact": "Fact A", "chunk_ids": s.get("chunk_ids", [])}]
        s["flags"] = []
        s["build_status"] = "built"
    with _cur(conn) as cur:
        cur.execute(
            "UPDATE course_versions SET steps = %s::jsonb, "
            "meta = '{\"status\":\"built\",\"title\":\"Draft Course\"}'::jsonb, revision = 2 "
            "WHERE journey_id = %s AND state = 'draft'", (json.dumps(steps), journey_id))
    return journey_id


def make_published_course(conn, school: dict, *, creator: Optional[str] = None) -> str:
    """A published course: one `published` version, no draft, student-facing
    `journeys.steps` written — for version-history / restore tests."""
    journey_id = make_built_draft(conn, school, creator=creator)
    steps = fetch(conn, "SELECT steps FROM course_versions WHERE journey_id = %s AND state = 'draft'",
                  (journey_id,))[0]["steps"]
    public = [{k: s.get(k) for k in ("id", "title", "description", "type", "estimated_minutes", "core_question")}
              for s in steps]
    with _cur(conn) as cur:
        cur.execute("UPDATE course_versions SET state = 'published', published_at = now() "
                    "WHERE journey_id = %s AND state = 'draft'", (journey_id,))
        cur.execute("UPDATE journeys SET steps = %s::jsonb WHERE id = %s", (json.dumps(public), journey_id))
        cur.execute("UPDATE school_courses SET status = 'published', published_version = 1 WHERE journey_id = %s",
                    (journey_id,))
    return journey_id


def make_update_proposal(conn, school: dict, *, journey_id: str, op: str = "modify",
                         step_id: str = "s1", status: str = "pending",
                         payload: Optional[dict] = None, reason: str = "source changed") -> str:
    """A `course_change_proposals` row for update-flow tests. Defaults build a
    valid modify/add payload so an accepted proposal applies cleanly."""
    if payload is None:
        _step = {"id": step_id, "title": "Updated step", "description": "", "type": "concept",
                 "estimated_minutes": 10, "core_question": "", "learning_objective": "",
                 "body_md": "## Updated\n\nA fresh grounded body.", "citations": [], "key_facts": [],
                 "quiz_anchors": [], "chunk_ids": [], "origin": "ai"}
        if op == "modify":
            payload = {"step": _step, "old_body": "old body", "new_body": _step["body_md"],
                       "diff": {"added": 2, "removed": 1}, "old_title": "Introduction"}
        elif op == "add":
            payload = {"after_step_id": None, "step": {**_step, "id": "snew1", "title": "New section"}}
        else:  # remove
            payload = {"suggestion_only": False}
    row = fetch(conn, """INSERT INTO course_change_proposals
                             (journey_id, version, op, step_id, payload, reason, status)
                         VALUES (%s, 1, %s, %s, %s::jsonb, %s, %s) RETURNING id::text""",
                (journey_id, op, step_id, json.dumps(payload), reason, status))
    return row[0]["id"]


def enqueue_job(conn, school: dict, kind: str = "outline", status: str = "queued") -> str:
    row = fetch(conn, "INSERT INTO school_jobs (school_id, kind, status) VALUES (%s, %s, %s) RETURNING id::text",
                (school["id"], kind, status))
    return row[0]["id"]


def step_ids(conn, journey_id: str) -> list[str]:
    with _cur(conn) as cur:
        cur.execute("SELECT steps FROM journeys WHERE id = %s", (journey_id,))
        return [s["id"] for s in cur.fetchone()["steps"]]


def fetch(conn, sql: str, params: tuple = ()) -> list[dict]:
    with _cur(conn) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []
