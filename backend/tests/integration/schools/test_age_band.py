"""SC-503: school students are pitched to their class grade.

grade → age band (≤5 kids, 6+ teens; never adult) drives the tutor and quiz
prompts. The class that assigned the course is authoritative; the student's own
grade is the fallback.
"""
import pytest

from app.services import chat_service, quiz_service
from app.services.school_assignment_service import age_band_for_grade, student_age_band
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def test_age_band_for_grade_pure():
    assert age_band_for_grade(None) is None
    assert age_band_for_grade(3) == "kids"
    assert age_band_for_grade(5) == "kids"
    assert age_band_for_grade(6) == "teens"
    assert age_band_for_grade(12) == "teens"


def _assign(db, school, cls, journey_id):
    f.fetch(db, """INSERT INTO course_assignments (class_id, school_id, journey_id, status, settings)
                   VALUES (%s, %s, %s, 'active', '{}'::jsonb)""",
            (cls["id"], school["id"], journey_id))


def test_band_from_class_grade_wins_over_student_grade(db):
    school = f.make_school(db)
    jid = f.make_published_course(db, school)
    cls = f.make_class(db, school, grade=4)
    stu = f.make_student(db, school, grade=9)      # the student's own grade differs
    f.enroll(db, cls, stu)
    _assign(db, school, cls, jid)
    assert student_age_band(stu, jid) == "kids"    # the class (grade 4) decides


def test_band_falls_back_to_student_grade_without_course_context(db):
    school = f.make_school(db)
    stu = f.make_student(db, school, grade=8)
    assert student_age_band(stu, None) == "teens"
    jid = f.make_published_course(db, school)       # not assigned to any of the student's classes
    assert student_age_band(stu, jid) == "teens"


def test_non_student_has_no_band(db):
    assert student_age_band(f.make_user(db), None) is None


def test_lowest_class_grade_wins_when_several(db):
    school = f.make_school(db)
    jid = f.make_published_course(db, school)
    young = f.make_class(db, school, grade=4)
    older = f.make_class(db, school, grade=10)
    stu = f.make_student(db, school, grade=10)
    f.enroll(db, young, stu)
    f.enroll(db, older, stu)
    _assign(db, school, young, jid)
    _assign(db, school, older, jid)
    assert student_age_band(stu, jid) == "kids"     # conservative: youngest class


def test_tutor_and_quiz_prompts_use_the_band(db):
    school = f.make_school(db)
    jid = f.make_published_course(db, school)
    cls = f.make_class(db, school, grade=3)
    stu = f.make_student(db, school, grade=3)
    f.enroll(db, cls, stu)
    _assign(db, school, cls, jid)
    assert "primary-school" in chat_service._get_chat_age_context(stu, jid)
    assert "kids" in quiz_service._get_user_age_context(stu, jid)

    teen = f.make_student(db, school, grade=9)
    teen_cls = f.make_class(db, school, grade=9)
    f.enroll(db, teen_cls, teen)
    _assign(db, school, teen_cls, jid)
    assert "secondary-school" in chat_service._get_chat_age_context(teen, jid)
    assert "teens" in quiz_service._get_user_age_context(teen, jid)
