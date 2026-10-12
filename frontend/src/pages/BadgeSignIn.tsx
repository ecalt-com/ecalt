import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { apiErrorCode } from '../lib/api'
import { badgeSignIn, schoolErrorMessage } from '../lib/schoolApi'

// /class/badge#<token> — QR badge sign-in (frontend-changes.md §6.3). The token
// sits in the URL fragment, which browsers never send to a server, and is
// removed from the address bar straight away.
export default function BadgeSignIn() {
  const navigate = useNavigate()
  const { user, loading, signOut, signInWithClassToken } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const token = useRef(window.location.hash.replace(/^#/, ''))
  const started = useRef(false)

  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname)
  }, [])

  useEffect(() => {
    if (loading || started.current) return
    if (!token.current) { setError('invalid_badge'); return }
    started.current = true
    ;(async () => {
      try {
        if (user) await signOut()     // a shared device: the badge holder takes over
        const session = await badgeSignIn(token.current)
        await signInWithClassToken(session.custom_token)
        navigate('/my-classes', { replace: true })
      } catch (err) {
        setError(apiErrorCode(err) ?? 'invalid_badge')
      }
    })()
  }, [loading, user, signOut, signInWithClassToken, navigate])

  return (
    <>
      <PageMeta title="Badge sign-in" />
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
        <div className="glass-card rounded-3xl p-8 max-w-sm w-full text-center">
          {error ? (
            <>
              <p className="text-sm text-rose-600 dark:text-rose-400 mb-5" role="alert">{schoolErrorMessage(error)}</p>
              <Link to="/class" className="btn-primary inline-block">Sign in with the class code</Link>
            </>
          ) : (
            <>
              <Loader2 className="animate-spin text-violet-500 mx-auto mb-3" />
              <p className="text-sm text-slate-600 dark:text-slate-300">Signing you in…</p>
            </>
          )}
        </div>
      </div>
    </>
  )
}
