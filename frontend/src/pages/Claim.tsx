import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle, KeyRound, Loader2 } from 'lucide-react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { apiErrorCode, type ApiError } from '../lib/api'
import { claimProfile } from '../lib/familyApi'
import { setActiveProfile } from '../lib/profileStore'

// /claim?code=… — a teen attaches their own Google login to the profile their
// parent created, keeping all journeys and progress. AuthContext skips the
// new-account sign-up gates on this page.
export default function Claim() {
  const [params] = useSearchParams()
  const { user, loading: authLoading, signIn, signOut, getToken } = useAuth()
  const [code, setCode] = useState((params.get('code') ?? '').toUpperCase())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const handleClaim = async () => {
    if (busy || code.trim().length < 6) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Please sign in first.')
      await claimProfile(code.trim(), token)
      setActiveProfile(null)
      setDone(true)
    } catch (err) {
      const c = apiErrorCode(err)
      setError(
        c === 'invalid_claim_code' ? 'This code is invalid or has expired. Ask your parent for a new one.'
          : c === 'account_exists' ? (err as ApiError).message
            : (err as ApiError)?.message || 'Something went wrong. Please try again.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <PageMeta title="Get your own login" description="Link your Google account to your ECALT profile" />
      <Navigation />
      <main className="max-w-md mx-auto px-4 pt-32 pb-16">
        <div className="glass-card rounded-3xl p-6 sm:p-8">
          {done ? (
            <div className="text-center">
              <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle size={24} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">You're all set</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                From now on, sign in with this Google account. All your journeys and progress came with you.
              </p>
              <button onClick={() => window.location.assign('/learn')} className="w-full btn-primary">Start learning</button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <KeyRound size={18} className="text-violet-500" />
                <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Get your own login</h1>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
                Your parent gave you a code. Sign in with <strong>your own</strong> Google account, then enter
                the code to move your ECALT profile onto it.
              </p>

              {error && <p className="mb-4 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

              {authLoading ? (
                <div className="flex justify-center py-4"><Loader2 size={20} className="animate-spin text-violet-500" /></div>
              ) : !user ? (
                <button onClick={signIn} className="w-full btn-primary">Sign in with Google</button>
              ) : (
                <>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                    Signed in as <span className="font-medium text-slate-700 dark:text-slate-200">{user.email}</span>.{' '}
                    <button onClick={signOut} className="underline text-violet-600 dark:text-violet-400">Not you?</button>
                  </p>
                  <label htmlFor="claim-code" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Code from your parent</label>
                  <input
                    id="claim-code"
                    value={code}
                    onChange={e => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 16))}
                    onKeyDown={e => { if (e.key === 'Enter') handleClaim() }}
                    placeholder="ABCD2345"
                    autoComplete="off"
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-base tracking-widest text-center uppercase focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
                  />
                  <button
                    onClick={handleClaim}
                    disabled={busy || code.trim().length < 6}
                    className="w-full btn-primary mt-5 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {busy && <Loader2 size={14} className="animate-spin" />} Link my login
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
