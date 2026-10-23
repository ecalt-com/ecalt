import { useCallback, useEffect, useState } from 'react'
import { BookOpen, Loader2, Plus, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  assignCourse, listAssignments, listCourses, schoolErrorMessage, unassignCourse, updateAssignment,
  type Assignment, type CourseListItem,
} from '../../lib/schoolApi'

const fieldCls = 'px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 disabled:opacity-60'

// A date-only input value (YYYY-MM-DD) → end-of-day ISO so "due Friday" means
// any time that day. The reverse is used to prefill the input.
const toDueIso = (date: string): string | null => (date ? `${date}T23:59:59Z` : null)
const toDateInput = (iso: string | null): string => (iso ? iso.slice(0, 10) : '')

function dueLabel(iso: string | null): { text: string; overdue: boolean } | null {
  if (!iso) return null
  const due = new Date(iso)
  const overdue = due.getTime() < Date.now()
  return { text: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), overdue }
}

// Class → Courses (frontend-changes.md §9). Lists the published courses assigned
// to a class with a progress summary, and (for class staff) lets them assign a
// published course, set a due date, toggle the tutor / quiz-required, or
// unassign. The API is the authority; controls are hidden when canManage is false.
export default function ClassCourses({ schoolId, classId, canManage }: {
  schoolId: string; classId: string; canManage: boolean
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [assignments, setAssignments] = useState<Assignment[] | null>(null)
  const [publishable, setPublishable] = useState<CourseListItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmUnassign, setConfirmUnassign] = useState<string | null>(null)
  const [pick, setPick] = useState('')
  const [due, setDue] = useState('')
  const [tutor, setTutor] = useState(true)
  const [quiz, setQuiz] = useState(false)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      const [a, c] = await Promise.all([
        listAssignments(schoolId, classId, token),
        canManage ? listCourses(schoolId, token) : Promise.resolve({ courses: [] as CourseListItem[] }),
      ])
      setAssignments(a.assignments)
      setPublishable(c.courses.filter(x => x.status === 'published'))
    } catch {
      setAssignments([])
    }
  }, [schoolId, classId, canManage, getToken])

  useEffect(() => { load() }, [load])

  const act = async <T,>(key: string, fn: (token: string) => Promise<T>, success?: string): Promise<T | undefined> => {
    setBusy(key)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const result = await fn(token)
      if (success) addToast(success)
      return result
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message), 'error')
      return undefined
    } finally {
      setBusy(null)
    }
  }

  const assigned = new Set((assignments ?? []).map(a => a.journey_id))
  const options = publishable.filter(c => !assigned.has(c.journey_id))

  const doAssign = async () => {
    if (!pick) return
    const r = await act('assign', t => assignCourse(schoolId, classId, {
      journey_id: pick, due_at: toDueIso(due), tutor_enabled: tutor, quiz_required: quiz,
    }, t), 'Course assigned ✓')
    if (r) { setPick(''); setDue(''); setTutor(true); setQuiz(false); load() }
  }

  const patch = async (a: Assignment, body: { due_at?: string | null; tutor_enabled?: boolean; quiz_required?: boolean }) => {
    const r = await act(a.id, t => updateAssignment(schoolId, classId, a.id, body, t))
    // PATCH returns only the changed fields (due_at, settings, …) — merge them so
    // the course meta and progress summary already in state are preserved.
    if (r) setAssignments(list => (list ?? []).map(x => (x.id === a.id ? { ...x, ...r } : x)))
  }

  return (
    <div className="glass-card rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-2">
        <BookOpen size={15} className="text-violet-500" /> Courses
      </h3>

      {assignments === null ? (
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-violet-500" size={18} /></div>
      ) : assignments.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">No courses assigned yet.</p>
      ) : (
        <ul className="space-y-3">
          {assignments.map(a => {
            const d = dueLabel(a.due_at)
            return (
              <li key={a.id} className="rounded-xl border border-slate-200/70 dark:border-slate-700/50 p-3">
                <div className="flex items-start gap-3">
                  <span className="text-xl shrink-0" aria-hidden="true">{a.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">{a.title}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {a.progress.enrolled} student{a.progress.enrolled === 1 ? '' : 's'} ·{' '}
                      {a.progress.started} started · {a.progress.completed} finished · {a.progress.avg_percent}% avg
                    </p>
                  </div>
                  {d && (
                    <span className={clsx('text-xs font-medium shrink-0', d.overdue ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500 dark:text-slate-400')}>
                      Due {d.text}
                    </span>
                  )}
                  {canManage && (
                    confirmUnassign === a.id ? (
                      <span className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={async () => { if (await act(a.id, t => unassignCourse(schoolId, classId, a.id, t).then(() => true), 'Course unassigned')) { setConfirmUnassign(null); load() } }}
                          disabled={busy !== null} className="px-2 py-1 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white"
                        >Remove</button>
                        <button onClick={() => setConfirmUnassign(null)} className="px-2 py-1 rounded-lg text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">Cancel</button>
                      </span>
                    ) : (
                      <button
                        onClick={() => setConfirmUnassign(a.id)} disabled={busy !== null}
                        aria-label={`Unassign ${a.title}`} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 disabled:opacity-50 shrink-0"
                      ><Trash2 size={14} /></button>
                    )
                  )}
                </div>

                {canManage && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 pl-9">
                    <label className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                      Due
                      <input
                        type="date" value={toDateInput(a.due_at)} disabled={busy !== null}
                        onChange={e => patch(a, { due_at: toDueIso(e.target.value) })}
                        className={clsx(fieldCls, '!py-1 !px-2')}
                      />
                    </label>
                    <button
                      onClick={() => patch(a, { tutor_enabled: !a.settings.tutor_enabled })}
                      disabled={busy !== null}
                      className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border transition-colors',
                        a.settings.tutor_enabled
                          ? 'border-violet-300 dark:border-violet-500/40 text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/10'
                          : 'border-slate-200 dark:border-slate-700 text-slate-400')}
                    >Tutor {a.settings.tutor_enabled ? 'on' : 'off'}</button>
                    <button
                      onClick={() => patch(a, { quiz_required: !a.settings.quiz_required })}
                      disabled={busy !== null}
                      className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border transition-colors',
                        a.settings.quiz_required
                          ? 'border-amber-300 dark:border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10'
                          : 'border-slate-200 dark:border-slate-700 text-slate-400')}
                    >Quiz {a.settings.quiz_required ? 'required' : 'optional'}</button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {canManage && (
        <div className="mt-4 border-t border-slate-200/70 dark:border-slate-700/50 pt-4">
          {options.length === 0 ? (
            <p className="text-xs text-slate-400">
              {publishable.length === 0 ? 'Publish a course first to assign it here.' : 'Every published course is already assigned to this class.'}
            </p>
          ) : (
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex-1 min-w-[12rem]">
                <span className="text-xs text-slate-500 dark:text-slate-400">Assign a course</span>
                <select value={pick} onChange={e => setPick(e.target.value)} className={clsx(fieldCls, 'w-full mt-1')}>
                  <option value="">Choose a published course…</option>
                  {options.map(c => <option key={c.journey_id} value={c.journey_id}>{c.title}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-500 dark:text-slate-400">Due date (optional)
                <input type="date" value={due} onChange={e => setDue(e.target.value)} className={clsx(fieldCls, 'w-full mt-1')} />
              </label>
              <label className="text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1.5 pb-2">
                <input type="checkbox" checked={tutor} onChange={e => setTutor(e.target.checked)} className="accent-violet-600" /> Tutor on
              </label>
              <label className="text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1.5 pb-2">
                <input type="checkbox" checked={quiz} onChange={e => setQuiz(e.target.checked)} className="accent-violet-600" /> Quiz required
              </label>
              <button onClick={doAssign} disabled={!pick || busy !== null} className="btn-primary !py-2 !px-4 flex items-center gap-1.5">
                {busy === 'assign' ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Assign
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
