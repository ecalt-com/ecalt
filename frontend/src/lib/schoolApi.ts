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
    default: return fallback
  }
}
