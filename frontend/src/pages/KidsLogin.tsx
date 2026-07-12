import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Rocket } from 'lucide-react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'

export default function KidsLogin() {
  const { signInWithEmail, user } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      await signInWithEmail(email.trim(), password)
      navigate('/learn', { replace: true })
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? ''
      if (code === 'auth/invalid-credential' || code === 'auth/wrong-password' || code === 'auth/user-not-found') {
        setError("That email or password doesn't match. Ask your parent to double-check!")
      } else if (code === 'auth/too-many-requests') {
        setError('Too many tries — wait a little while, then try again.')
      } else {
        setError("Couldn't sign you in. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  if (user) {
    navigate('/learn', { replace: true })
    return null
  }

  return (
    <>
      <PageMeta title="Kids Login" description="Sign in to ECALT with the family account your parent created." />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4 pt-24 pb-16">
        <div className="glass-card rounded-3xl p-8 max-w-sm w-full shadow-2xl">
          <div className="text-center mb-6">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
              <Rocket size={28} className="text-violet-600 dark:text-violet-400" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">Welcome back, explorer!</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Sign in with the email and password your parent gave you.
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label htmlFor="kids-email" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Your email</label>
              <input
                id="kids-email"
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); if (error) setError(null) }}
                placeholder="you@example.com"
                autoComplete="username"
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
            </div>
            <div className="mb-4">
              <label htmlFor="kids-password" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Your password</label>
              <input
                id="kids-password"
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); if (error) setError(null) }}
                autoComplete="current-password"
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
            </div>

            {error && <p className="mb-3 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

            <button
              type="submit"
              disabled={loading || !email.trim() || !password}
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? <><Loader2 size={14} className="animate-spin" /> Signing in…</> : "Let's go! 🚀"}
            </button>
          </form>

          <p className="mt-4 text-xs text-center text-slate-400 dark:text-slate-500">
            Forgot your password? Ask your parent — they can help from their{' '}
            <Link to="/parents" className="underline hover:text-slate-600 dark:hover:text-slate-300">Family dashboard</Link>.
          </p>
        </div>
      </div>
    </>
  )
}
