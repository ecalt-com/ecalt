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
                 status: str = "active", uid: Optional[str] = None) -> str:
    uid = uid or f"stu_{secrets.token_hex(8)}"
    make_user(conn, uid, email=None, display_name=display_name, profile_type="school_student",
              age_group="child")
    with _cur(conn) as cur:
        cur.execute(
            """
            INSERT INTO school_students (uid, school_id, display_name, grade, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (uid, school["id"], display_name, grade, status),
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


def step_ids(conn, journey_id: str) -> list[str]:
    with _cur(conn) as cur:
        cur.execute("SELECT steps FROM journeys WHERE id = %s", (journey_id,))
        return [s["id"] for s in cur.fetchone()["steps"]]


def fetch(conn, sql: str, params: tuple = ()) -> list[dict]:
    with _cur(conn) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []
