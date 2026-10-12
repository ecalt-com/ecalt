// Typed wrappers for the schools API (backend/plans/school-courses, M1:
// schools, staff, invites, settings, DPA, ECALT-admin school management).
// Contract: backend/plans/school-courses/frontend-changes.md.
import { request } from './api'

export type StaffRole = 'owner' | 'admin' | 'teacher'
export type SchoolStatus = 'onboarding' | 'active' | 'suspended' | 'terminated'

export interface MySchool {
  id: string
  name: string
  slug: string
  status: SchoolStatus
  role: StaffRole
}

export interface SchoolSettings {
  teachers_can_create_students: boolean
  login_roster_visible: boolean
  teacher_transcript_access: boolean
  delete_originals_after_days: number | null
  student_daily_tutor_messages: number
  student_daily_quiz_sets: number
}

export interface School {
  id: string
  name: string
  slug: string
  country: string
  status: SchoolStatus
  seat_limit: number
  monthly_ai_budget_cents?: number   // owners/admins (and ECALT admins) only
  settings: SchoolSettings
  dpa_version: string | null
  dpa_accepted_at: string | null
  dpa_current_version: string
  dpa_accepted: boolean
  staff_count: number
  student_count: number
  created_at: string
  terminated_at: string | null
  my_role?: StaffRole                // staff view only
}

export interface StaffMember {
  uid: string
  role: StaffRole
  display_name: string | null
  email: string | null
  photo_url: string | null
  created_at: string
}

export interface StaffInvite {
  id: string
  email: string
  role: StaffRole
  expires_at: string
  created_at: string
  expired: boolean
}

export interface InvitePreview {
  school_name: string
  role: StaffRole
  email_hint: string
  expires_at: string
}

const enc = encodeURIComponent
const json = (method: string, body?: unknown): RequestInit =>
  ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })

// ── Staff: schools ───────────────────────────────────────────────────────────

export const getMySchools = (token: string): Promise<{ schools: MySchool[] }> =>
  request('/api/v1/schools/mine', undefined, token)

export const getSchool = (schoolId: string, token: string): Promise<School> =>
  request(`/api/v1/schools/${enc(schoolId)}`, undefined, token)

export const updateSchool = (
  schoolId: string, body: { name?: string; settings?: Partial<SchoolSettings> }, token: string,
): Promise<School> =>
  request(`/api/v1/schools/${enc(schoolId)}`, json('PATCH', body), token)

export const acceptDpa = (schoolId: string, dpaVersion: string, token: string): Promise<School> =>
  request(`/api/v1/schools/${enc(schoolId)}/dpa/accept`, json('POST', { dpa_version: dpaVersion }), token)

// ── Staff and invites ────────────────────────────────────────────────────────

export const listStaff = (schoolId: string, token: string): Promise<{ members: StaffMember[]; invites: StaffInvite[] }> =>
  request(`/api/v1/schools/${enc(schoolId)}/staff`, undefined, token)

export type CreatedInvite = Omit<StaffInvite, 'expired'>

export const inviteStaff = (schoolId: string, email: string, role: StaffRole, token: string): Promise<CreatedInvite> =>
  request(`/api/v1/schools/${enc(schoolId)}/staff/invites`, json('POST', { email, role }), token)

export const revokeInvite = (schoolId: string, inviteId: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/staff/invites/${enc(inviteId)}`, json('DELETE'), token)

export const changeStaffRole = (schoolId: string, uid: string, role: StaffRole, token: string): Promise<{ uid: string; role: StaffRole }> =>
  request(`/api/v1/schools/${enc(schoolId)}/staff/${enc(uid)}`, json('PATCH', { role }), token)

// Removing yourself is "leave school".
export const removeStaff = (schoolId: string, uid: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/staff/${enc(uid)}`, json('DELETE'), token)

// Invite links: preview needs no sign-in; accept needs the invited Google account.
export const previewSchoolInvite = (token: string): Promise<InvitePreview> =>
  request('/api/v1/school-invites/preview', json('POST', { token }))

export const acceptSchoolInvite = (inviteToken: string, token: string): Promise<{ school_id: string; school_name: string; role: StaffRole }> =>
  request('/api/v1/school-invites/accept', json('POST', { token: inviteToken }), token)

// ── ECALT admin ──────────────────────────────────────────────────────────────

export interface AdminCreateSchool {
  name: string
  country?: string
  seat_limit?: number
  monthly_ai_budget_cents?: number
  owner_email?: string
}

export interface AdminUpdateSchool {
  name?: string
  status?: SchoolStatus
  seat_limit?: number
  monthly_ai_budget_cents?: number
}

export const adminListSchools = (
  params: { q?: string; status?: SchoolStatus; limit?: number; offset?: number }, token: string,
): Promise<{ schools: School[]; total: number }> => {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  return request(`/api/v1/admin/schools${qs.toString() ? `?${qs}` : ''}`, undefined, token)
}

export const adminCreateSchool = (body: AdminCreateSchool, token: string): Promise<School & { owner_invite?: CreatedInvite }> =>
  request('/api/v1/admin/schools', json('POST', body), token)

export const adminUpdateSchool = (schoolId: string, body: AdminUpdateSchool, token: string): Promise<School> =>
  request(`/api/v1/admin/schools/${enc(schoolId)}`, json('PATCH', body), token)

export const adminInviteOwner = (schoolId: string, email: string, token: string): Promise<CreatedInvite> =>
  request(`/api/v1/admin/schools/${enc(schoolId)}/owner-invite`, json('POST', { email }), token)

// ── Permissions (mirror of TESTING.md §4; the API stays the authority) ───────

export type SchoolAction = 'manage_settings' | 'manage_staff' | 'invite_owner' | 'accept_dpa' | 'view_budget'

export function canDo(role: StaffRole | null | undefined, action: SchoolAction): boolean {
  if (!role) return false
  switch (action) {
    case 'accept_dpa':
    case 'invite_owner':
      return role === 'owner'
    case 'manage_settings':
    case 'manage_staff':
    case 'view_budget':
      return role === 'owner' || role === 'admin'
  }
}

export const ROLE_LABEL: Record<StaffRole, string> = { owner: 'Owner', admin: 'Admin', teacher: 'Teacher' }

// Friendly text for the school error codes (frontend-changes.md §14).
export function schoolErrorMessage(code: string | null, fallback = 'Something went wrong. Please try again.'): string {
  switch (code) {
    case 'school_role_required': return 'Only school admins can do this.'
    case 'school_access_suspended': return "This school's ECALT access is suspended. Contact ECALT support."
    case 'school_not_found': return "That school isn't available to you."
    case 'parent_profile_required': return 'Switch to your own profile to manage your school.'
    case 'already_member': return 'This person is already on your staff.'
    case 'last_owner': return 'A school needs at least one owner. Make someone else an owner first.'
    case 'invalid_email': return 'Enter a valid email address.'
    case 'invalid_settings': return 'Some settings are not valid.'
    case 'dpa_version_mismatch': return 'The agreement has changed. Reload the page and review the current version.'
    case 'invite_invalid': return "This invite link isn't valid any more. Ask the school for a new one."
    case 'invite_expired': return 'This invite has expired. Ask the school to send a new one.'
    case 'invite_email_mismatch': return 'This invite was sent to a different email address.'
    case 'staff_must_be_adult': return 'School staff accounts must belong to an adult.'
    case 'account_setup_required': return 'Finish setting up your ECALT account, then open the invite again.'
    case 'school_terminated': return "A terminated school can't be reopened."
    case 'seat_limit_reached': return 'The school has no seats left. Archive students who have left, or ask ECALT for more seats.'
    case 'dpa_required': return "The school's owner must accept the data processing agreement before students can be added."
    case 'external_ref_taken': return 'Another student already has this roll number.'
    case 'student_not_found': return 'Student not found.'
    case 'class_not_found': return 'Class not found.'
    case 'class_archived': return 'This class is archived.'
    case 'member_not_found': return "That person isn't on this school's staff."
    case 'import_has_errors': return 'Fix the errors in the file, then import again.'
    case 'class_code_invalid': return "We couldn't find that class code. Check it with your teacher."
    case 'invalid_student_secret': return "That's not right. Try again, or ask your teacher."
    case 'student_locked': return 'Too many tries. Ask your teacher, or wait a few minutes.'
    case 'class_code_throttled': return 'Too many wrong tries in this class. Wait a few minutes, or ask your teacher.'
    case 'invalid_badge': return "This badge doesn't work any more. Ask your teacher for a new card."
    case 'login_unavailable': return "Class sign-in isn't available right now. Ask your teacher."
    case 'school_session_expired': return 'Your session has ended. Sign in again with your class code.'
    case 'picture_secret_too_old': return 'Picture passwords are only for younger grades. Use a PIN instead.'
    case 'school_budget_exhausted': return 'Your class has used up its AI help for now. Ask your teacher.'
    case 'school_daily_limit_reached': return "You've used all your AI help for today. Try again tomorrow."
    default: return fallback
  }
}

// ── Students (M2) ────────────────────────────────────────────────────────────

export type SecretKind = 'picture' | 'pin'
// A picture password is 3 icon indices (0–15, order matters); a PIN is 6 digits.
export type StudentSecret = number[] | string

export interface ClassRef { id: string; name: string }

export interface Student {
  uid: string
  display_name: string
  grade: number | null
  external_ref: string | null
  avatar: string | null
  status: 'active' | 'archived'
  secret_kind: SecretKind
  has_secret: boolean
  has_badge: boolean
  locked_until: string | null
  created_at: string
  archived_at: string | null
  classes: ClassRef[]
}

export interface StudentList {
  students: Student[]
  total: number
  seat_limit: number
  seats_used: number
  can_manage: boolean
}

export interface CreatedStudent extends Student {
  secret: StudentSecret
  badge_token: string
}

export interface ImportRow {
  line: number
  display_name: string
  grade: number | null
  external_ref: string | null
  class_name: string | null
  secret_kind: SecretKind | null
  action: 'create' | 'update'
  errors: string[]
  warnings: string[]
}

export interface ImportReport {
  dry_run: boolean
  rows: ImportRow[]
  errors: string[]
  summary: {
    rows: number
    create: number
    update: number
    rows_with_errors: number
    new_classes: string[]
    seats_available: number
    created_classes?: number
  }
}

export const listStudents = (
  schoolId: string,
  params: { q?: string; class_id?: string; status?: 'active' | 'archived'; limit?: number; offset?: number },
  token: string,
): Promise<StudentList> => {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  return request(`/api/v1/schools/${enc(schoolId)}/students${qs.toString() ? `?${qs}` : ''}`, undefined, token)
}

export const createStudent = (
  schoolId: string,
  body: { display_name: string; grade?: number | null; external_ref?: string | null; secret_kind?: SecretKind; class_ids?: string[] },
  token: string,
): Promise<CreatedStudent> =>
  request(`/api/v1/schools/${enc(schoolId)}/students`, json('POST', body), token)

export const updateStudent = (
  schoolId: string, uid: string,
  body: { display_name?: string; grade?: number | null; external_ref?: string | null; avatar?: string },
  token: string,
): Promise<Student> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/${enc(uid)}`, json('PATCH', body), token)

export const deleteStudent = (schoolId: string, uid: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/${enc(uid)}`, json('DELETE'), token)

export const resetStudentSecret = (schoolId: string, uid: string, secretKind: SecretKind | undefined, token: string):
  Promise<{ uid: string; secret_kind: SecretKind; secret: StudentSecret }> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/${enc(uid)}/reset-secret`,
    json('POST', secretKind ? { secret_kind: secretKind } : {}), token)

export const archiveStudents = (schoolId: string, uids: string[], token: string): Promise<{ changed: number }> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/archive`, json('POST', { student_uids: uids }), token)

export const restoreStudent = (schoolId: string, uid: string, token: string): Promise<{ changed: number }> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/${enc(uid)}/restore`, json('POST'), token)

export const exportStudent = (schoolId: string, uid: string, token: string): Promise<unknown> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/${enc(uid)}/export`, undefined, token)

export const importStudents = (schoolId: string, csv: string, dryRun: boolean, token: string): Promise<ImportReport> =>
  request(`/api/v1/schools/${enc(schoolId)}/students/import?dry_run=${dryRun}`, json('POST', { csv }), token)

// ── Classes (M2) ─────────────────────────────────────────────────────────────

export interface ClassTeacher { uid: string; role: 'lead' | 'co'; display_name: string | null }

export interface SchoolClass {
  id: string
  name: string
  grade: number | null
  subject: string | null
  academic_year: string | null
  join_code: string
  archived: boolean
  created_at: string
  is_mine: boolean
  student_count: number
  teachers: ClassTeacher[]
}

export interface ClassStudent {
  uid: string
  display_name: string
  grade: number | null
  external_ref: string | null
  avatar: string | null
  status: 'active' | 'archived'
  secret_kind: SecretKind
  has_secret: boolean
  has_badge: boolean
  locked_until: string | null
  enrolled_at: string
}

export interface ClassDetail extends SchoolClass {
  students: ClassStudent[]
  can_manage: boolean
}

export interface LoginCard {
  uid: string
  display_name: string
  avatar: string | null
  secret_kind: SecretKind
  secret: StudentSecret | null
  badge_token: string | null
}

export interface LoginCards {
  school_name: string
  class: { id: string; name: string; join_code: string }
  cards: LoginCard[]
}

type ClassFields = { name?: string; grade?: number | null; subject?: string | null; academic_year?: string | null }

export const listClasses = (schoolId: string, token: string, includeArchived = false): Promise<{ classes: SchoolClass[] }> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes${includeArchived ? '?include_archived=true' : ''}`, undefined, token)

export const createClass = (schoolId: string, body: ClassFields & { name: string }, token: string): Promise<ClassDetail> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes`, json('POST', body), token)

export const getClass = (schoolId: string, classId: string, token: string): Promise<ClassDetail> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}`, undefined, token)

export const updateClass = (schoolId: string, classId: string, body: ClassFields, token: string): Promise<ClassDetail> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}`, json('PATCH', body), token)

export const archiveClass = (schoolId: string, classId: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}`, json('DELETE'), token)

export const addClassTeacher = (schoolId: string, classId: string, uid: string, role: 'lead' | 'co', token: string): Promise<ClassDetail> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/teachers`, json('POST', { uid, role }), token)

export const removeClassTeacher = (schoolId: string, classId: string, uid: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/teachers/${enc(uid)}`, json('DELETE'), token)

export const enrollStudents = (schoolId: string, classId: string, uids: string[], token: string): Promise<ClassDetail> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/students`, json('POST', { student_uids: uids }), token)

export const unenrollStudent = (schoolId: string, classId: string, uid: string, token: string): Promise<void> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/students/${enc(uid)}`, json('DELETE'), token)

export const rotateClassCode = (schoolId: string, classId: string, token: string): Promise<{ join_code: string }> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/rotate-code`, json('POST'), token)

export const getLoginCards = (
  schoolId: string, classId: string, body: { student_uids?: string[]; reset: boolean }, token: string,
): Promise<LoginCards> =>
  request(`/api/v1/schools/${enc(schoolId)}/classes/${enc(classId)}/login-cards`, json('POST', body), token)

// ── Student sign-in (public) ─────────────────────────────────────────────────

export interface ClassLookup {
  class: { name: string; grade: number | null }
  school: { name: string }
  roster_visible: boolean
  students: { uid: string; display_name: string; avatar: string | null; secret_kind: SecretKind }[]
}

export interface ClassSession {
  custom_token: string
  expires_in: number
  student: { uid: string; display_name: string }
}

export const formatJoinCode = (code: string) => (code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code)

export const lookupClass = (code: string): Promise<ClassLookup> =>
  request(`/api/v1/school-login/classes/${enc(code.replace(/[\s-]/g, '').toUpperCase())}`)

export const classSignIn = (body: {
  class_code: string; student_uid?: string; external_ref?: string; secret: { kind: SecretKind; value: StudentSecret }
}): Promise<ClassSession> =>
  request('/api/v1/school-login/sessions', json('POST', body))

export const badgeSignIn = (token: string): Promise<ClassSession> =>
  request('/api/v1/school-login/badge', json('POST', { token }))
