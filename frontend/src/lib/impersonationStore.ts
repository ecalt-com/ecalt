// Module-level store so non-React code (api.ts) can read the active session ID
// without React context. Updated by ImpersonationContext on every session change.

let _sessionId: string | null = null

export function setImpersonationSessionId(id: string | null) {
  _sessionId = id
}

export function getImpersonationSessionId(): string | null {
  return _sessionId
}
