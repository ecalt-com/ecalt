import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { CheckCircle, XCircle, Loader2, ShieldCheck, CreditCard } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import GoogleSignInButton from '../components/GoogleSignInButton'
import { useAuth } from '../lib/AuthContext'
import { apiErrorCode, type ApiError } from '../lib/api'
import {
  getConsentStatus,
  decideConsent,
  approveLinkRequest,
  declineLinkRequest,
} from '../lib/familyApi'

type Phase =
  | 'loading'
  | 'review'            // pending_review — parent must decide
  | 'confirmed'
  | 'refused'
  | 'already_confirmed'
  | 'verification_required'
  | 'expired'
  | 'invalid'

export default function ConsentConfirm() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token')
  const { user, loading: authLoading, getToken } = useAuth()

  const [phase, setPhase] = useState<Phase>('loading')
  const [childName, setChildName] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [linkedToFamily, setLinkedToFamily] = useState(false)
  const [submitting, setSubmitting] = useState<'approve' | 'decline' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Read-only status check. Never approves anything — a human click below is
  // the entire point of this page.
  useEffect(() => {
    if (!token) { setPhase('invalid'); return }
    getConsentStatus(token)
      .then(data => {
        if (data.status === 'pending_review') {
          setChildName(data.child_name ?? null)
          setPhase('review')
        } else if (data.status === 'already_confirmed') {
          setMessage(data.message ?? null)
          setPhase('already_confirmed')
        } else {
          setMessage(data.message ?? null)
          setPhase('refused')
        }
      })
      .catch((err: unknown) => {
        setPhase(apiErrorCode(err) === 'token_expired' ? 'expired' : 'invalid')
      })
  }, [token])

  const decide = async (approved: boolean) => {
    if (!token || submitting) return
    setSubmitting(approved ? 'approve' : 'decline')
    setActionError(null)
    try {
      // Signed-in adults approve via the family endpoint — it also links the
      // child to their Family dashboard. Anonymous falls back to the plain
      // consent endpoint.
      const authToken = user ? await getToken() : null
      const data = authToken
        ? await (approved ? approveLinkRequest(token, authToken) : declineLinkRequest(token, authToken))
        : await decideConsent(token, approved)

      setMessage(data.message ?? null)
      if (data.status === 'confirmed') {
        setLinkedToFamily(Boolean(authToken))
        setPhase('confirmed')
      } else if (data.status === 'verification_required') {
        setLinkedToFamily(Boolean(authToken))
        setPhase('verification_required')
      } else if (data.status === 'already_confirmed') {
        setPhase('already_confirmed')
      } else {
        setPhase('refused')
      }
    } catch (err: unknown) {
      const code = apiErrorCode(err)
      if (code === 'token_expired') { setPhase('expired'); return }
      if (code === 'invalid_token') { setPhase('invalid'); return }
      if (code === 'self_approval' || code === 'consent_pending') {
        setActionError("This link is meant for your parent or guardian — you can't approve your own account. Please ask them to open the email.")
      } else if (code === 'adult_account_required' || code === 'no_account') {
        setActionError('Only an active adult account can approve from a signed-in session. Sign out and use "Approve without an account", or sign in with your own Google account.')
      } else {
        setActionError((err as ApiError)?.message || 'Something went wrong. Please try again.')
      }
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <>
      <PageMeta title="Parental Consent" description="Review and decide on your child's ECALT account." />
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4 py-10">
        <div className="glass-card rounded-3xl p-8 max-w-md w-full shadow-2xl">
          {phase === 'loading' && (
            <div className="text-center">
              <Loader2 size={32} className="mx-auto mb-4 text-violet-500 animate-spin" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Checking your link…</p>
            </div>
          )}

          {phase === 'review' && (
            <>
              <div className="text-center mb-5">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                  <ShieldCheck size={28} className="text-violet-600 dark:text-violet-400" />
                </div>
                <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">
                  {childName ? `${childName} wants to join ECALT` : 'Your child wants to join ECALT'}
                </h1>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Because they're under 18, we need your permission before their account becomes active.
                </p>
              </div>

              {/* Disclosure — same content as the consent email */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 p-4 mb-4 text-left">
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">If you approve, ECALT will collect:</p>
                <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 mb-3">
                  <li>• Their name and email from Google sign-in</li>
                  <li>• The learning questions they ask and the journeys they create</li>
                  <li>• AI-generated knowledge topics (their learning map)</li>
                </ul>
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">ECALT never:</p>
                <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 mb-3">
                  <li>• Sells data</li>
                  <li>• Shows ads</li>
                  <li>• Shares data with third parties for marketing</li>
                </ul>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Full details:{' '}
                  <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline text-violet-600 dark:text-violet-400">Terms of Service</a>
                  {' '}·{' '}
                  <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline text-violet-600 dark:text-violet-400">Privacy Policy</a>
                </p>
              </div>

              {!authLoading && !user && (
                <div className="mb-4">
                  <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">
                    <span className="font-semibold">Recommended:</span> sign in with Google to approve — you'll
                    also get a Family dashboard to see what your child is learning.
                  </p>
                  <GoogleSignInButton label="Sign in with Google to approve" />
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-2 text-center">
                    or decide without an account below
                  </p>
                </div>
              )}

              {actionError && (
                <p className="mb-3 text-xs text-rose-600 dark:text-rose-400" role="alert">{actionError}</p>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => decide(false)}
                  disabled={submitting !== null}
                  className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-rose-300 hover:text-rose-600 dark:hover:text-rose-400 transition-all disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {submitting === 'decline' ? <Loader2 size={14} className="animate-spin" /> : null}
                  Decline
                </button>
                <button
                  onClick={() => decide(true)}
                  disabled={submitting !== null}
                  className="flex-1 btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {submitting === 'approve' ? <Loader2 size={14} className="animate-spin" /> : null}
                  {user ? 'Approve account' : 'Approve without an account'}
                </button>
              </div>
            </>
          )}

          {phase === 'confirmed' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle size={28} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Account approved!</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                {message ?? 'Your child can now log in and start learning on ECALT.'}
              </p>
              {linkedToFamily ? (
                <button onClick={() => navigate('/family')} className="w-full btn-primary">
                  Go to Family dashboard
                </button>
              ) : (
                <button onClick={() => navigate('/')} className="w-full btn-primary">
                  Go to ECALT
                </button>
              )}
            </div>
          )}

          {phase === 'verification_required' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center">
                <CreditCard size={28} className="text-amber-600 dark:text-amber-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">One more step: verify your identity</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                {message ?? 'This region requires identity verification before the account activates.'}
              </p>
              {linkedToFamily ? (
                <button onClick={() => navigate('/family')} className="w-full btn-primary">
                  Verify from your Family dashboard
                </button>
              ) : (
                <GoogleSignInButton label="Sign in with Google to continue" />
              )}
            </div>
          )}

          {phase === 'refused' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-slate-100 dark:bg-slate-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-slate-500 dark:text-slate-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Consent declined</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                {message ?? 'Understood — the account will not be activated.'}
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </div>
          )}

          {phase === 'already_confirmed' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
                <CheckCircle size={28} className="text-emerald-600 dark:text-emerald-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Already approved</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                {message ?? 'This account is already active.'}
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </div>
          )}

          {phase === 'expired' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-amber-600 dark:text-amber-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Link expired</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                This link has expired. Please ask your child to request a new one — they can resend it from their pending-approval screen.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </div>
          )}

          {phase === 'invalid' && (
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-100 dark:bg-rose-500/15 flex items-center justify-center">
                <XCircle size={28} className="text-rose-600 dark:text-rose-400" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Invalid link</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                This confirmation link is invalid or was replaced by a newer email. Please use the most recent email, or ask your child to resend it.
              </p>
              <button onClick={() => navigate('/')} className="w-full btn-primary">
                Go to ECALT
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
