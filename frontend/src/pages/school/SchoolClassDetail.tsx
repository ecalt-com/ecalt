import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Archive, Loader2, Lock, Printer, RefreshCw, UserMinus, UserPlus } from 'lucide-react'
import clsx from 'clsx'
import ProfileAvatar from '../../components/family/ProfileAvatar'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  addClassTeacher, archiveClass, enrollStudents, formatJoinCode, getClass, listStaff, listStudents,
  removeClassTeacher, rotateClassCode, schoolErrorMessage, unenrollStudent, updateClass,
  type ClassDetail, type StaffMember, type Student,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 disabled:opacity-60'

// /school/classes/:classId (frontend-changes.md §5).
export default function SchoolClassDetail() {
  const { classId = '' } = useParams()
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [cls, setCls] = useState<ClassDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [edit, setEdit] = useState({ name: '', subject: '', academic_year: '' })
  const [staff, setStaff] = useState<StaffMember[]>([])
  const [teacherToAdd, setTeacherToAdd] = useState('')
  const [search, setSearch] = useState('')
  const [candidates, setCandidates] = useState<Student[]>([])
  const [confirmArchive, setConfirmArchive] = useState(false)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      const data = await getClass(school.id, classId, token)
      setCls(data)
      setEdit({ name: data.name, subject: data.subject ?? '', academic_year: data.academic_year ?? '' })
      setError(null)
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), "Couldn't load this class."))
    }
  }, [school.id, classId, getToken])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!cls?.can_manage) return
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try { setStaff((await listStaff(school.id, token)).members) } catch { /* teacher picker stays empty */ }
    })()
  }, [cls?.can_manage, school.id, getToken])

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

  const findStudents = async (e: React.FormEvent) => {
    e.preventDefault()
    const res = await act('search', token => listStudents(school.id, { q: search.trim() || undefined, status: 'active', limit: 20 }, token))
    if (res && cls) setCandidates(res.students.filter(s => !cls.students.some(cs => cs.uid === s.uid)))
  }

  if (error) return <div className="glass-card rounded-2xl p-5 text-sm text-rose-600 dark:text-rose-400" role="alert">{error}</div>
  if (!cls) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>

  const manage = cls.can_manage && !cls.archived
  const dirty = edit.name.trim() !== cls.name || edit.subject.trim() !== (cls.subject ?? '') || edit.academic_year.trim() !== (cls.academic_year ?? '')
  const teacherOptions = staff.filter(m => !cls.teachers.some(t => t.uid === m.uid))
  const withSecrets = cls.students.filter(s => s.has_secret).length

  return (
    <div className="space-y-5">
      <Link to="/school/classes" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400"><ArrowLeft size={12} /> All classes</Link>

      <div className="glass-card rounded-2xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{cls.name}{cls.archived && <span className="ml-2 text-xs font-normal text-slate-400">archived</span>}</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">{cls.students.length} students · {cls.grade !== null ? `Grade ${cls.grade === 0 ? 'KG' : cls.grade}` : 'No grade'}</p>
          </div>
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-wide text-slate-400">Class code</p>
            <p className="font-mono text-xl font-bold text-slate-900 dark:text-slate-100">{formatJoinCode(cls.join_code)}</p>
            {manage && (
              <button
                onClick={async () => { const r = await act('code', t => rotateClassCode(school.id, cls.id, t), 'New class code ✓'); if (r) load() }}
                disabled={busy !== null}
                className="mt-1 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-violet-600 disabled:opacity-50"
              >
                <RefreshCw size={11} /> New code
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Students sign in at <span className="font-medium text-slate-700 dark:text-slate-200">{window.location.host}/class</span> with this code, then pick their name and enter their picture password or PIN.
        </p>
        {manage && (
          <div className="flex flex-wrap gap-2">
            <button onClick={() => navigate(`/school/print/cards/${cls.id}`)} className="btn-primary !py-2 !px-4 flex items-center gap-1.5">
              <Printer size={14} /> Print login cards
            </button>
            {withSecrets < cls.students.length && (
              <p className="text-xs text-amber-700 dark:text-amber-300 self-center">
                {cls.students.length - withSecrets} student{cls.students.length - withSecrets === 1 ? " hasn't" : "s haven't"} got a sign-in yet — print cards to give them one.
              </p>
            )}
          </div>
        )}
      </div>

      {manage && (
        <form
          onSubmit={async e => {
            e.preventDefault()
            if (!dirty || !edit.name.trim()) return
            const r = await act('edit', t => updateClass(school.id, cls.id, {
              name: edit.name.trim(), subject: edit.subject.trim() || null, academic_year: edit.academic_year.trim() || null,
            }, t), 'Class saved ✓')
            if (r) setCls(r)
          }}
          className="glass-card rounded-2xl p-5 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
        >
          <label className="text-xs text-slate-600 dark:text-slate-400">Name
            <input value={edit.name} onChange={e => setEdit(v => ({ ...v, name: e.target.value }))} maxLength={80} className={clsx(fieldCls, 'w-full mt-1')} />
          </label>
          <label className="text-xs text-slate-600 dark:text-slate-400">Subject
            <input value={edit.subject} onChange={e => setEdit(v => ({ ...v, subject: e.target.value }))} maxLength={80} className={clsx(fieldCls, 'w-full mt-1')} />
          </label>
          <label className="text-xs text-slate-600 dark:text-slate-400">Academic year
            <input value={edit.academic_year} onChange={e => setEdit(v => ({ ...v, academic_year: e.target.value }))} maxLength={20} className={clsx(fieldCls, 'w-full mt-1')} />
          </label>
          <button type="submit" disabled={!dirty || busy !== null} className="btn-primary !py-2 sm:col-span-3 justify-self-start">Save</button>
        </form>
      )}

      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Teachers</h3>
        <ul className="space-y-2">
          {cls.teachers.map(t => (
            <li key={t.uid} className="flex items-center gap-3">
              <ProfileAvatar name={t.display_name} />
              <span className="flex-1 text-sm text-slate-700 dark:text-slate-200">{t.display_name ?? 'Teacher'} <span className="text-xs text-slate-400">{t.role === 'lead' ? 'lead' : 'co-teacher'}</span></span>
              {manage && (
                <button
                  onClick={async () => { if (await act(t.uid, tok => removeClassTeacher(school.id, cls.id, t.uid, tok).then(() => true))) load() }}
                  disabled={busy !== null} aria-label={`Remove ${t.display_name ?? 'teacher'} from this class`}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 disabled:opacity-50"
                ><UserMinus size={14} /></button>
              )}
            </li>
          ))}
          {cls.teachers.length === 0 && <li className="text-xs text-slate-500">No teachers yet.</li>}
        </ul>
        {manage && teacherOptions.length > 0 && (
          <div className="mt-3 flex gap-2">
            <label className="flex-1">
              <span className="sr-only">Add a teacher</span>
              <select value={teacherToAdd} onChange={e => setTeacherToAdd(e.target.value)} className={clsx(fieldCls, 'w-full')}>
                <option value="">Add a co-teacher…</option>
                {teacherOptions.map(m => <option key={m.uid} value={m.uid}>{m.display_name ?? m.email}</option>)}
              </select>
            </label>
            <button
              onClick={async () => { const r = await act('teacher', t => addClassTeacher(school.id, cls.id, teacherToAdd, 'co', t)); if (r) { setCls(r); setTeacherToAdd('') } }}
              disabled={!teacherToAdd || busy !== null} className="btn-ghost !px-3 flex items-center gap-1"
            ><UserPlus size={14} /> Add</button>
          </div>
        )}
      </div>

      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Students ({cls.students.length})</h3>
        <ul className="divide-y divide-slate-200/70 dark:divide-slate-700/50">
          {cls.students.map(s => {
            const locked = !!s.locked_until && new Date(s.locked_until) > new Date()
            return (
              <li key={s.uid} className="flex items-center gap-3 py-2.5">
                <ProfileAvatar name={s.display_name} avatar={s.avatar} />
                <span className="flex-1 min-w-0 text-sm text-slate-700 dark:text-slate-200 truncate">
                  {s.display_name}
                  {s.status === 'archived' && <span className="ml-1 text-xs text-slate-400">archived</span>}
                </span>
                {locked && <span className="text-xs text-rose-600 flex items-center gap-1"><Lock size={11} /> locked</span>}
                {!s.has_secret && <span className="text-xs text-amber-600">no sign-in yet</span>}
                {manage && (
                  <button
                    onClick={async () => { if (await act(s.uid, t => unenrollStudent(school.id, cls.id, s.uid, t).then(() => true))) load() }}
                    disabled={busy !== null} aria-label={`Remove ${s.display_name} from this class`}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 disabled:opacity-50"
                  ><UserMinus size={14} /></button>
                )}
              </li>
            )
          })}
          {cls.students.length === 0 && <li className="text-xs text-slate-500 py-2">No students in this class yet.</li>}
        </ul>

        {manage && (
          <div className="mt-4 border-t border-slate-200/70 dark:border-slate-700/50 pt-4">
            <form onSubmit={findStudents} className="flex gap-2">
              <label className="flex-1">
                <span className="sr-only">Find students to add</span>
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Find students to add" className={clsx(fieldCls, 'w-full')} />
              </label>
              <button type="submit" disabled={busy !== null} className="btn-ghost !px-3">Search</button>
            </form>
            {candidates.length > 0 && (
              <ul className="mt-2 space-y-1">
                {candidates.map(s => (
                  <li key={s.uid} className="flex items-center gap-3 text-sm">
                    <span className="flex-1 truncate text-slate-700 dark:text-slate-200">{s.display_name} <span className="text-xs text-slate-400">{s.classes.map(c => c.name).join(', ')}</span></span>
                    <button
                      onClick={async () => {
                        const r = await act(s.uid, t => enrollStudents(school.id, cls.id, [s.uid], t))
                        if (r) { setCls(r); setCandidates(c => c.filter(x => x.uid !== s.uid)) }
                      }}
                      disabled={busy !== null} className="text-xs font-medium text-violet-600 hover:underline disabled:opacity-50"
                    >Add</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {manage && (
        <div className="flex justify-end">
          {confirmArchive ? (
            <span className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Archive this class? Its students lose access to its courses.</span>
              <button
                onClick={async () => { if (await act('archive', t => archiveClass(school.id, cls.id, t).then(() => true), 'Class archived')) navigate('/school/classes') }}
                className="px-2 py-1 rounded-lg font-semibold bg-rose-600 hover:bg-rose-500 text-white"
              >Archive</button>
              <button onClick={() => setConfirmArchive(false)} className="px-2 py-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">Cancel</button>
            </span>
          ) : (
            <button onClick={() => setConfirmArchive(true)} className="text-xs text-slate-500 hover:text-rose-600 flex items-center gap-1"><Archive size={12} /> Archive class</button>
          )}
        </div>
      )}
    </div>
  )
}
