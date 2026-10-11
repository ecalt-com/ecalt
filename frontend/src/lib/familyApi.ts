// Typed wrappers for the parental-accounts endpoints (/family/* and the
// consent surfaces under /users). Contracts: backend/plans/parental-accounts/.
import { authHeaders, request } from './api'

export type VerificationTier = 'email_plus' | 'card' | 'id'
export type VerificationStatus = 'unverified' | 'pending' | 'verified'
export type ContentAgeBand = 'kids' | 'teens' | 'adults' | 'all'
export type TranscriptVisibility = 'summaries' | 'full'

// ── Children list / create / delete ──────────────────────────────────────────

export type ProfileType = 'account' | 'profile'

export interface FamilyChild {
  child_uid: string
  display_name: string | null
  email: string | null  // null for child profiles (no login of their own)
  profile_type: ProfileType
  avatar: string | null
  account_status: string
  age_group_flag: 'teen' | 'child' | null
  birth_year: number | null
  birth_month: number | null
  paused: boolean
  streak_days: number
  managed: boolean | null
  chat_enabled: boolean | null
  content_age_band: ContentAgeBand | null
  weekly_digest_enabled: boolean | null
  transcript_visibility: TranscriptVisibility | null
  verification_tier: VerificationTier | null
  verification_status: VerificationStatus | null
  verified_at: string | null
  linked_at: string
}

export const getChildren = (token: string): Promise<{ children: FamilyChild[] }> =>
  request('/api/v1/family/children', undefined, token)

// Adds a child *profile*: the child uses ECALT through the parent's sign-in,
// so no child email or password is collected.
export interface CreateChildBody {
  display_name: string
  birth_year: number
  birth_month?: number
  country?: string
  avatar?: string
}

export interface CreateChildResponse {
  child_uid: string
  display_name: string
  avatar: string | null
  profile_type: ProfileType
  age_group: 'teen' | 'child'
  chat_enabled: boolean
  managed: boolean
  verification_tier: VerificationTier
  verification_required: boolean
  account_status: string
}

export const createChild = (body: CreateChildBody, token: string): Promise<CreateChildResponse> =>
  request('/api/v1/family/children', { method: 'POST', body: JSON.stringify(body) }, token)

export const deleteChild = (childUid: string, token: string): Promise<void> =>
  request(`/api/v1/family/children/${childUid}`, { method: 'DELETE' }, token)

// ── Path B: authenticated approval of a child-initiated consent request ──────

export interface LinkDecisionResponse {
  status: 'confirmed' | 'refused' | 'already_confirmed' | 'verification_required'
  message: string
  child_uid?: string
  child_name?: string | null
  verification_tier?: VerificationTier
}

export const approveLinkRequest = (consentToken: string, token: string): Promise<LinkDecisionResponse> =>
  request(`/api/v1/family/link-requests/${encodeURIComponent(consentToken)}/approve`, { method: 'POST' }, token)

export const declineLinkRequest = (consentToken: string, token: string): Promise<LinkDecisionResponse> =>
  request(`/api/v1/family/link-requests/${encodeURIComponent(consentToken)}/decline`, { method: 'POST' }, token)

// ── Card micro-verification (Stripe Checkout, setup mode) ────────────────────

export const startCardVerification = (childUid: string, token: string): Promise<{ checkout_url: string }> =>
  request(`/api/v1/family/children/${childUid}/verify/card`, { method: 'POST' }, token)

export const confirmCardVerification = (
  childUid: string,
  sessionId: string,
  token: string,
): Promise<{ status: string; message?: string }> =>
  request(
    `/api/v1/family/children/${childUid}/verify/card/confirm`,
    { method: 'POST', body: JSON.stringify({ session_id: sessionId }) },
    token,
  )

// ── Child detail: overview / activity / transcripts ──────────────────────────

export interface ChildOverview {
  child: {
    display_name: string | null
    streak_days: number
    last_active_date: string | null
    created_at: string | null
    account_status: string
    age_group_flag: 'teen' | 'child' | null
    paused: boolean
  }
  totals: { journeys: number; steps_completed: number; knowledge_nodes: number; conversations: number }
  quiz: { total: number; correct: number; last_7_days: number }
  top_domains: { domain: string; mastery_level: number; concept_count: number }[]
  recent_journeys: {
    id: string
    title: string
    icon: string | null
    created_at: string
    total_steps: number
    completed_steps: number
    last_progress_at: string | null
  }[]
}

export const getChildOverview = (childUid: string, token: string): Promise<ChildOverview> =>
  request(`/api/v1/family/children/${childUid}/overview`, undefined, token)

export interface ChildActivity {
  days: number
  steps_completed: { completed_at: string; step_id: string; journey_id: string; journey_title: string }[]
  journeys_started: { id: string; title: string; question: string | null; created_at: string }[]
  quiz_answers: { concept: string; is_correct: boolean; difficulty: string | null; answered_at: string }[]
  conversations: { id: string; title: string | null; started_at: string; last_active: string; message_count: number }[]
  transcripts_available: boolean
}

export const getChildActivity = (childUid: string, days: number, token: string): Promise<ChildActivity> =>
  request(`/api/v1/family/children/${childUid}/activity?days=${days}`, undefined, token)

export interface ChildTranscript {
  id: string
  title: string | null
  started_at: string
  messages: { role: 'user' | 'assistant'; content: string; created_at: string }[]
}

export const getChildTranscript = (childUid: string, conversationId: string, token: string): Promise<ChildTranscript> =>
  request(`/api/v1/family/children/${childUid}/conversations/${conversationId}`, undefined, token)

// ── Child-facing family transparency ─────────────────────────────────────────

export interface MyFamily {
  linked: boolean
  parent_name?: string | null
  managed?: boolean
  parent_can_see?: {
    topics_and_journeys: boolean
    progress_and_streaks: boolean
    quiz_scores: boolean
    conversation_titles: boolean
    full_conversations: boolean
  }
}

export const getMyFamily = (token: string): Promise<MyFamily> =>
  request('/api/v1/family/my-family', undefined, token)

// ── Consent record ────────────────────────────────────────────────────────────

export interface ConsentEvent {
  action: string
  method: string | null
  policy_version: string | null
  jurisdiction: string | null
  created_at: string
}

export interface ChildConsentRecord {
  consent: {
    account_status: string
    consent_given_at: string | null
    consent_version: string | null
    jurisdiction: string | null
  }
  verification: {
    verification_tier: VerificationTier | null
    verification_status: VerificationStatus | null
    verified_at: string | null
  }
  current_policy_version: string
  events: ConsentEvent[]
}

export const getChildConsentRecord = (childUid: string, token: string): Promise<ChildConsentRecord> =>
  request(`/api/v1/family/children/${childUid}/consent`, undefined, token)

// ── Parental controls (Phase 4) ───────────────────────────────────────────────

export interface ChildSettings {
  paused: boolean
  chat_enabled: boolean
  content_age_band: ContentAgeBand | null
  transcript_visibility: TranscriptVisibility
  weekly_digest_enabled: boolean
}

export const patchChildSettings = (
  childUid: string,
  patch: Partial<ChildSettings>,
  token: string,
): Promise<{ child_uid: string; settings: ChildSettings }> =>
  request(`/api/v1/family/children/${childUid}/settings`, { method: 'PATCH', body: JSON.stringify(patch) }, token)

export const revokeChildConsent = (childUid: string, token: string): Promise<{ status: string; message: string }> =>
  request(`/api/v1/family/children/${childUid}/revoke-consent`, { method: 'POST' }, token)

export const cancelChildRevocation = (childUid: string, token: string): Promise<{ status: string; message?: string }> =>
  request(`/api/v1/family/children/${childUid}/revoke-consent/cancel`, { method: 'POST' }, token)

export const reconsentChild = (childUid: string, token: string): Promise<{ status: string; policy_version?: string }> =>
  request(`/api/v1/family/children/${childUid}/reconsent`, { method: 'POST' }, token)

// Child data export is a file download (Content-Disposition: attachment).
export const exportChildData = async (childUid: string, token: string): Promise<Blob> => {
  const res = await fetch(`/api/v1/family/children/${childUid}/export`, {
    headers: authHeaders(token),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

// ── Self consent record + re-consent (any user) ──────────────────────────────

export interface MyConsent {
  account_status?: string
  consent_given_at?: string | null
  consent_version?: string | null
  jurisdiction?: string | null
  current_policy_version: string
  needs_reconsent: boolean
}

export const getMyConsent = (token: string): Promise<MyConsent> =>
  request('/api/v1/users/me/consent', undefined, token)

export const reconsentSelf = (token: string): Promise<{ status: string; policy_version: string }> =>
  request('/api/v1/users/me/reconsent', { method: 'POST' }, token)

// ── Consent confirmation page (public + pending-child endpoints) ─────────────

export interface ConsentStatusResponse {
  status: 'pending_review' | 'already_confirmed' | 'refused'
  message?: string
  child_name?: string | null
  parent_email?: string | null
}

export const getConsentStatus = (consentToken: string): Promise<ConsentStatusResponse> =>
  request(`/api/v1/users/consent/confirm?token=${encodeURIComponent(consentToken)}`)

export interface ConsentDecisionResponse {
  status: 'confirmed' | 'refused' | 'already_confirmed' | 'verification_required'
  message: string
}

export const decideConsent = (consentToken: string, approved: boolean): Promise<ConsentDecisionResponse> =>
  request('/api/v1/users/consent/confirm', {
    method: 'POST',
    body: JSON.stringify({ token: consentToken, approved }),
  })

export const resendConsentEmail = (token: string): Promise<{ status: string; parent_email: string }> =>
  request('/api/v1/users/consent/resend', { method: 'POST' }, token)

export const reportConsent = (childUid: string, reportToken: string): Promise<{ status: string; message: string }> =>
  request('/api/v1/users/consent/report', {
    method: 'POST',
    body: JSON.stringify({ child_uid: childUid, token: reportToken }),
  })

// ── Family profiles: picker, parent PIN, claim ───────────────────────────────
// Contract: backend/plans/family-profiles/README.md.

export interface PickerAccount {
  uid: string
  display_name: string | null
  photo_url: string | null
  avatar: string | null
  profile_type: ProfileType
}

export interface PickerProfile {
  uid: string
  display_name: string | null
  avatar: string | null
  age_group: 'teen' | 'child' | 'adult' | null
  account_status: string
  paused: boolean
  onboarding_done: boolean
  chat_enabled: boolean
  verification_required: boolean | null
}

export interface ProfilesResponse {
  account: PickerAccount
  profiles: PickerProfile[]
  pin_set: boolean
}

export const getProfiles = (token: string): Promise<ProfilesResponse> =>
  request('/api/v1/family/profiles', undefined, token)

export const setParentPin = (pin: string, currentPin: string | null, token: string): Promise<{ pin_set: boolean }> =>
  request('/api/v1/family/pin', {
    method: 'POST',
    body: JSON.stringify(currentPin ? { pin, current_pin: currentPin } : { pin }),
  }, token)

export const verifyParentPin = (pin: string, token: string): Promise<{ unlock_token: string; expires_in: number }> =>
  request('/api/v1/family/pin/verify', { method: 'POST', body: JSON.stringify({ pin }) }, token)

// Needs a token from a sign-in within the last 5 minutes (re-auth with Google first).
export const resetParentPin = (pin: string, token: string): Promise<{ pin_set: boolean }> =>
  request('/api/v1/family/pin/reset', { method: 'POST', body: JSON.stringify({ pin }) }, token)

export interface ClaimInvite {
  code: string
  claim_url: string
  expires_at: string
}

export const createClaimInvite = (childUid: string, token: string): Promise<ClaimInvite> =>
  request(`/api/v1/family/children/${childUid}/claim-invite`, { method: 'POST' }, token)

export const claimProfile = (code: string, token: string): Promise<{ status: string; uid: string }> =>
  request('/api/v1/users/claim', { method: 'POST', body: JSON.stringify({ code }) }, token)
