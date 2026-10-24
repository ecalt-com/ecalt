import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Copy, Loader2, Plus, Archive } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  archiveCourse, duplicateCourse, listCourses, schoolErrorMessage,
  type CourseListItem, type CourseStatus,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const STATUS_CHIP: Record<CourseStatus, string> = {
  draft: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  published: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  archived: 'bg-slate-200 text-slate-600 dark:bg-slate-700/50 dark:text-slate-300',
}

const DRAFT_HINT: Record<string, string> = {
  empty: 'No outline yet',
  outlining: 'Reading your document…',
  outline_ready: 'Outline ready to review',
  building: 'Building step content…',
  built: 'Built — ready to publish',
  outline_failed: 'Outline failed',
  build_failed: 'Build failed',
  published: 'Published',
}

const FILTERS: { id: CourseStatus | 'all'; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'draft', label: 'Drafts' },
  { id: 'published', label: 'Published' },
  { id: 'archived', label: 'Archived' },
]

// /school/courses (frontend-changes.md §8.5) — the course library.
export default function SchoolCourses() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [items, setItems] = useState<CourseListItem[] | null>(null)
  const [filter, setFilter] = useState<CourseStatus | 'all'>('all')
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      setItems((await listCourses(school.id, token)).courses)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
      setItems([])
    }
  }, [school.id, getToken, addToast])

  useEffect(() => { load() }, [load])

  const duplicate = async (c: CourseListItem) => {
    const token = await getToken()
    if (!token) return
    setBusy(c.journey_id)
    try {
      const dup = await duplicateCourse(school.id, c.journey_id, token)
      addToast('Course duplicated ✓')
      navigate(`/school/courses/${dup.journey_id}`)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    } finally { setBusy(null) }
  }

  const archive = async (c: CourseListItem) => {
    const token = await getToken()
    if (!token) return
    if (!window.confirm(`Archive "${c.title}"? Students will no longer see it.`)) return
    setBusy(c.journey_id)
    try {
      await archiveCourse(school.id, c.journey_id, token)
      addToast('Course archived')
      await load()
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    } finally { setBusy(null) }
  }

  const shown = (items ?? []).filter(c => filter === 'all' || c.status === filter)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex gap-1 p-1 glass-card rounded-xl">
          {FILTERS.map(f => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={clsx('px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                filter === f.id ? 'bg-violet-600 text-white' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200')}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button onClick={() => navigate('/school/courses/new')} className="btn-primary !py-2 !px-4 flex items-center gap-1.5">
          <Plus size={14} /> New course
        </button>
      </div>

      {items === null ? (
        <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
      ) : shown.length === 0 ? (
        <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-500 dark:text-slate-400">
          {filter === 'all'
            ? 'No courses yet. Upload a PDF or Word document in Materials, then build a course from it.'
            : `No ${filter} courses.`}
        </div>
      ) : (
        <ul className="space-y-2">
          {shown.map(c => (
            <li key={c.journey_id}>
              <div className="glass-card rounded-2xl p-4 flex items-center gap-3">
                <button
                  onClick={() => navigate(`/school/courses/${c.journey_id}`)}
                  className="flex items-center gap-3 min-w-0 flex-1 text-left"
                >
                  <div className="w-9 h-9 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center shrink-0">
                    <BookOpen size={16} className="text-violet-600 dark:text-violet-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{c.title}</span>
                      <span className={clsx('text-xs px-2 py-0.5 rounded-full capitalize', STATUS_CHIP[c.status])}>
                        {c.status === 'published' && c.published_version ? `Published v${c.published_version}` : c.status}
                      </span>
                    </div>
                    {c.draft_status && c.status !== 'published' && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{DRAFT_HINT[c.draft_status] ?? c.draft_status}</p>
                    )}
                  </div>
                </button>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => duplicate(c)} disabled={busy === c.journey_id} aria-label="Duplicate"
                    className="p-2 rounded-lg text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 disabled:opacity-50">
                    {busy === c.journey_id ? <Loader2 size={15} className="animate-spin" /> : <Copy size={15} />}
                  </button>
                  {c.status !== 'archived' && (
                    <button onClick={() => archive(c)} disabled={busy === c.journey_id} aria-label="Archive"
                      className="p-2 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 disabled:opacity-50">
                      <Archive size={15} />
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
