import { useState } from 'react'
import { Loader2, CheckCircle } from 'lucide-react'
import { useAuth } from '../../lib/AuthContext'

interface Props {
  onSent: (parentEmail: string) => void
}

export default function ParentalConsentForm({ onSent }: Props) {
  const { submitParentalConsent, signOut } = useAuth()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    const trimmed = email.trim()
    if (!trimmed || !trimmed.includes('@')) {
      setError('Enter a valid email address.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await submitParentalConsent(trimmed)
      onSent(trimmed)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-3xl mb-3">📧</div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">One more step</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Because you're under 18, we need a parent or guardian to approve your account.
          </p>
        </div>

        <div className="mb-3">
          <label htmlFor="parent-email" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
            Parent/Guardian email
          </label>
          <input
            id="parent-email"
            type="email"
            value={email}
            onChange={e => { setEmail(e.target.value); if (error) setError(null) }}
            placeholder="parent@example.com"
            aria-describedby={error ? 'parent-email-error' : undefined}
            className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
          />
          {error && (
            <p id="parent-email-error" className="mt-1.5 text-xs text-rose-600 dark:text-rose-400" role="alert">
              {error}
            </p>
          )}
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          We'll send them a quick confirmation email. Your account will be ready once they confirm.
        </p>

        <button
          onClick={handleSubmit}
          disabled={loading || !email.trim()}
          className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading
            ? <><Loader2 size={14} className="animate-spin" /> Sending…</>
            : 'Send Confirmation Email'}
        </button>

        <p className="mt-4 text-xs text-center text-slate-400 dark:text-slate-500">
          By continuing you agree to our{' '}
          <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600 dark:hover:text-slate-400">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600 dark:hover:text-slate-400">
            Privacy Policy
          </a>.
        </p>

        <button
          onClick={() => signOut()}
          className="w-full mt-3 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-1 transition-colors"
        >
          Sign out
        </button>
      </div>
    </div>
  )
}

interface SentProps {
  parentEmail: string
  onSignOut: () => void
}

export function ConsentSentScreen({ parentEmail, onSignOut }: SentProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="glass-card rounded-3xl p-8 max-w-sm w-full shadow-2xl text-center">
        <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
          <CheckCircle size={24} className="text-emerald-600 dark:text-emerald-400" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Email sent!</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-1">
          We've emailed your parent at
        </p>
        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 mb-4 break-all">{parentEmail}</p>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-1">
          Once they confirm, you'll be able to start learning on ECALT.
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-6">The link expires in 7 days.</p>
        <button onClick={onSignOut} className="w-full btn-primary">
          Sign out
        </button>
      </div>
    </div>
  )
}
