import { useState } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'

interface Props {
  onSubmit: (birthYear: number) => Promise<void>
}

export default function BirthYearGate({ onSubmit }: Props) {
  const currentYear = new Date().getFullYear()
  const years = Array.from({ length: 100 }, (_, i) => currentYear - i)

  const [year, setYear] = useState('')
  const [consented, setConsented] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canContinue = year !== '' && consented

  const handleSubmit = async () => {
    const birthYear = parseInt(year, 10)
    if (!year || isNaN(birthYear)) {
      setError('Please select your birth year.')
      return
    }
    if (!consented) {
      setError('Please accept the Terms of Service and Privacy Policy.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await onSubmit(birthYear)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="animate-celebration glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-4xl mb-3">🎓</div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">How old are you?</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            We ask to keep ECALT safe for all learners.
          </p>
        </div>

        <div className="mb-4">
          <label htmlFor="birth-year" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
            Birth year
          </label>
          <select
            id="birth-year"
            value={year}
            onChange={e => { setYear(e.target.value); if (error) setError(null) }}
            aria-describedby={error ? 'birth-year-error' : undefined}
            className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
          >
            <option value="">Select year</option>
            {years.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <label className="flex items-start gap-2.5 mb-5 cursor-pointer">
          <input
            type="checkbox"
            checked={consented}
            onChange={e => { setConsented(e.target.checked); if (error) setError(null) }}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-violet-600 focus:ring-violet-500"
          />
          <span className="text-xs text-slate-600 dark:text-slate-400">
            I agree to the{' '}
            <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-violet-600 dark:hover:text-violet-400">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline hover:text-violet-600 dark:hover:text-violet-400">
              Privacy Policy
            </a>
          </span>
        </label>

        {error && (
          <p id="birth-year-error" className="mb-3 text-xs text-rose-600 dark:text-rose-400" role="alert">
            {error}
          </p>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || !canContinue}
          className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading
            ? <><Loader2 size={14} className="animate-spin" /> Checking…</>
            : <>Continue <ArrowRight size={14} /></>}
        </button>
      </div>
    </div>
  )
}
