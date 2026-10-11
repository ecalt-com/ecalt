import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Loader2, Plus, Users, Flame, CreditCard, ShieldCheck, ShieldAlert,
  PauseCircle, ChevronRight, Lock, Play, X,
} from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import AddChildWizard from '../components/family/AddChildWizard'
import PinPad from '../components/family/PinPad'
import ProfileAvatar from '../components/family/ProfileAvatar'
import { useAuth } from '../lib/AuthContext'
import { useProfiles } from '../lib/ProfileContext'
import { useToast } from '../lib/ToastContext'
import { apiErrorCode, type ApiError } from '../lib/api'
import {
  getChildren,
  setParentPin,
  startCardVerification,
  confirmCardVerification,
  type FamilyChild,
} from '../lib/familyApi'

function childStatus(child: FamilyChild): { label: string; tone: 'ok' | 'warn' | 'muted' } {
  if (child.paused) return { label: 'Paused', tone: 'muted' }
  if (child.account_status === 'parental_consent_pending') return { label: 'Awaiting verification', tone: 'warn' }
  if (child.account_status === 'active') return { label: 'Active', tone: 'ok' }
  return { label: child.account_status, tone: 'muted' }
}

const needsCardVerification = (child: FamilyChild) =>
  child.verification_tier === 'card' && child.verification_status !== 'verified'

function ChangePinModal({ onClose }: { onClose: () => void }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const valid = current.length >= 4 && next.length >= 4 && next === confirm

  const save = async () => {
    if (!valid || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      await setParentPin(next, current, token)
      addToast('PIN changed ✓')
      onClose()
    } catch (err) {
      const code = apiErrorCode(err)
      setError(code === 'invalid_pin' ? "Your current PIN isn't right."
        : code === 'pin_locked' ? 'Too many wrong PINs. Try again later.'
          : (err as ApiError)?.message || 'Could not change the PIN.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Change parent PIN</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X size={16} />
          </button>
        </div>
        {error && <p className="mb-4 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
        <div className="space-y-3">
          <PinPad value={current} onChange={setCurrent} label="Current PIN" id="current-pin" />
          <PinPad value={next} onChange={setNext} autoFocus={false} label="New PIN" id="next-pin" />
          <PinPad value={confirm} onChange={setConfirm} onSubmit={save} autoFocus={false} label="Confirm new PIN" id="confirm-next-pin" />
        </div>
        {confirm.length >= 4 && next !== confirm && (
          <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">PINs don't match.</p>
        )}
        <button
          onClick={save}
          disabled={!valid || busy}
          className="w-full btn-primary mt-5 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {busy && <Loader2 size={14} className="animate-spin" />} Save PIN
        </button>
        <p className="mt-3 text-xs text-slate-400 text-center">Forgot it? Use “Forgot PIN” when you're asked for it.</p>
      </div>
    </div>
  )
}

export default function Family() {
  const { user, loading: authLoading, getToken, refreshRole } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  const [children, setChildren] = useState<FamilyChild[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showWizard, setShowWizard] = useState(params.get('add') === '1')
  const [showChangePin, setShowChangePin] = useState(false)
  const [verifyingUid, setVerifyingUid] = useState<string | null>(null)
  const { pinSet, switchTo, refresh: refreshProfiles } = useProfiles()

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  const loadChildren = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      const data = await getChildren(token)
      setChildren(data.children)
      setLoadError(null)
    } catch (err) {
      setLoadError(apiErrorCode(err) === 'parent_unlock_required'
        ? 'Enter your parent PIN to see your family. Refresh to try again.'
        : "Couldn't load your family. Please refresh and try again.")
    }
  }, [getToken])

  useEffect(() => {
    if (user) loadChildren()
  }, [user, loadChildren])

  // Return leg of the Stripe card-verification redirect:
  // /family?verify_session={SESSION_ID}&child={uid}
  useEffect(() => {
    const sessionId = params.get('verify_session')
    const childUid = params.get('child')
    if (!user || !sessionId || !childUid) return
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        await confirmCardVerification(childUid, sessionId, token)
        addToast('Card verified — account activated ✓')
        loadChildren()
      } catch (err: unknown) {
        const code = apiErrorCode(err)
        addToast(
          code === 'verification_incomplete'
            ? "Card verification wasn't completed — try again from the child's card."
            : 'Could not confirm verification. Please try again.',
          'error',
        )
      } finally {
        // Clear the params so a refresh doesn't re-confirm.
        setParams({}, { replace: true })
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  const handleVerifyCard = async (child: FamilyChild) => {
    if (verifyingUid) return
    setVerifyingUid(child.child_uid)
    try {
      const token = await getToken()
      if (!token) return
      const { checkout_url } = await startCardVerification(child.child_uid, token)
      window.location.href = checkout_url
    } catch (err: unknown) {
      const code = apiErrorCode(err)
      addToast(
        code === 'not_configured'
          ? 'Card verification is temporarily unavailable.'
          : 'Could not start card verification. Please try again.',
        'error',
      )
      setVerifyingUid(null)
    }
  }

  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <Loader2 className="animate-spin text-violet-500" />
      </div>
    )
  }

  return (
    <>
      <PageMeta title="Family" description="See what your children are learning and manage their accounts." />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Family</h1>
            <button
              onClick={() => setShowWizard(true)}
              className="btn-primary flex items-center gap-1.5 text-sm"
            >
              <Plus size={14} /> Add a child
            </button>
          </div>

          {loadError && (
            <div className="glass-card rounded-2xl p-5 mb-5 text-sm text-rose-600 dark:text-rose-400">{loadError}</div>
          )}

          {children === null && !loadError && (
            <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
          )}

          {children !== null && children.length === 0 && (
            <div className="glass-card rounded-2xl p-10 text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                <Users size={28} className="text-violet-600 dark:text-violet-400" />
              </div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">No children linked yet</h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 max-w-sm mx-auto">
                Add a profile for your child — they'll learn through your sign-in, no email or password
                needed. Teens with their own Google login show up here once you approve their request.
              </p>
              <button onClick={() => setShowWizard(true)} className="btn-primary inline-flex items-center gap-1.5">
                <Plus size={14} /> Add a child
              </button>
            </div>
          )}

          <div className="space-y-4">
            {children?.map(child => {
              const status = childStatus(child)
              return (
                <div key={child.child_uid} className="glass-card rounded-2xl p-5">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0 flex items-start gap-3">
                      <ProfileAvatar name={child.display_name} avatar={child.avatar} />
                      <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-base font-semibold text-slate-900 dark:text-slate-100">
                          {child.display_name || 'Child'}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 dark:bg-slate-700/50 dark:text-slate-300 capitalize">
                          {child.age_group_flag === 'child' ? 'Under 13' : 'Teen'}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
                          {child.profile_type === 'profile' ? 'Profile' : 'Own login'}
                        </span>
                        <span className={clsx(
                          'text-xs px-2 py-0.5 rounded-full flex items-center gap-1',
                          status.tone === 'ok' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
                          status.tone === 'warn' && 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
                          status.tone === 'muted' && 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
                        )}>
                          {child.paused && <PauseCircle size={11} />}
                          {status.label}
                        </span>
                      </div>
                      {child.email && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 break-all">{child.email}</p>
                      )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span className="flex items-center gap-1">
                        <Flame size={13} className="text-amber-500" /> {child.streak_days} day streak
                      </span>
                      {child.verification_status === 'verified' ? (
                        <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                          <ShieldCheck size={13} /> Verified
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-slate-400">
                          <ShieldAlert size={13} /> Unverified
                        </span>
                      )}
                    </div>
                  </div>

                  {needsCardVerification(child) && (
                    <div className="mt-4 rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-3 flex items-center justify-between gap-3 flex-wrap">
                      <p className="text-xs text-amber-800 dark:text-amber-300">
                        A quick card check activates this account. €0/₹0 — card check only, nothing is charged.
                      </p>
                      <button
                        onClick={() => handleVerifyCard(child)}
                        disabled={verifyingUid !== null}
                        className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white transition-all disabled:opacity-60"
                      >
                        {verifyingUid === child.child_uid
                          ? <Loader2 size={12} className="animate-spin" />
                          : <CreditCard size={12} />}
                        Verify with card
                      </button>
                    </div>
                  )}

                  <div className="mt-4 flex justify-between items-center gap-3 flex-wrap">
                    {child.profile_type === 'profile' && child.account_status === 'active' && !child.paused ? (
                      <button
                        onClick={() => switchTo(child.child_uid)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-300 hover:text-violet-600 dark:hover:text-violet-400"
                      >
                        <Play size={12} /> Switch to {child.display_name?.split(' ')[0] || 'their'} profile
                      </button>
                    ) : <span />}
                    <Link
                      to={`/family/child/${child.child_uid}`}
                      className="inline-flex items-center gap-1 text-xs font-medium text-violet-600 dark:text-violet-400 hover:underline"
                    >
                      View activity &amp; settings <ChevronRight size={13} />
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>

          {children !== null && children.length > 0 && (
            <div className="mt-6 text-xs text-slate-400 dark:text-slate-500 text-center space-y-2">
              <p>
                Children with a profile learn through your sign-in — pick them on{' '}
                <Link to="/profiles" className="underline text-violet-600 dark:text-violet-400">Who's learning?</Link>.
                They need your PIN to leave their profile.
              </p>
              {pinSet && (
                <button onClick={() => setShowChangePin(true)} className="inline-flex items-center gap-1 underline text-violet-600 dark:text-violet-400">
                  <Lock size={11} /> Change parent PIN
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {showWizard && (
        <AddChildWizard
          onClose={() => { setShowWizard(false); if (params.get('add')) setParams({}, { replace: true }) }}
          onCreated={() => { loadChildren(); refreshRole(); refreshProfiles() }}
        />
      )}
      {showChangePin && <ChangePinModal onClose={() => setShowChangePin(false)} />}
    </>
  )
}
