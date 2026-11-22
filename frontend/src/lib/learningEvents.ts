// Learning funnel events (backend/plans/feature-improvements F1.2): where do
// learners stop? Batched, best-effort, never throws. Nothing is sent for school
// students or guests (no token) and the payloads carry no free text.
import { useEffect, useRef } from 'react'
import { authHeaders } from './api'
import { isStudentSession } from './telemetryPrivacy'

const BASE = import.meta.env.VITE_API_URL || ''
const MAX_BATCH = 20
const FLUSH_MS = 10_000

export type LearningEventName =
  | 'step_open' | 'step_scroll_50' | 'step_scroll_90' | 'step_time'
  | 'quiz_view' | 'quiz_ready' | 'quiz_answer' | 'quiz_skip'
  | 'review_answer' | 'notification_click'

interface Queued {
  event: LearningEventName
  journey_id?: string
  step_id?: string
  props?: Record<string, number | string | boolean>
}

type TokenGetter = () => Promise<string | null>

const queue: Queued[] = []
let tokenGetter: TokenGetter | null = null
let timer: number | undefined
let listening = false

export async function flushLearningEvents(): Promise<void> {
  if (timer !== undefined) { window.clearTimeout(timer); timer = undefined }
  while (queue.length && tokenGetter) {
    const batch = queue.splice(0, MAX_BATCH)
    try {
      const token = await tokenGetter()
      if (!token) return
      await fetch(`${BASE}/api/v1/events`, {
        method: 'POST',
        keepalive: true,
        headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
        body: JSON.stringify({ events: batch }),
      })
    } catch {
      // telemetry must never break the page
    }
  }
}

function listen() {
  if (listening || typeof document === 'undefined') return
  listening = true
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void flushLearningEvents()
  })
  window.addEventListener('pagehide', () => { void flushLearningEvents() })
}

export function trackLearning(
  getToken: TokenGetter,
  event: LearningEventName,
  ctx: { journeyId?: string; stepId?: string; props?: Queued['props'] } = {},
): void {
  if (isStudentSession()) return
  tokenGetter = getToken
  listen()
  queue.push({ event, journey_id: ctx.journeyId, step_id: ctx.stepId, props: ctx.props })
  if (queue.length >= MAX_BATCH) void flushLearningEvents()
  else if (timer === undefined) timer = window.setTimeout(() => { void flushLearningEvents() }, FLUSH_MS)
}

/**
 * While `active`, report how far the learner scrolled through `contentRef`
 * (50% and 90% once each) and, when it ends, how many seconds the step was
 * on screen with the tab visible.
 */
export function useStepEngagement(
  active: boolean,
  journeyId: string,
  stepId: string,
  getToken: TokenGetter,
  contentRef: React.RefObject<HTMLElement>,
): void {
  const getTokenRef = useRef(getToken)
  getTokenRef.current = getToken

  useEffect(() => {
    if (!active) return
    const send: typeof trackLearning = (_g, event, ctx) => trackLearning(getTokenRef.current, event, ctx)
    send(getTokenRef.current, 'step_open', { journeyId, stepId })

    const fired = new Set<string>()
    const onScroll = () => {
      const el = contentRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      if (rect.height <= 0) return
      const seen = Math.min(1, Math.max(0, (window.innerHeight - rect.top) / rect.height))
      for (const [pct, name] of [[0.5, 'step_scroll_50'], [0.9, 'step_scroll_90']] as const) {
        if (seen >= pct && !fired.has(name)) {
          fired.add(name)
          send(getTokenRef.current, name, { journeyId, stepId })
        }
      }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    const first = window.setTimeout(onScroll, 1500) // short lessons are fully on screen already

    let visibleMs = 0
    let since = document.visibilityState === 'visible' ? Date.now() : 0
    const onVisibility = () => {
      if (document.visibilityState === 'visible') since = Date.now()
      else if (since) { visibleMs += Date.now() - since; since = 0 }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      window.removeEventListener('scroll', onScroll)
      window.clearTimeout(first)
      document.removeEventListener('visibilitychange', onVisibility)
      if (since) visibleMs += Date.now() - since
      const seconds = Math.round(visibleMs / 1000)
      if (seconds >= 2) send(getTokenRef.current, 'step_time', { journeyId, stepId, props: { seconds: Math.min(seconds, 3600) } })
    }
  }, [active, journeyId, stepId, contentRef])
}
