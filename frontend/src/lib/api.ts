import type { Journey, JourneysResponse, ExploreRequest, SparkRequest, SparkResponse, SessionStatus, QuizQuestion, QuizHint, QuizResult } from './types'

// In production, Vercel rewrites /api/* → Railway (no env var needed, no mixed-content).
// In local dev, the Vite proxy forwards /api/* → localhost:8000.
// VITE_API_URL can still override both (e.g. to hit Railway directly from dev).
const BASE = import.meta.env.VITE_API_URL || ''

async function request<T>(path: string, init?: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Unknown error' }))
    const err = new Error(
      typeof body.detail === 'string' ? body.detail : (body.detail?.message ?? `Request failed: ${res.status}`)
    ) as Error & { status: number; detail: unknown }
    err.status = res.status
    err.detail = body.detail
    throw err
  }
  return res.json()
}

export const askSpark = (body: SparkRequest, token?: string): Promise<SparkResponse> =>
  request('/api/v1/spark', { method: 'POST', body: JSON.stringify(body) }, token)

export const getSessionStatus = (sessionId: string): Promise<SessionStatus> =>
  request(`/api/v1/session/${encodeURIComponent(sessionId)}`)

export const exploreQuestion = (body: ExploreRequest, token: string): Promise<{ journey: Journey }> =>
  request('/api/v1/explore', { method: 'POST', body: JSON.stringify(body) }, token)

export const getJourneys = (token?: string): Promise<JourneysResponse> =>
  request('/api/v1/journeys', undefined, token)

export const getJourney = (id: string, token?: string): Promise<Journey> =>
  request(`/api/v1/journeys/${id}`, undefined, token)

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

export interface UserProfile {
  uid: string
  email?: string
  display_name?: string
  photo_url?: string
  onboarding_done: boolean
  streak_days: number
  whatsapp_opted_in?: boolean
  has_notification_prefs?: boolean
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

export const getQuizHint = (quizId: string, token: string): Promise<QuizHint> =>
  request(`/api/v1/quiz/${quizId}/hint`, { method: 'POST' }, token)

export const submitQuizAnswer = (
  quizId: string,
  body: { user_answer: string },
  token: string,
): Promise<QuizResult> =>
  request(`/api/v1/quiz/${quizId}/submit`, { method: 'POST', body: JSON.stringify(body) }, token)
