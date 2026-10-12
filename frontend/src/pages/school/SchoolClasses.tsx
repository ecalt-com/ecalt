import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, Loader2, Plus, Users, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import { createClass, formatJoinCode, listClasses, schoolErrorMessage, type SchoolClass } from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

function CreateClassModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const [name, setName] = useState('')
  const [grade, setGrade] = useState('')
  const [subject, setSubject] = useState('')
  const [year, setYear] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const created = await createClass(school.id, {
        name: name.trim(), grade: grade === '' ? null : Number(grade),
        subject: subject.trim() || null, academic_year: year.trim() || null,
      }, token)
      onCreated(created.id)
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Create a class">
      <form onSubmit={submit} className="glass-card rounded-3xl p-6 sm:p-7 max-w-md w-full shadow-2xl space-y-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Create a class</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={16} /></button>
        </div>
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Class name</span>
          <input value={name} onChange={e => setName(e.target.value)} maxLength={80} required autoFocus placeholder="6A Science" className={fieldCls} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Grade</span>
            <select value={grade} onChange={e => setGrade(e.target.value)} className={fieldCls}>
              <option value="">—</option>
              {Array.from({ length: 13 }, (_, g) => <option key={g} value={g}>{g === 0 ? 'KG' : g}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Academic year</span>
            <input value={year} onChange={e => setYear(e.target.value)} maxLength={20} placeholder="2026–27" className={fieldCls} />
          </label>
        </div>
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Subject</span>
          <input value={subject} onChange={e => setSubject(e.target.value)} maxLength={80} placeholder="optional" className={fieldCls} />
        </label>
        <p className="text-xs text-slate-500 dark:text-slate-400">You'll be the class's lead teacher.</p>
        {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
        <button type="submit" disabled={busy || !name.trim()} className="w-full btn-primary flex items-center justify-center gap-2">
          {busy && <Loader2 size={14} className="animate-spin" />} Create class
        </button>
      </form>
    </div>
  )
}

// /school/classes (frontend-changes.md §5).
export default function SchoolClasses() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [classes, setClasses] = useState<SchoolClass[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      setClasses((await listClasses(school.id, token)).classes)
      setError(null)
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), "Couldn't load classes. Please refresh and try again."))
    }
  }, [school.id, getToken])

  useEffect(() => { load() }, [load])

  const mine = classes?.filter(c => c.is_mine) ?? []
  const others = classes?.filter(c => !c.is_mine) ?? []

  const section = (title: string, list: SchoolClass[]) => list.length > 0 && (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">{title}</h2>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {list.map(c => (
          <li key={c.id}>
            <Link to={`/school/classes/${c.id}`} className="glass-card rounded-2xl p-4 flex items-center justify-between gap-3 hover:border-violet-300 transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">{c.name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                  {[c.grade !== null ? `Grade ${c.grade === 0 ? 'KG' : c.grade}` : null, c.subject,
                    c.teachers.map(t => t.display_name).filter(Boolean).join(', ') || 'No teacher'].filter(Boolean).join(' · ')}
                </p>
                <p className="text-xs text-slate-400 mt-1 font-mono">{formatJoinCode(c.join_code)}</p>
              </div>
              <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 shrink-0">
                <Users size={13} /> {c.student_count} <ChevronRight size={14} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button onClick={() => setShowCreate(true)} className="btn-primary !py-2 !px-4 flex items-center gap-1.5"><Plus size={14} /> Create class</button>
      </div>
      {error && <div className="glass-card rounded-2xl p-5 text-sm text-rose-600 dark:text-rose-400" role="alert">{error}</div>}
      {classes === null && !error && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>}
      {classes?.length === 0 && (
        <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-500 dark:text-slate-400">
          No classes yet. Create one, or import students with a class column.
        </div>
      )}
      {section('My classes', mine)}
      <div className={clsx(mine.length > 0 && 'pt-1')}>{section(mine.length ? 'Other classes' : 'Classes', others)}</div>
      {showCreate && (
        <CreateClassModal
          onClose={() => setShowCreate(false)}
          onCreated={id => { setShowCreate(false); addToast('Class created ✓'); navigate(`/school/classes/${id}`) }}
        />
      )}
    </div>
  )
}
