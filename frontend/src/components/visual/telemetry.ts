import { postVisualEvent } from '../../lib/api'
import type { VisualEventType } from '../../lib/types'

// Per-tab session id for visual telemetry — separate from the anonymous
// spark session id (ecalt_sid), which tracks something unrelated (spark rate
// limiting) and persists across tabs via localStorage.
function getVisualSessionId(): string {
  const key = 'ecalt_visual_sid'
  let id = sessionStorage.getItem(key) || ''
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem(key, id)
  }
  return id
}

// Best-effort, fire-and-forget — a telemetry failure must never surface to
// the learner. Safe to call unconditionally: the backend endpoint always
// returns 200 whether or not VISUAL_TELEMETRY_ENABLED is on.
export function emitVisualEvent(
  journeyId: string,
  stepId: string,
  vloId: string,
  eventType: VisualEventType,
  getToken: () => Promise<string | null>,
  eventData: Record<string, unknown> = {},
): void {
  getToken()
    .then(token => {
      if (!token) return
      return postVisualEvent(
        journeyId, stepId,
        { eventType, vloId, sessionId: getVisualSessionId(), eventData },
        token,
      )
    })
    .catch(() => { /* best-effort */ })
}
