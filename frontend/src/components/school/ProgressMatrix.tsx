import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, BarChart3, CheckCircle2, Download, Loader2, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { flagLabel, getClassProgress, getClassProgressCsv, type ProgressCell, type ProgressCourseCol, type ProgressStudentRow } from '../../lib/schoolApi'
import StudentDrilldown from './StudentDrilldown'

// Colour for a cell by how far the student has got, with an overdue outline.
function cellClasses(c: ProgressCell): string {
  if (c.completed) return 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
  if (c.overdue) return 'bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 ring-1 ring-inset ring-rose-300 dark:ring-rose-500/40'
  if (c.flags?.length) return 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-1 ring-inset ring-amber-300 dark:ring-amber-500/40'
  if (c.done > 0) return 'bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300'
  return 'text-slate-400 dark:text-slate-500'
}

function dueText(iso: string | null): string | null {
  if (!iso) return null
  return `Due ${new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
}

// Class → Progress (frontend-changes.md §10, SC-505). A matrix of the class's
// active students (rows) × its assigned courses (columns); each cell shows steps
// done/total, coloured by progress, outlined when overdue. Read-only; open to any
// staff member. Drill-down / CSV export / usage are a later milestone (M7).
export default function ProgressMatrix({ schoolId, classId, refreshKey = 0 }: { schoolId: string; classId: string; refreshKey?: number }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [students, setStudents] = useState<ProgressStudentRow[] | null>(null)
  const [courses, setCourses] = useState<ProgressCourseCol[]>([])
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [drilldown, setDrilldown] = useState<{ uid: string; name: string } | null>(null)
  const [attentionOnly, setAttentionOnly] = useState(false)
  const flaggedCount = students?.filter(s => s.needs_attention).length ?? 0
  const shown = attentionOnly ? (students ?? []).filter(s => s.needs_attention) : (students ?? [])

  const exportCsv = async () => {
    setExporting(true)
    try {
      const token = await getToken()
      if (!token) return
      const csv = await getClassProgressCsv(schoolId, classId, token)
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url
      a.download = 'class-progress.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      addToast("Couldn't export the CSV — try again.", 'error')
    } finally {
      setExporting(false)
    }
  }

  const load = useCallback(async () => {
    setBusy(true)
    try {
      const token = await getToken()
      if (!token) return
      const data = await getClassProgress(schoolId, classId, token)
      setStudents(data.students)
      setCourses(data.courses)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }, [schoolId, classId, getToken])

  useEffect(() => { load() }, [load, refreshKey])

  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
          <BarChart3 size={15} className="text-violet-500" /> Progress
        </h3>
        <div className="flex items-center gap-1 whitespace-nowrap">
          {students && courses.length > 0 && students.length > 0 && (
            <button
              onClick={() => setAttentionOnly(v => !v)}
              aria-pressed={attentionOnly}
              data-testid="needs-attention-filter"
              className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border',
                attentionOnly
                  ? 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/40'
                  : 'text-slate-500 dark:text-slate-400 hover:text-amber-600 border-slate-200 dark:border-slate-700')}
            ><AlertTriangle size={13} /> Needs attention ({flaggedCount})</button>
          )}
          {students && courses.length > 0 && students.length > 0 && (
            <button
              onClick={exportCsv} disabled={exporting}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-violet-600 border border-slate-200 dark:border-slate-700 disabled:opacity-50"
            >{exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} CSV</button>
          )}
          <button
            onClick={load} disabled={busy}
            className="p-1.5 rounded-lg text-slate-400 hover:text-violet-600 disabled:opacity-50" aria-label="Refresh progress"
          ><RefreshCw size={14} className={clsx(busy && 'animate-spin')} /></button>
        </div>
      </div>

      {students === null ? (
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-violet-500" size={18} /></div>
      ) : error ? (
        <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">Couldn't load progress. Try refreshing.</p>
      ) : courses.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">Assign a course to see progress.</p>
      ) : students.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">No students enrolled yet.</p>
      ) : shown.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400" data-testid="needs-attention-empty">No students need attention right now.</p>
      ) : (
        <div className="overflow-x-auto -mx-1 px-1">
          <table className="w-full border-separate border-spacing-1 text-sm">
            <thead>
              <tr>
                <th className="text-left font-medium text-xs text-slate-400 dark:text-slate-500 px-2 py-1 sticky left-0 bg-[var(--card-bg)] z-10">Student</th>
                {courses.map(c => (
                  <th key={c.journey_id} className="font-medium text-xs text-slate-500 dark:text-slate-400 px-2 py-1 min-w-[5.5rem] align-bottom">
                    <span className="flex flex-col items-center gap-0.5">
                      <span className="text-base" aria-hidden="true">{c.icon}</span>
                      <span className="max-w-[7rem] truncate" title={c.title}>{c.title}</span>
                      {dueText(c.due_at) && <span className="text-[10px] text-slate-400">{dueText(c.due_at)}</span>}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map(s => (
                <tr key={s.uid} data-testid="progress-row" data-needs-attention={s.needs_attention ? 'true' : 'false'}>
                  <td className="px-2 py-1 whitespace-nowrap sticky left-0 bg-[var(--card-bg)] z-10">
                    <button
                      onClick={() => setDrilldown({ uid: s.uid, name: s.display_name })}
                      className="text-slate-700 dark:text-slate-200 hover:text-violet-600 dark:hover:text-violet-400 hover:underline"
                    >{s.display_name}</button>
                    {!!s.flags?.length && (
                      <span className="ml-1.5 inline-flex align-middle text-amber-500" title={s.flags.map(flagLabel).join(' · ')}
                            aria-label={`Needs attention: ${s.flags.map(flagLabel).join(', ')}`}>
                        <AlertTriangle size={12} />
                      </span>
                    )}
                  </td>
                  {courses.map(c => {
                    const cell = s.cells[c.journey_id]
                    if (!cell) return <td key={c.journey_id} className="px-2 py-1 text-center text-slate-300">–</td>
                    return (
                      <td key={c.journey_id} className="px-1 py-1 text-center">
                        <span className={clsx('inline-flex items-center justify-center gap-1 rounded-lg px-2 py-1 text-xs font-medium min-w-[3.25rem]', cellClasses(cell))}
                              title={[`${cell.done} of ${cell.total} steps`, ...(cell.flags ?? []).map(flagLabel)].join(' · ')}>
                          {cell.completed
                            ? <CheckCircle2 size={14} />
                            : <span>{cell.done}/{cell.total}</span>}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {drilldown && (
        <StudentDrilldown
          schoolId={schoolId} classId={classId}
          studentUid={drilldown.uid} studentName={drilldown.name}
          onClose={() => setDrilldown(null)}
        />
      )}
    </div>
  )
}
