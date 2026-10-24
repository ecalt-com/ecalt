import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Loader2, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { getStudentDrilldown, type StudentDrilldown as Drilldown } from '../../lib/schoolApi'

const FLAG_LABEL: Record<string, string> = {
  overdue: 'Overdue',
  low_quiz_accuracy: 'Low quiz scores',
  heavy_hints: 'Needs many hints',
  stalled: 'Stalled',
}

// Student drill-down (frontend-changes.md §10, SC-701/702): per assigned course,
// step completion plus quiz attempts / accuracy / hints, with "needs attention"
// flags. Opened from the class progress matrix; read-only.
export default function StudentDrilldown({ schoolId, classId, studentUid, studentName, onClose }: {
  schoolId: string; classId: string; studentUid: string; studentName: string; onClose: () => void
}) {
  const { getToken } = useAuth()
  const [data, setData] = useState<Drilldown | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const d = await getStudentDrilldown(schoolId, classId, studentUid, token)
        if (live) setData(d)
      } catch {
        if (live) setError(true)
      }
    })()
    return () => { live = false }
  }, [schoolId, classId, studentUid, getToken])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-20 bg-slate-900/70 backdrop-blur-sm overflow-y-auto"
         role="dialog" aria-modal="true" aria-label={`${studentName} progress`} onClick={onClose}>
      <div className="glass-card rounded-2xl p-5 w-full max-w-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{data?.student.display_name ?? studentName}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={18} /></button>
        </div>

        {!data && !error && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>}
        {error && <p className="text-sm text-rose-600 dark:text-rose-400" role="alert">Couldn't load this student's progress.</p>}

        {data && data.courses.length === 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">No courses assigned to this class yet.</p>
        )}

        <div className="space-y-5">
          {data?.courses.map(c => (
            <section key={c.assignment_id}>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-lg" aria-hidden="true">{c.icon}</span>
                <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{c.title}</h3>
                <span className="text-xs text-slate-500 dark:text-slate-400">{c.done_steps}/{c.total_steps} steps · {c.percent}%</span>
                {c.quiz_accuracy !== null && <span className="text-xs text-slate-500 dark:text-slate-400">· {c.quiz_accuracy}% quiz</span>}
                {c.flags.map(f => (
                  <span key={f} className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300">
                    {FLAG_LABEL[f] ?? f}
                  </span>
                ))}
              </div>
              <ul className="space-y-1">
                {c.steps.map((s, i) => (
                  <li key={s.step_id} className="flex items-center gap-2 text-xs py-1 border-b border-slate-100/70 dark:border-slate-800/60 last:border-0">
                    {s.completed
                      ? <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
                      : <Circle size={14} className="text-slate-300 dark:text-slate-600 shrink-0" />}
                    <span className={clsx('flex-1 min-w-0 truncate', s.completed ? 'text-slate-700 dark:text-slate-200' : 'text-slate-500 dark:text-slate-400')}>
                      {i + 1}. {s.title ?? 'Step'}
                    </span>
                    {s.quiz_attempts > 0 && (
                      <span className="text-slate-400 dark:text-slate-500 shrink-0">
                        {s.quiz_correct}/{s.quiz_attempts} correct{s.hints_used > 0 ? ` · ${s.hints_used} hint${s.hints_used === 1 ? '' : 's'}` : ''}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
