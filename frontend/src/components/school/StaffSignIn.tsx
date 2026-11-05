import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../../lib/AuthContext'
import { MICROSOFT_SIGNIN_ENABLED } from '../../lib/firebase'

// Staff sign-in: Google, plus Microsoft work/school accounts when enabled (D8).
function message(code?: string): string | null {
  switch (code) {
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request': return null
    case 'auth/account-exists-with-different-credential':
      return 'This email already signs in with another provider. Use that one (for example Continue with Google).'
    case 'auth/operation-not-allowed': return "Microsoft sign-in isn't switched on yet. Use Google for now."
    case 'auth/popup-blocked': return 'Your browser blocked the sign-in window. Allow pop-ups for this site and try again.'
    default: return 'Sign-in failed. Please try again.'
  }
}

export default function StaffSignIn() {
  const { signIn } = useAuth()
  const [busy, setBusy] = useState<'google' | 'microsoft' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const go = async (provider: 'google' | 'microsoft') => {
    setBusy(provider); setError(null)
    try { await signIn(provider) } catch (err) { setError(message((err as { code?: string }).code)) }
    finally { setBusy(null) }
  }
  return (
    <div className="space-y-2.5">
      <button onClick={() => go('google')} disabled={busy !== null} className="w-full btn-primary flex items-center justify-center gap-2">
        {busy === 'google' && <Loader2 size={14} className="animate-spin" />} Continue with Google
      </button>
      {MICROSOFT_SIGNIN_ENABLED && (
        <button onClick={() => go('microsoft')} disabled={busy !== null} data-testid="microsoft-sign-in"
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/70 text-slate-700 dark:text-slate-200 text-sm font-medium disabled:opacity-50">
          {busy === 'microsoft' ? <Loader2 size={14} className="animate-spin" /> : (
            <svg width="14" height="14" viewBox="0 0 21 21" aria-hidden="true">
              <rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect x="11" y="1" width="9" height="9" fill="#7fba00" />
              <rect x="1" y="11" width="9" height="9" fill="#00a4ef" /><rect x="11" y="11" width="9" height="9" fill="#ffb900" />
            </svg>
          )} Continue with Microsoft
        </button>
      )}
      {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
    </div>
  )
}
