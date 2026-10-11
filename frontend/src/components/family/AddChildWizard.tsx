import { useState } from 'react'
import { X, Loader2, ArrowRight, ArrowLeft, CheckCircle, CreditCard, Lock } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useGeo } from '../../lib/GeoContext'
import { useProfiles } from '../../lib/ProfileContext'
import { apiErrorCode, type ApiError } from '../../lib/api'
import { AVATARS, AVATAR_KEYS } from '../../lib/avatars'
import { createChild, setParentPin, startCardVerification, verifyParentPin, type CreateChildResponse } from '../../lib/familyApi'
import { setParentUnlock } from '../../lib/profileStore'
import PinPad from './PinPad'

interface Props {
  onClose: () => void
  onCreated: () => void
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

// Adds a child *profile* on the parent's account — no child email or
// password. A parent PIN must exist first: it's what keeps the child inside
// their own profile on a shared device.
type Step = 'pin' | 'details' | 'consent' | 'done'

export default function AddChildWizard({ onClose, onCreated }: Props) {
  const { getToken } = useAuth()
  const { country } = useGeo()
  const { pinSet, markPinSet, refresh: refreshProfiles } = useProfiles()
  const currentYear = new Date().getFullYear()
  // Managed accounts are for minors (3–17); the backend rejects the rest.
  const years = Array.from({ length: 16 }, (_, i) => currentYear - 2 - i)

  const [startedWithPin] = useState(pinSet)
  const [step, setStep] = useState<Step>(pinSet ? 'details' : 'pin')
  const steps: Step[] = startedWithPin ? ['details', 'consent'] : ['pin', 'details', 'consent']
  const [pin, setPin] = useState('')
  const [pinConfirm, setPinConfirm] = useState('')
  const [savingPin, setSavingPin] = useState(false)
  const [name, setName] = useState('')
  const [avatar, setAvatar] = useState<string>(AVATAR_KEYS[0])
  const [year, setYear] = useState('')
  const [month, setMonth] = useState('')
  const [consented, setConsented] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<CreateChildResponse | null>(null)
  const [startingVerify, setStartingVerify] = useState(false)

  const detailsValid = name.trim().length > 0 && year !== '' && month !== ''
  const pinValid = pin.length >= 4 && pin === pinConfirm

  const handleSavePin = async () => {
    if (!pinValid || savingPin) return
    setSavingPin(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      await setParentPin(pin, null, token)
      // Unlock right away so creating the profile doesn't ask for the PIN again.
      const { unlock_token, expires_in } = await verifyParentPin(pin, token)
      setParentUnlock(unlock_token, expires_in)
      markPinSet()
      setStep('details')
    } catch (err) {
      setError(apiErrorCode(err) === 'current_pin_required'
        ? 'A PIN is already set — use “Change PIN” on the Family dashboard.'
        : (err as ApiError)?.message || 'Could not save the PIN.')
    } finally {
      setSavingPin(false)
    }
  }

  const handleCreate = async () => {
    if (!consented || creating) return
    setCreating(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const res = await createChild({
        display_name: name.trim(),
        birth_year: parseInt(year, 10),
        birth_month: parseInt(month, 10),
        avatar,
        ...(country ? { country: country.toUpperCase() } : {}),
      }, token)
      setCreated(res)
      setStep('done')
      onCreated()
      refreshProfiles()
    } catch (err: unknown) {
      const code = apiErrorCode(err)
      const messages: Record<string, string> = {
        under_13_not_available: "Profiles for under-13s are coming soon — they need our verified-consent flow. You can add learners aged 13–17 today.",
        adult_account_required: 'Only active adult accounts can add children.',
        no_account: 'Only active adult accounts can add children.',
        not_a_minor: 'Child profiles are for under-18s — adults sign up themselves.',
        invalid_birth_year: 'Please check the birth year.',
        family_full: 'A family supports up to 5 children.',
        pin_required: 'Set a parent PIN first.',
      }
      setError((code && messages[code]) || (err as ApiError)?.message || 'Something went wrong. Please try again.')
      // Age-related errors belong on the details step.
      if (code === 'under_13_not_available' || code === 'not_a_minor' || code === 'invalid_birth_year') {
        setStep('details')
      } else if (code === 'pin_required') {
        setStep('pin')
      }
    } finally {
      setCreating(false)
    }
  }

  const handleVerifyCard = async () => {
    if (!created || startingVerify) return
    setStartingVerify(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const { checkout_url } = await startCardVerification(created.child_uid, token)
      window.location.href = checkout_url
    } catch (err: unknown) {
      const code = apiErrorCode(err)
      setError(code === 'not_configured'
        ? 'Card verification is temporarily unavailable. You can start it later from the dashboard.'
        : 'Could not start card verification. You can retry from the dashboard.')
      setStartingVerify(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {step === 'done' ? 'Profile added' : step === 'pin' ? 'Set your parent PIN' : 'Add a child'}
          </h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X size={16} />
          </button>
        </div>

        {step !== 'done' && (
          <div className="flex items-center gap-1.5 mb-5">
            {steps.map((s, i) => (
              <div
                key={s}
                className={`h-1 flex-1 rounded-full ${
                  steps.indexOf(step) >= i
                    ? 'bg-violet-500'
                    : 'bg-slate-200 dark:bg-slate-700'
                }`}
              />
            ))}
          </div>
        )}

        {error && <p className="mb-4 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

        {step === 'pin' && (
          <>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 flex gap-2">
              <Lock size={16} className="text-violet-500 shrink-0 mt-0.5" />
              <span>
                Your children use ECALT through your sign-in, each in their own profile. Your PIN keeps them
                there — it's needed to switch back to your profile or change family settings.
              </span>
            </p>
            <PinPad value={pin} onChange={setPin} label="Choose a 4–6 digit PIN" id="new-parent-pin" />
            <div className="mt-3 mb-5">
              <PinPad value={pinConfirm} onChange={setPinConfirm} onSubmit={handleSavePin} autoFocus={false} label="Confirm PIN" id="confirm-parent-pin" />
              {pinConfirm.length >= 4 && pin !== pinConfirm && (
                <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">PINs don't match.</p>
              )}
            </div>
            <button
              onClick={handleSavePin}
              disabled={!pinValid || savingPin}
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {savingPin ? <Loader2 size={14} className="animate-spin" /> : null} Save PIN & continue
            </button>
          </>
        )}

        {step === 'details' && (
          <>
            <div className="mb-4">
              <label htmlFor="child-name" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Child's name</label>
              <input
                id="child-name"
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="First name"
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
            </div>
            <fieldset className="mb-4">
              <legend className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Profile picture</legend>
              <div className="grid grid-cols-8 gap-1.5">
                {AVATAR_KEYS.map(key => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setAvatar(key)}
                    aria-label={key}
                    aria-pressed={avatar === key}
                    className={clsx(
                      'aspect-square rounded-xl text-xl flex items-center justify-center transition-all',
                      AVATARS[key].bg,
                      avatar === key ? 'ring-2 ring-violet-500 scale-105' : 'opacity-70 hover:opacity-100',
                    )}
                  >
                    {AVATARS[key].emoji}
                  </button>
                ))}
              </div>
            </fieldset>
            <div className="mb-6 grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="child-birth-month" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Birth month</label>
                <select
                  id="child-birth-month"
                  value={month}
                  onChange={e => setMonth(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
                >
                  <option value="">Month</option>
                  {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="child-birth-year" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Birth year</label>
                <select
                  id="child-birth-year"
                  value={year}
                  onChange={e => setYear(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
                >
                  <option value="">Year</option>
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>
            <button
              onClick={() => { setError(null); setStep('consent') }}
              disabled={!detailsValid}
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Continue <ArrowRight size={14} />
            </button>
          </>
        )}

        {step === 'consent' && (
          <>
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 p-4 mb-4 text-left">
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">ECALT will collect from {name.trim() || 'your child'}:</p>
              <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 mb-3">
                <li>• Their name, birth month/year and country</li>
                <li>• The learning questions they ask, the journeys they create and their chats with the AI tutor</li>
                <li>• AI-generated knowledge topics (their learning map)</li>
              </ul>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">ECALT never:</p>
              <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 mb-3">
                <li>• Sells data</li>
                <li>• Shows ads</li>
                <li>• Shares data with third parties for marketing</li>
              </ul>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">As the parent, you can always:</p>
              <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 mb-3">
                <li>• View their learning activity from your Family dashboard</li>
                <li>• Export all of their data</li>
                <li>• Open their profile and see everything in it</li>
                <li>• Delete their profile</li>
                <li>• Withdraw consent at any time</li>
              </ul>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline text-violet-600 dark:text-violet-400">Terms of Service</a>
                {' '}·{' '}
                <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline text-violet-600 dark:text-violet-400">Privacy Policy</a>
              </p>
            </div>
            <label className="flex items-start gap-2.5 mb-5 cursor-pointer">
              <input
                type="checkbox"
                checked={consented}
                onChange={e => setConsented(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-violet-600 focus:ring-violet-500"
              />
              <span className="text-xs text-slate-600 dark:text-slate-400">
                I am this child's parent or legal guardian, and I consent to ECALT collecting and
                processing their data as described above.
              </span>
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => setStep('details')}
                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 transition-all flex items-center justify-center gap-2"
              >
                <ArrowLeft size={14} /> Back
              </button>
              <button
                onClick={handleCreate}
                disabled={!consented || creating}
                className="flex-1 btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {creating ? <><Loader2 size={14} className="animate-spin" /> Adding…</> : 'Add profile'}
              </button>
            </div>
          </>
        )}

        {step === 'done' && created && (
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center">
              <CheckCircle size={24} className="text-emerald-600 dark:text-emerald-400" />
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300 mb-2">
              <span className="font-semibold">{created.display_name}</span>'s profile is set up.
            </p>
            {created.verification_required ? (
              <>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
                  One last step: your region requires a quick card check to verify you're an adult.
                  <span className="font-medium"> €0/₹0 — card check only, nothing is charged.</span>
                </p>
                <button
                  onClick={handleVerifyCard}
                  disabled={startingVerify}
                  className="w-full btn-primary flex items-center justify-center gap-2 mb-3 disabled:opacity-60"
                >
                  {startingVerify ? <Loader2 size={14} className="animate-spin" /> : <CreditCard size={14} />}
                  Verify with card
                </button>
                <button onClick={onClose} className="w-full text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-1 transition-colors">
                  Later — I'll verify from the dashboard
                </button>
              </>
            ) : (
              <>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
                  When it's their turn, open <span className="font-medium">Who's learning?</span> from the menu
                  and pick their profile. They'll need your PIN to leave it.
                </p>
                <button onClick={onClose} className="w-full btn-primary">Done</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
