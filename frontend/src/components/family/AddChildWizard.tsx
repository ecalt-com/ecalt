import { useState } from 'react'
import { X, Loader2, ArrowRight, ArrowLeft, CheckCircle, CreditCard, KeyRound } from 'lucide-react'
import { useAuth } from '../../lib/AuthContext'
import { useGeo } from '../../lib/GeoContext'
import { apiErrorCode, type ApiError } from '../../lib/api'
import { createChild, startCardVerification, type CreateChildResponse } from '../../lib/familyApi'

interface Props {
  onClose: () => void
  onCreated: () => void
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

// Step order follows the Google Family Link pattern: identity → consent → credentials → done.
type Step = 'details' | 'consent' | 'credentials' | 'done'

export default function AddChildWizard({ onClose, onCreated }: Props) {
  const { getToken } = useAuth()
  const { country } = useGeo()
  const currentYear = new Date().getFullYear()
  // Managed accounts are for minors (3–17); the backend rejects the rest.
  const years = Array.from({ length: 16 }, (_, i) => currentYear - 2 - i)

  const [step, setStep] = useState<Step>('details')
  const [name, setName] = useState('')
  const [year, setYear] = useState('')
  const [month, setMonth] = useState('')
  const [consented, setConsented] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<CreateChildResponse | null>(null)
  const [startingVerify, setStartingVerify] = useState(false)

  const detailsValid = name.trim().length > 0 && year !== '' && month !== ''
  const credentialsValid = email.includes('@') && password.length >= 8 && password === confirm

  const handleCreate = async () => {
    if (!credentialsValid || creating) return
    setCreating(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const res = await createChild({
        display_name: name.trim(),
        birth_year: parseInt(year, 10),
        birth_month: parseInt(month, 10),
        email: email.trim(),
        password,
        ...(country ? { country: country.toUpperCase() } : {}),
      }, token)
      setCreated(res)
      setStep('done')
      onCreated()
    } catch (err: unknown) {
      const code = apiErrorCode(err)
      const messages: Record<string, string> = {
        under_13_not_available: "Accounts for under-13s are coming soon — they need our verified-consent flow. You can add learners aged 13–17 today.",
        adult_account_required: 'Only active adult accounts can add children.',
        no_account: 'Only active adult accounts can add children.',
        not_a_minor: 'Managed accounts are for children under 18 — adults sign up themselves.',
        invalid_birth_year: 'Please check the birth year.',
        family_full: 'A family supports up to 5 children.',
        email_exists: 'An account with this email already exists — try a different one.',
        invalid_email: 'Enter a valid email address for the child.',
        not_configured: 'Child account creation is temporarily unavailable. Please try again later.',
      }
      setError((code && messages[code]) || (err as ApiError)?.message || 'Something went wrong. Please try again.')
      // Age-related errors belong on the details step.
      if (code === 'under_13_not_available' || code === 'not_a_minor' || code === 'invalid_birth_year') {
        setStep('details')
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
            {step === 'done' ? 'Account created' : 'Add a child'}
          </h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X size={16} />
          </button>
        </div>

        {step !== 'done' && (
          <div className="flex items-center gap-1.5 mb-5">
            {(['details', 'consent', 'credentials'] as Step[]).map((s, i) => (
              <div
                key={s}
                className={`h-1 flex-1 rounded-full ${
                  ['details', 'consent', 'credentials'].indexOf(step) >= i
                    ? 'bg-violet-500'
                    : 'bg-slate-200 dark:bg-slate-700'
                }`}
              />
            ))}
          </div>
        )}

        {error && <p className="mb-4 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

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
                <li>• Their name and login email</li>
                <li>• The learning questions they ask and the journeys they create</li>
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
                <li>• Delete their account</li>
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
                onClick={() => { setError(null); setStep('credentials') }}
                disabled={!consented}
                className="flex-1 btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Continue <ArrowRight size={14} />
              </button>
            </div>
          </>
        )}

        {step === 'credentials' && (
          <>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Create the login {name.trim() || 'your child'} will use. Share these with them — the email
              can be an alias you manage.
            </p>
            <div className="mb-3">
              <label htmlFor="child-email" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Child's login email</label>
              <input
                id="child-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="kid@example.com"
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
            </div>
            <div className="mb-3">
              <label htmlFor="child-password" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Password (min 8 characters)</label>
              <input
                id="child-password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
            </div>
            <div className="mb-5">
              <label htmlFor="child-password-confirm" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Confirm password</label>
              <input
                id="child-password-confirm"
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
              />
              {confirm && password !== confirm && (
                <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">Passwords don't match.</p>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setStep('consent')}
                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 transition-all flex items-center justify-center gap-2"
              >
                <ArrowLeft size={14} /> Back
              </button>
              <button
                onClick={handleCreate}
                disabled={!credentialsValid || creating}
                className="flex-1 btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {creating ? <><Loader2 size={14} className="animate-spin" /> Creating…</> : 'Create account'}
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
              <span className="font-semibold">{created.display_name}</span>'s account is set up.
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
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-5 flex items-center justify-center gap-1.5">
                  <KeyRound size={14} className="text-violet-500" />
                  They can now sign in at <a href="/kids-login" className="underline text-violet-600 dark:text-violet-400">ecalt.com/kids-login</a>
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
