import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { useAuth } from './AuthContext'
import { setImpersonationSessionId } from './impersonationStore'

interface ImpersonationSession {
  sessionId: string
  targetUid: string
  targetName: string
  expiresAt: Date
}

interface ImpersonationContextValue {
  session: ImpersonationSession | null
  startImpersonation: (targetUid: string, targetName: string, reason?: string) => Promise<void>
  stopImpersonation: () => Promise<void>
}

const ImpersonationContext = createContext<ImpersonationContextValue>({
  session: null,
  startImpersonation: async () => {},
  stopImpersonation: async () => {},
})

export function ImpersonationProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth()
  const [session, setSession] = useState<ImpersonationSession | null>(null)
  const expiryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearExpiryTimer = () => {
    if (expiryTimerRef.current) {
      clearTimeout(expiryTimerRef.current)
      expiryTimerRef.current = null
    }
  }

  useEffect(() => {
    return clearExpiryTimer
  }, [])

  const startImpersonation = useCallback(async (targetUid: string, targetName: string, reason?: string) => {
    const token = await getToken()
    if (!token) return
    const res = await fetch(`/api/v1/admin/impersonate/${targetUid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ reason: reason ?? null }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail ?? 'Failed to start impersonation session')
    }
    const data = await res.json()
    const expiresAt = new Date(data.expires_at)

    clearExpiryTimer()
    expiryTimerRef.current = setTimeout(() => {
      setImpersonationSessionId(null)
      setSession(null)
    }, expiresAt.getTime() - Date.now())

    setImpersonationSessionId(data.session_id)
    setSession({ sessionId: data.session_id, targetUid, targetName, expiresAt })
  }, [getToken])

  const stopImpersonation = useCallback(async () => {
    if (!session) return
    clearExpiryTimer()
    const token = await getToken()
    if (token) {
      // Best-effort — don't block UI on network failure
      fetch(`/api/v1/admin/impersonate/${session.sessionId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    setImpersonationSessionId(null)
    setSession(null)
  }, [session, getToken])

  return (
    <ImpersonationContext.Provider value={{ session, startImpersonation, stopImpersonation }}>
      {children}
    </ImpersonationContext.Provider>
  )
}

export const useImpersonation = () => useContext(ImpersonationContext)
