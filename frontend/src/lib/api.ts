import type { Journey, JourneysResponse, ExploreRequest, SparkRequest, SparkResponse } from './types'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
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

export const askSpark = (body: SparkRequest): Promise<SparkResponse> =>
  request('/api/v1/spark', { method: 'POST', body: JSON.stringify(body) })

export const exploreQuestion = (body: ExploreRequest): Promise<{ journey: Journey }> =>
  request('/api/v1/explore', { method: 'POST', body: JSON.stringify(body) })

export const getJourneys = (): Promise<JourneysResponse> =>
  request('/api/v1/journeys')

export const getJourney = (id: string): Promise<Journey> =>
  request(`/api/v1/journeys/${id}`)
