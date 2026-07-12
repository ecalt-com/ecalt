import { useNavigate } from 'react-router-dom'
import { PauseCircle } from 'lucide-react'

// Full-screen state for 403 {error: "account_paused"} — a parent paused the
// account from the Family dashboard.
export default function AccountPausedScreen() {
  const navigate = useNavigate()
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-primary)]">
      <div className="glass-card rounded-3xl p-8 max-w-sm w-full shadow-2xl text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center">
          <PauseCircle size={28} className="text-amber-600 dark:text-amber-400" />
        </div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Your account is paused</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
          Your parent has paused your ECALT account. Ask them to unpause it from their
          Family dashboard — your journeys and progress are safe and waiting for you.
        </p>
        <button onClick={() => navigate('/')} className="w-full btn-primary">
          Back to Home
        </button>
      </div>
    </div>
  )
}
