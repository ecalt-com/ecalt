import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, ShieldAlert, CheckCircle, XCircle } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import { apiErrorCode } from '../lib/api'
import { reportConsent } from '../lib/familyApi'

// Target of the email-plus follow-up email's "this wasn't me" link:
// /consent/report?child={uid}&token={hmac}. The click below is the whole
// point — nothing is auto-submitted on load.
export default function ConsentReport() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const childUid = params.get('child')
  const token = params.get('token')

  const [phase, setPhase] = useState<'confirm' | 'reported' | 'invalid'>(childUid && token ? 'confirm' : 'invalid')
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleReport = async () => {
    if (!childUid || !token || submitting) return
    setSubmitting(true)
    try {
      const data = await reportConsent(childUid, token)
      setMessage(data.message)
      setPhase('reported')
    } catch (err: unknown) {
      if (apiErrorCode(err) === 'invalid_token') {
        setPhase('invalid')
      } else {
        setMessage('Something went wrong. Please try again, or email support@ecalt.com.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageMeta title="Report an approval" description="Report a parental consent approval that you did not make." />
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
        <div className="glass-card rounded-3xl p-8 max-w-sm w-full shadow-2xl text-center">
          {phase === 'confirm' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-100 dark:bg-rose-500/15 flex items-center justify-center">
                <ShieldAlert size={28} className="text-rose-600 dark:text-rose-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Didn't approve this account?</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                We recorded an approval of a child's ECALT account under your email address.
                If that wasn't you, we'll suspend the account immediately and our team will follow up.
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-6">
                If you did approve it, you can simply close this page.
              </p>
              {message && <p className="mb-3 text-xs text-rose-600 dark:text-rose-400" role="alert">{message}</p>}
              <button
                onClick={handleReport}
                disabled={submitting}
                className="w-full px-4 py-2.5 rounded-xl text-sm font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {submitting ? <Loader2 size={14} className="animate-spin" /> : null}
                Yes, suspend this account
              </button>
            </>
          )}

          {phase === 'reported' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle size={28} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Account suspended</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">{message}</p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">Go to ECALT</button>
            </>
          )}

          {phase === 'invalid' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-100 dark:bg-rose-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-rose-600 dark:text-rose-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Invalid link</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                This report link is invalid. If you still have a concern, email{' '}
                <a href="mailto:support@ecalt.com" className="underline text-violet-600 dark:text-violet-400">support@ecalt.com</a>.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">Go to ECALT</button>
            </>
          )}
        </div>
      </div>
    </>
  )
}
