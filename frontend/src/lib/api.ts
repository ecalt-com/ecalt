import type { Journey, JourneysResponse, ExploreRequest, SparkRequest, SparkResponse, SessionStatus, QuizQuestion, QuizSet, QuizHint, QuizResult } from './types'
export type { LearnerPurpose, TopicExpertise, QuizVerdict } from './types'
import { getImpersonationSessionId } from './impersonationStore'

// In production, Vercel rewrites /api/* → Railway (no env var needed, no mixed-content).
// In local dev, the Vite proxy forwards /api/* → localhost:8000.
// VITE_API_URL can still override both (e.g. to hit Railway directly from dev).
const BASE = import.meta.env.VITE_API_URL || ''

export interface ApiError extends Error {
  status: number
  detail: unknown
}

// detail.error code from a structured {error, message} error body, or null.
export function apiErrorCode(err: unknown): string | null {
  const detail = (err as ApiError)?.detail
  if (detail && typeof detail === 'object' && 'error' in detail) {
    return String((detail as { error: unknown }).error)
  }
  return null
}

export async function request<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const impersonationId = getImpersonationSessionId()
  if (impersonationId) headers['X-Impersonate-Session'] = impersonationId

  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Unknown error' }))
    const err = new Error(
      typeof body.detail === 'string' ? body.detail : (body.detail?.message ?? `Request failed: ${res.status}`)
    ) as ApiError
    err.status = res.status
    err.detail = body.detail
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const askSpark = (body: SparkRequest, token?: string): Promise<SparkResponse> =>
  request('/api/v1/spark', { method: 'POST', body: JSON.stringify(body) }, token)

export const getSessionStatus = (sessionId: string): Promise<SessionStatus> =>
  request(`/api/v1/session/${encodeURIComponent(sessionId)}`)

export const exploreQuestion = (body: ExploreRequest, token: string): Promise<{ journey: Journey }> =>
  request('/api/v1/explore', { method: 'POST', body: JSON.stringify(body) }, token)

export const previewJourney = (body: ExploreRequest, token: string): Promise<{ preview_token: string; journey: Journey }> =>
  request('/api/v1/explore/preview', { method: 'POST', body: JSON.stringify(body) }, token)

export const confirmJourney = (preview_token: string, token: string): Promise<{ journey: Journey }> =>
  request('/api/v1/explore/confirm', { method: 'POST', body: JSON.stringify({ preview_token }) }, token)

export const getJourneys = (token?: string): Promise<JourneysResponse> =>
  request('/api/v1/journeys', undefined, token)

export const getJourney = (id: string, token?: string): Promise<Journey> =>
  request(`/api/v1/journeys/${id}`, undefined, token)

export interface JourneySuggestions {
  next_level: Journey | null
  similar: Journey[]
  next_level_generated: boolean
}

// Post-completion suggestions — next level of the same course + similar courses,
// excluding everything the user has completed, started, or authored.
export const getJourneySuggestions = (journeyId: string, token: string): Promise<JourneySuggestions> =>
  request(`/api/v1/journeys/${journeyId}/suggestions`, undefined, token)

export interface MarketplaceFilters {
  age_group?: string
  difficulty?: string
  tag?: string
  limit?: number
  offset?: number
}

export interface MarketplaceResponse {
  journeys: Journey[]
  total: number
  limit: number
  offset: number
}

export const getMarketplace = (filters: MarketplaceFilters = {}, token?: string): Promise<MarketplaceResponse> => {
  const params = new URLSearchParams()
  if (filters.age_group) params.set('age_group', filters.age_group)
  if (filters.difficulty) params.set('difficulty', filters.difficulty)
  if (filters.tag) params.set('tag', filters.tag)
  params.set('limit', String(filters.limit ?? 20))
  params.set('offset', String(filters.offset ?? 0))
  return request(`/api/v1/journeys/marketplace?${params}`, undefined, token)
}

export const toggleJourneyLike = (journeyId: string, token: string): Promise<{ liked: boolean; like_count: number }> =>
  request(`/api/v1/journeys/${journeyId}/like`, { method: 'POST' }, token)

export const forkJourney = (journeyId: string, token: string): Promise<{ journey: Journey }> =>
  request(`/api/v1/journeys/${journeyId}/fork`, { method: 'POST' }, token)

export const getProgress = (journeyId: string, token: string): Promise<{ journey_id: string; completed_step_ids: string[] }> =>
  request(`/api/v1/progress/${journeyId}`, undefined, token)

export const markStepComplete = (journeyId: string, stepId: string, token: string): Promise<void> =>
  request(`/api/v1/progress/${journeyId}/${stepId}`, { method: 'POST' }, token)

export const markStepIncomplete = (journeyId: string, stepId: string, token: string): Promise<void> =>
  request(`/api/v1/progress/${journeyId}/${stepId}`, { method: 'DELETE' }, token)

export interface PassportData {
  journeys: {
    id: string; title: string; icon: string; category: string
    completed_steps: number; total_steps: number; completed_at: string; fully_completed: boolean
  }[]
  total_completed: number
  total_in_progress: number
  categories: string[]
  estimated_hours: number
}

export const getPassport = (token: string): Promise<PassportData> =>
  request('/api/v1/passport', undefined, token)

export interface StepContent {
  journey_id: string
  step_id: string
  content: string
  cached: boolean
}

export const getStepContent = (journeyId: string, stepId: string, token?: string): Promise<StepContent> =>
  request(`/api/v1/journeys/${journeyId}/steps/${stepId}/content`, undefined, token)

// Synchronous full rewrite of a step's content (rate-limited server-side).
export const regenerateStepContent = (journeyId: string, stepId: string, token: string): Promise<StepContent> =>
  request(`/api/v1/journeys/${journeyId}/steps/${stepId}/content/regenerate`, { method: 'POST' }, token)

export type StepFeedbackTag = 'too_generic' | 'too_basic' | 'too_advanced' | 'inaccurate' | 'loved_it'

export interface StepFeedbackResponse {
  ok: boolean
  // true when a negative tag triggered a background rewrite of the step
  regenerating: boolean
}

export const submitStepFeedback = (
  journeyId: string,
  stepId: string,
  body: { rating: 'up' | 'down'; tag?: StepFeedbackTag; comment?: string },
  token: string,
): Promise<StepFeedbackResponse> =>
  request(`/api/v1/journeys/${journeyId}/steps/${stepId}/feedback`, { method: 'POST', body: JSON.stringify(body) }, token)

export interface UserProfile {
  uid: string
  email?: string
  display_name?: string
  photo_url?: string
  onboarding_done: boolean
  streak_days: number
  whatsapp_opted_in?: boolean
  has_notification_prefs?: boolean
  profession?: string
  role?: 'learner' | 'parent'
  account_status?: string
  consent_given_at?: string | null
  consent_status?: string | null
  birth_year?: number | null
  birth_month?: number | null
}

// ── Notification preferences ──────────────────────────────────────────────────

export interface NotificationPreferences {
  email_enabled: boolean
  whatsapp_enabled: boolean
  whatsapp_opted_in: boolean
  whatsapp_phone: string | null
  whatsapp_declined_onboarding: boolean
  whatsapp_nudge_last_dismissed: string | null
  quiet_hours_start: number
  quiet_hours_end: number
  timezone: string
  preferred_channel: 'email' | 'whatsapp'
}

export interface NotificationPreferencesPatch {
  email_enabled?: boolean
  whatsapp_enabled?: boolean
  whatsapp_phone?: string | null
  whatsapp_declined_onboarding?: boolean
  whatsapp_nudge_dismissed?: boolean
  quiet_hours_start?: number
  quiet_hours_end?: number
  timezone?: string
  preferred_channel?: 'email' | 'whatsapp'
}

export const getNotificationPrefs = (token: string): Promise<NotificationPreferences> =>
  request('/api/v1/notifications/preferences', undefined, token)

export const saveNotificationPrefs = (
  patch: NotificationPreferencesPatch,
  token: string,
): Promise<NotificationPreferences> =>
  request('/api/v1/notifications/preferences', { method: 'PATCH', body: JSON.stringify(patch) }, token)

export const optInWhatsApp = (phone: string, token: string): Promise<NotificationPreferences> =>
  request('/api/v1/notifications/whatsapp/opt-in', { method: 'POST', body: JSON.stringify({ phone }) }, token)

export const confirmWhatsApp = (phone: string, token: string): Promise<NotificationPreferences> =>
  request('/api/v1/notifications/whatsapp/confirm', { method: 'POST', body: JSON.stringify({ phone }) }, token)

export const optOutWhatsApp = (token: string): Promise<NotificationPreferences> =>
  request('/api/v1/notifications/preferences/whatsapp', { method: 'DELETE' }, token)

export const getUserProfile = (token: string): Promise<UserProfile> =>
  request('/api/v1/users/me', undefined, token)

export const completeOnboarding = (token: string): Promise<UserProfile> =>
  request('/api/v1/users/me/onboarding', { method: 'PATCH' }, token)

export const saveProfession = (profession: string, token: string): Promise<{ saved: boolean }> =>
  request('/api/v1/users/me/profession', { method: 'PATCH', body: JSON.stringify({ profession }) }, token)

// ── Chat / Knowledge ──────────────────────────────────────────────────────────

export interface Conversation {
  id: string
  title: string | null
  started_at: string
  last_active: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface KnowledgeNode {
  concept: string
  domain: string
  strength: number
  discovered_at: string
  last_reinforced: string
}

export const getConversations = (token: string): Promise<{ conversations: Conversation[] }> =>
  request('/api/v1/chat/conversations', undefined, token)

export const getConversation = (id: string, token: string): Promise<{ messages: ChatMessage[] }> =>
  request(`/api/v1/chat/conversations/${id}`, undefined, token)

export const deleteConversation = (id: string, token: string): Promise<{ deleted: boolean }> =>
  request(`/api/v1/chat/conversations/${id}`, { method: 'DELETE' }, token)

export const getKnowledgeNodes = (token: string): Promise<{ nodes: KnowledgeNode[] }> =>
  request('/api/v1/knowledge/nodes', undefined, token)

export const getDailySpark = (token: string): Promise<{ spark: string }> =>
  request('/api/v1/knowledge/spark', undefined, token)

// ── Quiz ─────────────────────────────────────────────────────────────────────

export const generateQuiz = (
  body: { concept: string; context: string; base_depth?: string },
  token: string,
): Promise<QuizQuestion> =>
  request('/api/v1/quiz', { method: 'POST', body: JSON.stringify(body) }, token)

// Multi-question quiz set for a journey step — passing it is what completes the step.
export const generateQuizSet = (
  body: {
    concept: string
    context: string
    journey_id: string
    step_id: string
    base_depth?: string
    num_questions?: number
  },
  token: string,
): Promise<QuizSet> =>
  request('/api/v1/quiz', { method: 'POST', body: JSON.stringify(body) }, token)

export const getQuizHint = (quizId: string, token: string): Promise<QuizHint> =>
  request(`/api/v1/quiz/${quizId}/hint`, { method: 'POST' }, token)

// Explicitly skip a step's quiz — opens the step's completion gate server-side.
export const skipStepQuiz = (journeyId: string, stepId: string, token: string): Promise<{ skipped: boolean }> =>
  request(`/api/v1/quiz/step-skip/${journeyId}/${stepId}`, { method: 'POST' }, token)

export const submitQuizAnswer = (
  quizId: string,
  body: { user_answer: string },
  token: string,
): Promise<QuizResult> =>
  request(`/api/v1/quiz/${quizId}/submit`, { method: 'POST', body: JSON.stringify(body) }, token)
