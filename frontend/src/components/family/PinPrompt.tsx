import { useState } from 'react'
import { reauthenticateWithPopup } from 'firebase/auth'
import { Loader2, Lock, X } from 'lucide-react'
import { firebaseAuth, googleProvider } from '../../lib/firebase'
import { useAuth } from '../../lib/AuthContext'
import { apiErrorCode, type ApiError } from '../../lib/api'
import { resetParentPin, verifyParentPin } from '../../lib/familyApi'
import { setParentUnlock } from '../../lib/profileStore'
import PinPad from './PinPad'

interface Props {
  reason?: string
  onDone: (unlocked: boolean) => void
}

// Asks for the parent PIN and stores the resulting unlock token. "Forgot PIN"
// re-authenticates with Google (the backend requires a sign-in within the last
// 5 minutes) and sets a new one.
export default function PinPrompt({ reason, onDone }: Props) {
  const { getToken } = useAuth()
  const [mode, setMode] = useState<'enter' | 'reset'>('enter')
  const [pin, setPin] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const unlockWith = async (value: string) => {
    const token = await getToken()
    if (!token) throw new Error('Session expired — please sign in again.')
    const { unlock_token, expires_in } = await verifyParentPin(value, token)
    setParentUnlock(unlock_token, expires_in)
  }

  const handleVerify = async () => {
    if (pin.length < 4 || busy) return
    setBusy(true)
    setError(null)
    try {
      await unlockWith(pin)
      onDone(true)
    } catch (err) {
      const code = apiErrorCode(err)
      const detail = (err as ApiError)?.detail as { attempts_left?: number; locked_until?: string } | undefined
      if (code === 'invalid_pin') {
        const left = detail?.attempts_left
        setError(left != null ? `That PIN isn't right. ${left} ${left === 1 ? 'try' : 'tries'} left.` : "That PIN isn't right.")
      } else if (code === 'pin_locked') {
        const until = detail?.locked_until ? new Date(detail.locked_until) : null
        setError(until
          ? `Too many wrong PINs. Try again after ${until.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}, or reset your PIN.`
          : 'Too many wrong PINs. Try again later, or reset your PIN.')
      } else {
        setError((err as ApiError)?.message || 'Could not check the PIN. Please try again.')
      }
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  const startReset = async () => {
    setError(null)
    const current = firebaseAuth.currentUser
    if (!current) return
    try {
      await reauthenticateWithPopup(current, googleProvider)
      await current.getIdToken(true)  // fresh auth_time for the backend's 5-minute check
      setPin('')
      setConfirm('')
      setMode('reset')
    } catch {
      setError('Google sign-in was cancelled. Sign in to reset your PIN.')
    }
  }

  const handleReset = async () => {
    if (pin.length < 4 || pin !== confirm || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      await resetParentPin(pin, token)
      await unlockWith(pin)
      onDone(true)
    } catch (err) {
      setError(apiErrorCode(err) === 'recent_login_required'
        ? 'Please sign in with Google again, then set your new PIN.'
        : (err as ApiError)?.message || 'Could not reset the PIN.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="pin-title">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <Lock size={16} className="text-violet-500" />
            <h2 id="pin-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {mode === 'enter' ? 'Parent PIN' : 'Set a new PIN'}
            </h2>
          </div>
          <button onClick={() => onDone(false)} aria-label="Cancel" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X size={16} />
          </button>
        </div>

        <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
          {mode === 'enter'
            ? reason ?? 'Enter your parent PIN to continue.'
            : 'Choose a new 4–6 digit PIN. Keep it secret from your children.'}
        </p>

        {error && <p className="mb-4 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

        {mode === 'enter' ? (
          <>
            <PinPad value={pin} onChange={setPin} onSubmit={handleVerify} />
            <button
              onClick={handleVerify}
              disabled={pin.length < 4 || busy}
              className="w-full btn-primary mt-5 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : null} Unlock
            </button>
            <button onClick={startReset} className="w-full text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400 dark:hover:text-violet-400 mt-3 py-1 transition-colors">
              Forgot PIN? Reset it with your Google sign-in
            </button>
          </>
        ) : (
          <>
            <PinPad value={pin} onChange={setPin} label="New PIN" id="new-pin" />
            <div className="mt-3">
              <PinPad value={confirm} onChange={setConfirm} onSubmit={handleReset} autoFocus={false} label="Confirm new PIN" id="confirm-pin" />
              {confirm.length >= 4 && pin !== confirm && (
                <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">PINs don't match.</p>
              )}
            </div>
            <button
              onClick={handleReset}
              disabled={pin.length < 4 || pin !== confirm || busy}
              className="w-full btn-primary mt-5 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : null} Save PIN
            </button>
          </>
        )}
      </div>
    </div>
  )
}
