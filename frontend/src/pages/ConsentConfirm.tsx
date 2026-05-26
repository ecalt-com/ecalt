import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'
import PageMeta from '../components/PageMeta'

export default function ConsentConfirm() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token')

  const [status, setStatus] = useState<'loading' | 'success' | 'expired' | 'invalid'>('loading')

  useEffect(() => {
    if (!token) { setStatus('invalid'); return }
    fetch(`/api/v1/users/consent/confirm?token=${encodeURIComponent(token)}`)
      .then(r => {
        if (r.ok) { setStatus('success'); return }
        return r.json().then(body => {
          const detail = typeof body?.detail === 'string' ? body.detail : ''
          setStatus(detail.includes('expired') ? 'expired' : 'invalid')
        })
      })
      .catch(() => setStatus('invalid'))
  }, [token])

  return (
    <>
      <PageMeta title="Parental Consent Confirmation" description="Confirm your child's ECALT account." />
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
        <div className="glass-card rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl">
          {status === 'loading' && (
            <>
              <Loader2 size={32} className="mx-auto mb-4 text-violet-500 animate-spin" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Confirming…</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle size={28} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Account approved!</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                Your child can now log in and start learning on ECALT.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </>
          )}

          {status === 'expired' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-amber-600 dark:text-amber-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Link expired</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                This link has expired. Please ask your child to request a new one by signing in again.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </>
          )}

          {status === 'invalid' && (
            <>
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-100 dark:bg-rose-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-rose-600 dark:text-rose-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Invalid link</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                This confirmation link is invalid. Please ask your child to sign up again to send a new link.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </>
          )}
        </div>
      </div>
    </>
  )
}
