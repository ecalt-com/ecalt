import { useState } from 'react'
import { Loader2, ShieldCheck, X } from 'lucide-react'
import { useAuth } from '../../lib/AuthContext'
import { apiErrorCode } from '../../lib/api'
import { acceptDpa, schoolErrorMessage, type School } from '../../lib/schoolApi'

// The school (controller) accepts ECALT's data processing agreement before
// any student can be added. The summary below must be replaced by the
// counsel-approved agreement text before real student data (TRACKER SC-002/SC-804).
export default function DpaModal({ school, onClose, onAccepted }: {
  school: School
  onClose: () => void
  onAccepted: (school: School) => void
}) {
  const { getToken } = useAuth()
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = async () => {
    if (!agreed || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      onAccepted(await acceptDpa(school.id, school.dpa_current_version, token))
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="dpa-title">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4 gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-violet-500" />
            <h2 id="dpa-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">Data processing agreement</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X size={16} />
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">Version {school.dpa_current_version}</p>

        <div className="space-y-3 text-sm text-slate-700 dark:text-slate-300">
          <p>
            <strong>{school.name}</strong> is the controller of its students' data. ECALT processes it only to
            run the service, on your school's instructions.
          </p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>For each student ECALT keeps only a display name, grade and optional school reference number — no email, birth date or photo.</li>
            <li>Teaching material your staff upload stays private to your school and is never used outside it.</li>
            <li>Staff actions are logged. You can export or delete any student's data at any time.</li>
            <li>If your school leaves ECALT, its data is deleted after a 30-day grace period.</li>
          </ul>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Your ECALT contact sends you the full agreement. Questions: support@ecalt.com.
          </p>
        </div>

        <label className="mt-5 flex items-start gap-2.5 text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
          <input
            type="checkbox"
            checked={agreed}
            onChange={e => setAgreed(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
          />
          <span>I have read the agreement and accept it on behalf of {school.name}.</span>
        </label>

        {error && <p className="mt-3 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

        <button
          onClick={accept}
          disabled={!agreed || busy}
          className="w-full btn-primary mt-5 flex items-center justify-center gap-2"
        >
          {busy && <Loader2 size={14} className="animate-spin" />} Accept agreement
        </button>
      </div>
    </div>
  )
}
