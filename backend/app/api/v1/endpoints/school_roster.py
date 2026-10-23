"""Students and classes under /schools/{school_id} (plans/school-courses M2,
README §3.15). Mounted with the /schools prefix in router.py.

Read routes are open to every staff member of the school; the services decide
who may change what (school admins, class teachers, or teachers when the
school lets them manage students — decision D9).
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.school_auth import SchoolCtx, school_member
from app.services import school_assignment_service as assignments
from app.services import school_class_service as classes
from app.services import school_student_service as students

router = APIRouter()

SecretKind = Literal["picture", "pin"]
Grade = Field(None, ge=0, le=12)


class CreateStudentRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=80)
    grade: Optional[int] = Grade
    external_ref: Optional[str] = Field(None, min_length=1, max_length=40)
    secret_kind: Optional[SecretKind] = None
    class_ids: list[str] = Field(default_factory=list, max_length=20)


class UpdateStudentRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=80)
    grade: Optional[int] = Grade
    external_ref: Optional[str] = Field(None, max_length=40)
    avatar: Optional[Literal["fox", "owl", "panda", "octopus", "turtle", "rocket", "star", "dino"]] = None


class ResetSecretRequest(BaseModel):
    secret_kind: Optional[SecretKind] = None


class StudentUidsRequest(BaseModel):
    student_uids: list[str] = Field(..., min_length=1, max_length=2000)


class ImportRequest(BaseModel):
    csv: str = Field(..., min_length=1, max_length=1_000_000)


class CreateClassRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    grade: Optional[int] = Grade
    subject: Optional[str] = Field(None, max_length=80)
    academic_year: Optional[str] = Field(None, max_length=20)


class UpdateClassRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    grade: Optional[int] = Grade
    subject: Optional[str] = Field(None, max_length=80)
    academic_year: Optional[str] = Field(None, max_length=20)


class AddTeacherRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=128)
    role: Literal["lead", "co"] = "co"


class LoginCardsRequest(BaseModel):
    student_uids: Optional[list[str]] = Field(None, max_length=500)
    reset: bool = True


class AssignCourseRequest(BaseModel):
    journey_id: str = Field(..., min_length=1, max_length=64)
    due_at: Optional[datetime] = None
    tutor_enabled: bool = True
    quiz_required: bool = False


class UpdateAssignmentRequest(BaseModel):
    due_at: Optional[datetime] = None
    tutor_enabled: Optional[bool] = None
    quiz_required: Optional[bool] = None


# ── Students ──────────────────────────────────────────────────────────────────

@router.get("/{school_id}/students", summary="Students of the school (paged, searchable)")
def list_students(
    q: Optional[str] = Query(None, max_length=80),
    class_id: Optional[str] = None,
    status: Optional[Literal["active", "archived"]] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: SchoolCtx = Depends(school_member()),
):
    return students.list_students(ctx, q, class_id, status, limit, offset)


@router.post("/{school_id}/students", status_code=201,
             summary="Create a student (returns their picture/PIN and badge once)")
def create_student(body: CreateStudentRequest, ctx: SchoolCtx = Depends(school_member())):
    return students.create_student(ctx, body.display_name.strip(), body.grade, body.external_ref,
                                   body.secret_kind, body.class_ids)


@router.post("/{school_id}/students/import", summary="CSV roster import (dry_run=true → report only)")
def import_students(body: ImportRequest, dry_run: bool = True, ctx: SchoolCtx = Depends(school_member())):
    return students.import_students(ctx, body.csv, dry_run)


@router.post("/{school_id}/students/archive", summary="Archive students (year end) — blocks sign-in, keeps data")
def archive_students(body: StudentUidsRequest, ctx: SchoolCtx = Depends(school_member())):
    return students.set_archived(ctx, body.student_uids, archived=True)


@router.get("/{school_id}/students/{student_uid}", summary="One student")
def get_student(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    return students.get_student(ctx, student_uid)


@router.patch("/{school_id}/students/{student_uid}", summary="Update a student")
def update_student(student_uid: str, body: UpdateStudentRequest, ctx: SchoolCtx = Depends(school_member())):
    return students.update_student(ctx, student_uid, body.model_dump(exclude_unset=True))


@router.delete("/{school_id}/students/{student_uid}", status_code=204,
               summary="Delete a student and all their data (incl. their sign-in)")
async def delete_student(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    await students.delete_student(ctx, student_uid)


@router.post("/{school_id}/students/{student_uid}/reset-secret",
             summary="New picture password / PIN (returned once); clears a lockout")
def reset_secret(student_uid: str, body: ResetSecretRequest, ctx: SchoolCtx = Depends(school_member())):
    return students.reset_secret(ctx, student_uid, body.secret_kind)


@router.post("/{school_id}/students/{student_uid}/rotate-badge",
             summary="New QR badge (returned once); the old one stops working")
def rotate_badge(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    return students.rotate_badge(ctx, student_uid)


@router.post("/{school_id}/students/{student_uid}/archive", summary="Archive one student")
def archive_student(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    return students.set_archived(ctx, [student_uid], archived=True)


@router.post("/{school_id}/students/{student_uid}/restore", summary="Restore an archived student (needs a seat)")
def restore_student(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    return students.set_archived(ctx, [student_uid], archived=False)


@router.get("/{school_id}/students/{student_uid}/export", summary="Everything ECALT holds on a student (admins)")
def export_student(student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    return students.export_student(ctx, student_uid)


# ── Classes ───────────────────────────────────────────────────────────────────

@router.get("/{school_id}/classes", summary="Classes of the school")
def list_classes(include_archived: bool = False, ctx: SchoolCtx = Depends(school_member())):
    return {"classes": classes.list_classes(ctx, include_archived)}


@router.post("/{school_id}/classes", status_code=201, summary="Create a class (you become its lead teacher)")
def create_class(body: CreateClassRequest, ctx: SchoolCtx = Depends(school_member())):
    return classes.create_class(ctx, body.name, body.grade, body.subject, body.academic_year)


@router.get("/{school_id}/classes/{class_id}", summary="A class with its teachers and students")
def get_class(class_id: str, ctx: SchoolCtx = Depends(school_member())):
    return classes.get_class(ctx, class_id)


@router.patch("/{school_id}/classes/{class_id}", summary="Update a class (its teachers, admins)")
def update_class(class_id: str, body: UpdateClassRequest, ctx: SchoolCtx = Depends(school_member())):
    return classes.update_class(ctx, class_id, body.model_dump(exclude_unset=True))


@router.delete("/{school_id}/classes/{class_id}", status_code=204, summary="Archive a class")
def archive_class(class_id: str, ctx: SchoolCtx = Depends(school_member())):
    classes.archive_class(ctx, class_id)


@router.post("/{school_id}/classes/{class_id}/teachers", summary="Add a teacher to a class")
def add_teacher(class_id: str, body: AddTeacherRequest, ctx: SchoolCtx = Depends(school_member())):
    return classes.add_teacher(ctx, class_id, body.uid, body.role)


@router.delete("/{school_id}/classes/{class_id}/teachers/{uid}", status_code=204,
               summary="Remove a teacher from a class")
def remove_teacher(class_id: str, uid: str, ctx: SchoolCtx = Depends(school_member())):
    classes.remove_teacher(ctx, class_id, uid)


@router.post("/{school_id}/classes/{class_id}/students", summary="Enroll students in a class")
def enroll_students(class_id: str, body: StudentUidsRequest, ctx: SchoolCtx = Depends(school_member())):
    return classes.enroll_students(ctx, class_id, body.student_uids)


@router.delete("/{school_id}/classes/{class_id}/students/{student_uid}", status_code=204,
               summary="Remove a student from a class (their progress is kept)")
def unenroll_student(class_id: str, student_uid: str, ctx: SchoolCtx = Depends(school_member())):
    classes.unenroll_student(ctx, class_id, student_uid)


@router.post("/{school_id}/classes/{class_id}/rotate-code", summary="New class join code; the old one stops working")
def rotate_code(class_id: str, ctx: SchoolCtx = Depends(school_member())):
    return classes.rotate_join_code(ctx, class_id)


@router.post("/{school_id}/classes/{class_id}/login-cards",
             summary="Printable sign-in cards (reset=true issues new secrets and badges)")
def login_cards(class_id: str, body: LoginCardsRequest, ctx: SchoolCtx = Depends(school_member())):
    return classes.login_cards(ctx, class_id, body.student_uids, body.reset)


# ── Course assignments (M5 SC-501) ────────────────────────────────────────────

@router.get("/{school_id}/classes/{class_id}/courses",
            summary="Courses assigned to a class, with a progress summary")
def list_assignments(class_id: str, ctx: SchoolCtx = Depends(school_member())):
    return {"assignments": assignments.list_class_assignments(ctx, class_id)}


@router.post("/{school_id}/classes/{class_id}/courses", status_code=201,
             summary="Assign a published course to a class")
def assign_course(class_id: str, body: AssignCourseRequest, ctx: SchoolCtx = Depends(school_member())):
    return assignments.assign_course(
        ctx, class_id, body.journey_id, body.due_at,
        {"tutor_enabled": body.tutor_enabled, "quiz_required": body.quiz_required},
    )


@router.patch("/{school_id}/classes/{class_id}/courses/{assignment_id}",
              summary="Change an assignment's due date or settings")
def update_assignment(class_id: str, assignment_id: str, body: UpdateAssignmentRequest,
                      ctx: SchoolCtx = Depends(school_member())):
    return assignments.update_assignment(ctx, class_id, assignment_id,
                                         body.model_dump(exclude_unset=True))


@router.delete("/{school_id}/classes/{class_id}/courses/{assignment_id}", status_code=204,
               summary="Unassign a course (students lose access; progress is kept)")
def unassign_course(class_id: str, assignment_id: str, ctx: SchoolCtx = Depends(school_member())):
    assignments.unassign(ctx, class_id, assignment_id)


@router.get("/{school_id}/classes/{class_id}/progress",
            summary="Class progress matrix (students × assigned courses)")
def class_progress(class_id: str, ctx: SchoolCtx = Depends(school_member())):
    return assignments.class_progress_matrix(ctx, class_id)
