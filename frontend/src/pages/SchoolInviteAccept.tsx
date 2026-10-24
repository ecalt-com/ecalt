import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, School as SchoolIcon } from 'lucide-react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { useSchool } from '../lib/SchoolContext'
import { useToast } from '../lib/ToastContext'
import { apiErrorCode } from '../lib/api'
import {
  acceptSchoolInvite, previewSchoolInvite, ROLE_LABEL, schoolErrorMessage, type InvitePreview,
} from '../lib/schoolApi'

// /school-invite?token=… (frontend-changes.md §3). The token is moved out of
// the URL straight away (history, screenshots, referrers) into localStorage so
// it survives the sign-out → sign-in round trip the invite often needs —
// including reopening the link in a new tab, restoring the tab, or a PWA cold
// start. sessionStorage is per-tab and dies with the session, so a bare
// /school-invite remount would lose the token ("this page needs the link")
// even though Firebase keeps you signed in (its own persistence is 'local').
// Cleared the moment the invite is accepted or turns out to be invalid/expired.
const TOKEN_KEY = 'ecalt.schoolInvite'

const storeToken = (t: string | null) => {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable — the token lives in memory only */ }
}
const storedToken = (): string | null => {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export default function SchoolInviteAccept() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { user, loading: authLoading, postSignInPhase, signIn, signOut, getToken } = useAuth()
  const { refresh: refreshSchools, setActiveSchool } = useSchool()
  const { addToast } = useToast()

  const [token] = useState<string | null>(() => {
    const fromUrl = params.get('token')
    if (fromUrl) storeToken(fromUrl)
    return fromUrl ?? storedToken()
  })
  const [preview, setPreview] = useState<InvitePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [accepting, setAccepting] = useState(false)

  useEffect(() => {
    if (params.get('token')) navigate('/school-invite', { replace: true })
  }, [params, navigate])

  useEffect(() => {
    if (!token) return
    previewSchoolInvite(token)
      .then(setPreview)
      .catch(err => {
        const code = apiErrorCode(err) ?? 'unknown'
        // A dead invite shouldn't linger in storage and reappear next visit.
        if (code === 'invite_invalid' || code === 'invite_expired') storeToken(null)
        setError(code)
      })
  }, [token])

  const accept = async () => {
    if (!token || accepting) return
    setAccepting(true)
    setError(null)
    try {
      const idToken = await getToken()
      if (!idToken) throw new Error('Session expired — please sign in again.')
      const joined = await acceptSchoolInvite(token, idToken)
      storeToken(null)
      await refreshSchools()
      setActiveSchool(joined.school_id)
      addToast(`Welcome to ${joined.school_name} ✓`)
      navigate('/school', { replace: true })
    } catch (err) {
      setError(apiErrorCode(err) ?? 'unknown')
    } finally {
      setAccepting(false)
    }
  }

  const switchAccount = async () => {
    setError(null)
    await signOut()
    await signIn()
  }

  const fatal = error === 'invite_invalid' || error === 'invite_expired'

  let body: React.ReactNode
  if (!token) {
    body = <p className="text-sm text-slate-600 dark:text-slate-400">This page needs the link from your invite email. Open the email and tap the button again.</p>
  } else if (fatal) {
    body = <p className="text-sm text-rose-600 dark:text-rose-400" role="alert">{schoolErrorMessage(error)}</p>
  } else if (!preview) {
    body = error
      ? <p className="text-sm text-rose-600 dark:text-rose-400" role="alert">{schoolErrorMessage(error)}</p>
      : <Loader2 className="animate-spin text-violet-500 mx-auto" />
  } else {
    body = (
      <>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-1">Join {preview.school_name}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
          You've been invited as {preview.role === 'teacher' ? 'a' : 'an'} {ROLE_LABEL[preview.role].toLowerCase()}.
          Sign in with the Google account for <strong>{preview.email_hint}</strong>.
        </p>

        {error && (
          <div className="mb-4 text-sm text-rose-600 dark:text-rose-400" role="alert">
            <p>{error === 'invite_email_mismatch'
              ? `You're signed in as ${user?.email ?? 'another account'}. This invite was sent to ${preview.email_hint}.`
              : schoolErrorMessage(error)}</p>
          </div>
        )}

        {authLoading ? (
          <Loader2 className="animate-spin text-violet-500 mx-auto" />
        ) : !user ? (
          <button onClick={signIn} className="w-full btn-primary">Sign in with Google</button>
        ) : postSignInPhase !== 'none' ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Finish setting up your account, then come back to this page.</p>
        ) : (
          <div className="space-y-3">
            <button onClick={accept} disabled={accepting} className="w-full btn-primary flex items-center justify-center gap-2">
              {accepting && <Loader2 size={14} className="animate-spin" />} Join as {user.email}
            </button>
            <button onClick={switchAccount} className="w-full text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400 dark:hover:text-violet-400 py-1">
              Use a different Google account
            </button>
          </div>
        )}
      </>
    )
  }

  return (
    <>
      <PageMeta title="School invite" />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4 flex justify-center">
        <div className="glass-card rounded-2xl p-8 max-w-md w-full text-center mt-10 h-fit">
          <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
            <SchoolIcon size={24} className="text-violet-600 dark:text-violet-400" />
          </div>
          {body}
        </div>
      </div>
    </>
  )
}
