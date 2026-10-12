import { useCallback, useEffect, useState } from 'react'
import { Archive, Download, KeyRound, Loader2, Lock, Plus, RotateCcw, Search, Trash2, Upload, X } from 'lucide-react'
import clsx from 'clsx'
import ProfileAvatar from '../../components/family/ProfileAvatar'
import SecretView from '../../components/school/SecretView'
import StudentImportWizard from '../../components/school/StudentImportWizard'
import { useAuth } from '../../lib/AuthContext'
import { useSchool } from '../../lib/SchoolContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  archiveStudents, createStudent, deleteStudent, exportStudent, listClasses, listStudents, resetStudentSecret,
  restoreStudent, schoolErrorMessage,
  type SchoolClass, type SecretKind, type Student, type StudentList, type StudentSecret,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'
const PAGE = 50

const isLocked = (s: Student) => !!s.locked_until && new Date(s.locked_until) > new Date()

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className="glass-card rounded-3xl p-6 sm:p-7 max-w-lg w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4 gap-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

// One-time reveal after creating a student or resetting their sign-in.
export function SecretReveal({ name, kind, secret, onClose }: {
  name: string; kind: SecretKind; secret: StudentSecret; onClose: () => void
}) {
  return (
    <Modal title={`${name}'s sign-in`} onClose={onClose}>
      <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">
        {kind === 'picture' ? 'Their picture password, in this order:' : 'Their PIN:'}
      </p>
      <div className="flex justify-center py-3"><SecretView kind={kind} secret={secret} /></div>
      <p className="mt-4 text-xs text-amber-700 dark:text-amber-300">
        Write it down now — you won't see it again. You can also print login cards from the class page,
        which gives the class new sign-ins.
      </p>
      <button onClick={onClose} className="w-full btn-primary mt-5">Done</button>
    </Modal>
  )
}

function AddStudentModal({ classes, onClose, onCreated }: {
  classes: SchoolClass[]
  onClose: () => void
  onCreated: (name: string, kind: SecretKind, secret: StudentSecret) => void
}) {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const [name, setName] = useState('')
  const [grade, setGrade] = useState('')
  const [roll, setRoll] = useState('')
  const [kind, setKind] = useState<'' | SecretKind>('')
  const [classIds, setClassIds] = useState<string[]>([])
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
      const created = await createStudent(school.id, {
        display_name: name.trim(),
        grade: grade === '' ? null : Number(grade),
        external_ref: roll.trim() || null,
        ...(kind ? { secret_kind: kind } : {}),
        class_ids: classIds,
      }, token)
      onCreated(created.display_name, created.secret_kind, created.secret)
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Add a student" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Name</span>
          <input value={name} onChange={e => setName(e.target.value)} maxLength={80} required autoFocus placeholder="First name + last initial" className={clsx(fieldCls, 'w-full')} />
          <span className="block mt-1 text-xs text-slate-500 dark:text-slate-400">Keep it short — the class sign-in page shows it to classmates.</span>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Grade</span>
            <select value={grade} onChange={e => setGrade(e.target.value)} className={clsx(fieldCls, 'w-full')}>
              <option value="">—</option>
              {Array.from({ length: 13 }, (_, g) => <option key={g} value={g}>{g === 0 ? 'KG' : g}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Roll number</span>
            <input value={roll} onChange={e => setRoll(e.target.value)} maxLength={40} placeholder="optional" className={clsx(fieldCls, 'w-full')} />
          </label>
        </div>
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Sign-in</span>
          <select value={kind} onChange={e => setKind(e.target.value as '' | SecretKind)} className={clsx(fieldCls, 'w-full')}>
            <option value="">Automatic (pictures up to grade 4, PIN after)</option>
            <option value="picture">Picture password</option>
            <option value="pin">6-digit PIN</option>
          </select>
        </label>
        {classes.length > 0 && (
          <fieldset>
            <legend className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">Classes</legend>
            <div className="flex flex-wrap gap-2">
              {classes.map(c => {
                const on = classIds.includes(c.id)
                return (
                  <button
                    type="button" key={c.id} aria-pressed={on}
                    onClick={() => setClassIds(ids => on ? ids.filter(i => i !== c.id) : [...ids, c.id])}
                    className={clsx('px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
                      on ? 'bg-violet-600 border-violet-600 text-white' : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-violet-400')}
                  >
                    {c.name}
                  </button>
                )
              })}
            </div>
          </fieldset>
        )}
        {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
        <button type="submit" disabled={busy || !name.trim()} className="w-full btn-primary flex items-center justify-center gap-2">
          {busy && <Loader2 size={14} className="animate-spin" />} Add student
        </button>
      </form>
    </Modal>
  )
}

// /school/students (frontend-changes.md §4).
export default function SchoolStudents() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { role } = useSchool()
  const { addToast } = useToast()

  const [data, setData] = useState<StudentList | null>(null)
  const [students, setStudents] = useState<Student[]>([])
  const [classes, setClasses] = useState<SchoolClass[]>([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<'active' | 'archived'>('active')
  const [classFilter, setClassFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [reveal, setReveal] = useState<{ name: string; kind: SecretKind; secret: StudentSecret } | null>(null)

  const load = useCallback(async (offset = 0) => {
    setLoading(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await listStudents(school.id, { q: q.trim() || undefined, status, class_id: classFilter || undefined, limit: PAGE, offset }, token)
      setData(res)
      setStudents(prev => offset === 0 ? res.students : [...prev, ...res.students])
      setLoadError(null)
    } catch (err) {
      setLoadError(schoolErrorMessage(apiErrorCode(err), "Couldn't load students. Please refresh and try again."))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [school.id, status, classFilter, getToken])

  useEffect(() => { load(0) }, [load])

  useEffect(() => {
    (async () => {
      const token = await getToken()
      if (!token) return
      try { setClasses((await listClasses(school.id, token)).classes) } catch { /* filter just stays empty */ }
    })()
  }, [school.id, getToken])

  const act = async <T,>(key: string, fn: (token: string) => Promise<T>): Promise<T | undefined> => {
    setBusy(key)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      return await fn(token)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message), 'error')
      return undefined
    } finally {
      setBusy(null)
    }
  }

  const resetSignIn = async (s: Student) => {
    const res = await act(s.uid, token => resetStudentSecret(school.id, s.uid, undefined, token))
    if (res) { setReveal({ name: s.display_name, kind: res.secret_kind, secret: res.secret }); load(0) }
  }

  const archive = async (s: Student) => {
    if (await act(s.uid, token => archiveStudents(school.id, [s.uid], token))) { addToast(`${s.display_name} archived`); load(0) }
  }

  const restore = async (s: Student) => {
    if (await act(s.uid, token => restoreStudent(school.id, s.uid, token))) { addToast(`${s.display_name} restored ✓`); load(0) }
  }

  const remove = async (s: Student) => {
    setConfirmDelete(null)
    const done = await act(s.uid, token => deleteStudent(school.id, s.uid, token).then(() => true))
    if (done) { addToast(`${s.display_name} and all their data were deleted`); load(0) }
  }

  const download = async (s: Student) => {
    const data = await act(s.uid, token => exportStudent(school.id, s.uid, token))
    if (!data) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `ecalt-student-${s.display_name.replace(/\W+/g, '-').toLowerCase()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const canManage = data?.can_manage ?? false
  const isAdmin = role === 'owner' || role === 'admin'
  const selectableClasses = isAdmin ? classes : classes.filter(c => c.is_mine)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <form onSubmit={e => { e.preventDefault(); load(0) }} className="flex items-center gap-2 flex-1 min-w-[220px]">
          <label className="relative flex-1">
            <span className="sr-only">Search students</span>
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search name or roll number" className={clsx(fieldCls, 'w-full !pl-9')} />
          </label>
        </form>
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)} className={fieldCls} aria-label="Filter by class">
          <option value="">All classes</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={status} onChange={e => setStatus(e.target.value as 'active' | 'archived')} className={fieldCls} aria-label="Filter by status">
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        {data && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {data.total} {status} student{data.total === 1 ? '' : 's'} · {data.seats_used} of {data.seat_limit} seats used
          </p>
        )}
        {canManage && (
          <div className="flex gap-2">
            <button onClick={() => setShowImport(true)} className="btn-ghost flex items-center gap-1.5 !px-3"><Upload size={14} /> Import CSV</button>
            <button onClick={() => setShowAdd(true)} className="btn-primary !py-2 !px-4 flex items-center gap-1.5"><Plus size={14} /> Add student</button>
          </div>
        )}
      </div>

      {!school.dpa_accepted && canManage && (
        <p className="text-xs text-amber-700 dark:text-amber-300">Students can be added once the school's owner accepts the data processing agreement (Settings).</p>
      )}
      {loadError && <div className="glass-card rounded-2xl p-5 text-sm text-rose-600 dark:text-rose-400" role="alert">{loadError}</div>}

      {data && students.length === 0 && !loading && (
        <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-500 dark:text-slate-400">
          {q || classFilter ? 'No students match.' : status === 'archived' ? 'No archived students.' : 'No students yet.'}
        </div>
      )}

      {students.length > 0 && (
        <ul className="glass-card rounded-2xl p-2 divide-y divide-slate-200/70 dark:divide-slate-700/50">
          {students.map(s => (
            <li key={s.uid} className="flex items-center gap-3 px-3 py-3 flex-wrap">
              <ProfileAvatar name={s.display_name} avatar={s.avatar} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{s.display_name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                  {[s.grade !== null ? `Grade ${s.grade === 0 ? 'KG' : s.grade}` : null, s.external_ref ? `Roll ${s.external_ref}` : null,
                    s.classes.map(c => c.name).join(', ') || 'No class'].filter(Boolean).join(' · ')}
                </p>
              </div>
              <span className={clsx('text-xs px-2 py-0.5 rounded-full flex items-center gap-1',
                isLocked(s) ? 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300'
                  : s.has_secret ? 'bg-slate-100 text-slate-600 dark:bg-slate-700/50 dark:text-slate-300'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300')}>
                {isLocked(s) ? <><Lock size={10} /> Locked</> : !s.has_secret ? 'No sign-in yet' : s.secret_kind === 'picture' ? 'Pictures' : 'PIN'}
              </span>

              {confirmDelete === s.uid ? (
                <span className="flex items-center gap-1.5 text-xs">
                  <span className="text-slate-500 dark:text-slate-400">Delete all their data?</span>
                  <button onClick={() => remove(s)} className="px-2 py-1 rounded-lg font-semibold bg-rose-600 hover:bg-rose-500 text-white">Delete</button>
                  <button onClick={() => setConfirmDelete(null)} className="px-2 py-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">Cancel</button>
                </span>
              ) : (
                <span className="flex items-center gap-0.5">
                  {busy === s.uid && <Loader2 size={14} className="animate-spin text-violet-500 mx-1" />}
                  {s.status === 'active' && (
                    <button onClick={() => resetSignIn(s)} disabled={busy !== null} title="New sign-in (also unlocks)" aria-label={`New sign-in for ${s.display_name}`}
                      className="p-2 rounded-lg text-slate-500 hover:text-violet-600 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"><KeyRound size={14} /></button>
                  )}
                  {isAdmin && (
                    <button onClick={() => download(s)} disabled={busy !== null} title="Export their data" aria-label={`Export ${s.display_name}'s data`}
                      className="p-2 rounded-lg text-slate-500 hover:text-violet-600 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"><Download size={14} /></button>
                  )}
                  {canManage && (s.status === 'active' ? (
                    <button onClick={() => archive(s)} disabled={busy !== null} title="Archive (blocks sign-in, keeps data)" aria-label={`Archive ${s.display_name}`}
                      className="p-2 rounded-lg text-slate-500 hover:text-amber-600 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"><Archive size={14} /></button>
                  ) : (
                    <button onClick={() => restore(s)} disabled={busy !== null} title="Restore" aria-label={`Restore ${s.display_name}`}
                      className="p-2 rounded-lg text-slate-500 hover:text-emerald-600 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"><RotateCcw size={14} /></button>
                  ))}
                  {canManage && (
                    <button onClick={() => setConfirmDelete(s.uid)} disabled={busy !== null} title="Delete" aria-label={`Delete ${s.display_name}`}
                      className="p-2 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"><Trash2 size={14} /></button>
                  )}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {loading && <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>}
      {!loading && data && students.length < data.total && (
        <button onClick={() => load(students.length)} className="btn-ghost mx-auto block">Show more</button>
      )}

      {showAdd && (
        <AddStudentModal
          classes={selectableClasses}
          onClose={() => setShowAdd(false)}
          onCreated={(name, kind, secret) => { setShowAdd(false); setReveal({ name, kind, secret }); load(0) }}
        />
      )}
      {showImport && (
        <StudentImportWizard onClose={() => setShowImport(false)} onImported={() => { load(0) }} />
      )}
      {reveal && <SecretReveal {...reveal} onClose={() => setReveal(null)} />}
    </div>
  )
}
