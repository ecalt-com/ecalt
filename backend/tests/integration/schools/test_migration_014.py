"""DB-01..05: migration 014_schools on the baseline schema (TESTING.md §2).

DB-01 applies cleanly on the baseline and is idempotent; RLS on every new table
DB-02 a school course can never enter the marketplace (D11 CHECK)
DB-03 composite FKs make cross-school links impossible
DB-04 at most one draft version per course
DB-05 new CHECK values: profile_type 'school_student', step_content.source
"""
import psycopg2
import pytest

from tests.factories import schools as f
from tests.schools import harness

pytestmark = pytest.mark.schools_db

NEW_TABLES = {
    "schools", "school_members", "school_invites", "school_students", "classes", "class_teachers",
    "class_enrollments", "school_courses", "course_versions", "source_documents", "document_chunks",
    "course_sources", "course_assignments", "school_jobs", "course_change_proposals", "school_usage",
    "school_audit_log",
}


def _violates(db, sql, params=()):
    with pytest.raises((psycopg2.IntegrityError, psycopg2.errors.CheckViolation)):
        with db.cursor() as cur:
            cur.execute(sql, params)


def test_db01_tables_exist_with_rls(db):
    rows = f.fetch(db, "SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY(%s)", (list(NEW_TABLES),))
    assert {r["relname"] for r in rows} == NEW_TABLES
    assert all(r["relrowsecurity"] for r in rows)


def test_db01_migration_is_idempotent(db):
    sql = (harness.MIGRATIONS_DIR / "014_schools.sql").read_text()
    with db.cursor() as cur:
        cur.execute("SET search_path TO public, extensions")
        cur.execute(sql)
        cur.execute(sql)


def test_db02_school_course_cannot_be_published_to_marketplace(db):
    school = f.make_school(db)
    course = f.make_course(db, school, None)
    _violates(db, "UPDATE journeys SET marketplace_status = 'published' WHERE id = %s", (course,))
    _violates(db, "UPDATE journeys SET marketplace_status = 'pending_review' WHERE id = %s", (course,))


def test_db02_ordinary_journeys_unaffected(db):
    owner = f.make_user(db)
    journey = f.make_journey(db, owner)
    with db.cursor() as cur:
        cur.execute("UPDATE journeys SET marketplace_status = 'published' WHERE id = %s", (journey,))


def test_db03_no_cross_school_links(db):
    a, b = f.make_school(db, name="A"), f.make_school(db, name="B")
    teacher_b = f.make_staff(db, b)
    student_b = f.make_student(db, b)
    class_a = f.make_class(db, a)
    course_b = f.make_course(db, b, teacher_b)

    # student of B into a class of A
    _violates(db, "INSERT INTO class_enrollments (class_id, school_id, student_uid) VALUES (%s, %s, %s)",
              (class_a["id"], a["id"], student_b))
    _violates(db, "INSERT INTO class_enrollments (class_id, school_id, student_uid) VALUES (%s, %s, %s)",
              (class_a["id"], b["id"], student_b))
    # teacher of B on a class of A
    _violates(db, "INSERT INTO class_teachers (class_id, school_id, uid) VALUES (%s, %s, %s)",
              (class_a["id"], a["id"], teacher_b))
    # course of B assigned to a class of A
    _violates(db, "INSERT INTO course_assignments (school_id, class_id, journey_id) VALUES (%s, %s, %s)",
              (a["id"], class_a["id"], course_b))
    # school_courses row claiming another school's journey
    _violates(db, "UPDATE school_courses SET school_id = %s WHERE journey_id = %s", (a["id"], course_b))


def test_db04_one_draft_per_course(db):
    school = f.make_school(db)
    course = f.make_course(db, school, None, published=False)  # version 1 is a draft
    _violates(db, "INSERT INTO course_versions (journey_id, version, state) VALUES (%s, 2, 'draft')", (course,))
    with db.cursor() as cur:
        cur.execute("INSERT INTO course_versions (journey_id, version, state) VALUES (%s, 2, 'discarded')", (course,))


def test_db05_check_values(db):
    f.make_user(db, "stu_ok", profile_type="school_student", email=None)
    _violates(db, "INSERT INTO users (uid, profile_type) VALUES ('robot_1', 'robot')")
    owner = f.make_user(db)
    journey = f.make_journey(db, owner, with_content=False)
    _violates(db, "INSERT INTO step_content (journey_id, step_id, content, source) VALUES (%s, 's', 'x', 'magic')",
              (journey,))
    with db.cursor() as cur:
        cur.execute("INSERT INTO step_content (journey_id, step_id, content) VALUES (%s, 's', 'x')", (journey,))
    assert f.fetch(db, "SELECT source, locked FROM step_content WHERE journey_id = %s", (journey,)) == [
        {"source": "ai", "locked": False}
    ]
