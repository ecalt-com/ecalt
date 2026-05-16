import type { Journey, JourneysResponse, ExploreRequest, SparkRequest, SparkResponse, SessionStatus } from './types'

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
