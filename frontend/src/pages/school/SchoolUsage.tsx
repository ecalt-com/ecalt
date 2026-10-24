import { useEffect, useState } from 'react'
import { Loader2, Wallet } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { apiErrorCode } from '../../lib/api'
import { getSchoolUsage, type SchoolUsage } from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`
const monthLabel = (iso: string) => new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', year: 'numeric' })

// /school/usage (frontend-changes.md §10, SC-706; admins). The school's monthly
// AI budget and spend, today's per-student usage against the daily caps, and
// recent monthly history. Per-class/per-course spend is not tracked yet.
export default function SchoolUsage() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const [usage, setUsage] = useState<SchoolUsage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const u = await getSchoolUsage(school.id, token)
        if (live) setUsage(u)
      } catch (err) {
        if (live) setError(apiErrorCode(err) === 'school_role_required'
          ? "Usage is visible to school admins only."
          : "Couldn't load usage. Refresh to try again.")
      }
    })()
    return () => { live = false }
  }, [school.id, getToken])

  if (error) {
    return <div className="glass-card rounded-2xl p-6 text-sm text-slate-600 dark:text-slate-300" role="alert">{error}</div>
  }
  if (!usage) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
  }

  const overBudget = usage.budget_cents > 0 && usage.spent_cents >= usage.budget_cents
  const near = usage.percent >= 80

  return (
    <div className="space-y-5">
      {/* Budget meter */}
      <div className="glass-card rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2 mb-1">
          <Wallet size={15} className="text-violet-500" /> AI budget — {monthLabel(usage.period_start)}
        </h2>
        {usage.budget_cents > 0 ? (
          <>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {dollars(usage.spent_cents)}
              <span className="text-sm font-normal text-slate-500 dark:text-slate-400"> of {dollars(usage.budget_cents)} ({usage.percent}%)</span>
            </p>
            <div className="mt-2 h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
              <div className={clsx('h-full rounded-full', overBudget ? 'bg-rose-500' : near ? 'bg-amber-500' : 'bg-violet-500')}
                   style={{ width: `${Math.min(usage.percent, 100)}%` }} />
            </div>
            {overBudget && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">The monthly budget is spent — students' AI tutor and quizzes are paused until next month or a higher budget.</p>}
          </>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No AI budget set for this school.</p>
        )}
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Daily cap per student: {usage.caps.student_daily_tutor_messages} tutor messages · {usage.caps.student_daily_quiz_sets} quiz sets
        </p>
      </div>

      {/* Today's per-student usage */}
      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Today's usage by student</h3>
        {usage.today.length === 0 ? (
          <p className="text-xs text-slate-500 dark:text-slate-400">No AI usage by students yet today.</p>
        ) : (
          <ul className="divide-y divide-slate-100/70 dark:divide-slate-800/60">
            {usage.today.map(s => (
              <li key={s.student_uid} className="flex items-center justify-between gap-3 py-1.5 text-sm">
                <span className="text-slate-700 dark:text-slate-200 truncate">{s.display_name ?? s.student_uid}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400 shrink-0">
                  {s.tutor_messages} tutor · {s.quiz_sets} quiz
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Monthly history */}
      {usage.history.length > 0 && (
        <div className="glass-card rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Recent months</h3>
          <ul className="space-y-1.5">
            {usage.history.map(m => (
              <li key={m.period_start} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-600 dark:text-slate-300">{monthLabel(m.period_start)}</span>
                <span className="text-slate-500 dark:text-slate-400">{dollars(m.cost_cents)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
