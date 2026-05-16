import type { Journey, JourneysResponse, ExploreRequest } from './types'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const exploreQuestion = (body: ExploreRequest): Promise<{ journey: Journey }> =>
  request('/api/v1/explore', { method: 'POST', body: JSON.stringify(body) })

export const getJourneys = (): Promise<JourneysResponse> =>
  request('/api/v1/journeys')

export const getJourney = (id: string): Promise<Journey> =>
  request(`/api/v1/journeys/${id}`)
