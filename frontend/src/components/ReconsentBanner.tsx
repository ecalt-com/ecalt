import { useEffect, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { getMyConsent, reconsentSelf } from '../lib/familyApi'

// Shown when the privacy policy version was bumped after the user's last
// consent (GET /users/me/consent → needs_reconsent). Accept → POST /me/reconsent.
export default function ReconsentBanner() {
  const { user, getToken } = useAuth()
  const [needed, setNeeded] = useState(false)
  const [policyVersion, setPolicyVersion] = useState<string | null>(null)
  const [accepting, setAccepting] = useState(false)

  useEffect(() => {
    if (!user) { setNeeded(false); return }
    let cancelled = false
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        const consent = await getMyConsent(token)
        if (!cancelled && consent.needs_reconsent) {
          setPolicyVersion(consent.current_policy_version)
          setNeeded(true)
        }
      } catch { /* non-critical */ }
    })()
    return () => { cancelled = true }
  }, [user, getToken])

  if (!needed) return null

  const handleAccept = async () => {
    setAccepting(true)
    try {
      const token = await getToken()
      if (!token) return
      await reconsentSelf(token)
      setNeeded(false)
    } catch { /* keep the banner; the user can retry */ } finally {
      setAccepting(false)
    }
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 px-4 pb-4 pointer-events-none">
      <div className="max-w-xl mx-auto glass-card rounded-2xl p-4 shadow-2xl border border-violet-200 dark:border-violet-500/30 flex items-center justify-between gap-3 flex-wrap pointer-events-auto">
        <p className="text-xs text-slate-700 dark:text-slate-300">
          Our{' '}
          <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline text-violet-600 dark:text-violet-400">privacy policy</a>{' '}
          has been updated{policyVersion ? ` (v${policyVersion})` : ''} — please review and accept to keep using ECALT.
        </p>
        <button
          onClick={handleAccept}
          disabled={accepting}
          className="shrink-0 btn-primary text-xs flex items-center gap-1.5 disabled:opacity-60"
        >
          {accepting ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Accept
        </button>
      </div>
    </div>
  )
}
