import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, FileText, Loader2, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  createCourse, estimateCourse, generateOutline, listDocuments, schoolErrorMessage,
  type CourseEstimate, type OutlineInputs, type SchoolDocument,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

// /school/courses/new (frontend-changes.md §8.1) — the create wizard.
export default function SchoolCourseNew() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [docs, setDocs] = useState<SchoolDocument[] | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [title, setTitle] = useState('')
  const [grade, setGrade] = useState('')
  const [subject, setSubject] = useState('')
  const [goal, setGoal] = useState('')
  const [targetSteps, setTargetSteps] = useState('')
  const [sessionMinutes, setSessionMinutes] = useState('')
  const [language, setLanguage] = useState('')
  const [followOrder, setFollowOrder] = useState(true)

  const [stage, setStage] = useState<'form' | 'estimate'>('form')
  const [busy, setBusy] = useState(false)
  const [jid, setJid] = useState<string | null>(null)
  const [estimate, setEstimate] = useState<CourseEstimate | null>(null)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      const all = (await listDocuments(school.id, token)).documents
      setDocs(all.filter(d => d.status === 'ready'))
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
      setDocs([])
    }
  }, [school.id, getToken, addToast])

  useEffect(() => { load() }, [load])

  const toggle = (id: string) => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]))

  const buildInputs = (): OutlineInputs => {
    const i: OutlineInputs = { follow_document_order: followOrder }
    if (grade !== '') i.grade = Number(grade)
    if (subject.trim()) i.subject = subject.trim()
    if (goal.trim()) i.goal = goal.trim()
    if (targetSteps !== '') i.target_steps = Number(targetSteps)
    if (sessionMinutes !== '') i.session_minutes = Number(sessionMinutes)
    if (language.trim()) i.language = language.trim()
    return i
  }

  const toEstimate = async () => {
    const token = await getToken()
    if (!token) return
    setBusy(true)
    try {
      const course = await createCourse(school.id, { title: title.trim(), document_ids: picked }, token)
      setJid(course.journey_id)
      setEstimate(await estimateCourse(school.id, course.journey_id, token))
      setStage('estimate')
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    } finally { setBusy(false) }
  }

  const startOutline = async () => {
    const token = await getToken()
    if (!token || !jid) return
    setBusy(true)
    try {
      await generateOutline(school.id, jid, buildInputs(), token)
      navigate(`/school/courses/${jid}`)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
      setBusy(false)
    }
  }

  const budgetDollars = school.monthly_ai_budget_cents !== undefined
    ? (school.monthly_ai_budget_cents / 100).toFixed(2) : null

  if (stage === 'estimate' && estimate) {
    return (
      <div className="max-w-lg mx-auto space-y-5">
        <button onClick={() => setStage('form')} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
          <ArrowLeft size={14} /> Back
        </button>
        <div className="glass-card rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
            <Sparkles size={22} className="text-violet-600 dark:text-violet-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Ready to generate the outline</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              We'll read {estimate.chunk_count} section{estimate.chunk_count === 1 ? '' : 's'} from {estimate.document_count} document{estimate.document_count === 1 ? '' : 's'}.
            </p>
          </div>
          <div className="flex items-center justify-center gap-6 text-sm">
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400">Estimated cost</p>
              <p className="font-bold text-slate-900 dark:text-slate-100">${(estimate.estimated_cost_cents / 100).toFixed(2)}</p>
            </div>
            {budgetDollars && (
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Monthly budget</p>
                <p className="font-bold text-slate-900 dark:text-slate-100">${budgetDollars}</p>
              </div>
            )}
          </div>
          <button onClick={startOutline} disabled={busy} className="btn-primary w-full flex items-center justify-center gap-2">
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Generate outline
          </button>
          <p className="text-xs text-slate-400">You'll review and edit the outline before any step content is written.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link to="/school/courses" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
        <ArrowLeft size={14} /> Courses
      </Link>

      {/* 1. Material */}
      <section className="glass-card rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-1">1. Source material</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Pick the document(s) to build the course from.</p>
        {docs === null ? (
          <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>
        ) : docs.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No ready documents yet. <Link to="/school/materials" className="text-violet-600 dark:text-violet-400 font-medium">Upload one in Materials</Link>, then come back.
          </p>
        ) : (
          <ul className="space-y-2">
            {docs.map(d => {
              const on = picked.includes(d.id)
              return (
                <li key={d.id}>
                  <button type="button" onClick={() => toggle(d.id)}
                    className={clsx('w-full flex items-center gap-3 p-3 rounded-xl border transition-colors text-left',
                      on ? 'border-violet-400 bg-violet-50 dark:bg-violet-500/10' : 'border-slate-200 dark:border-slate-700 hover:border-violet-300')}>
                    <FileText size={16} className="text-slate-400 shrink-0" />
                    <span className="text-sm text-slate-800 dark:text-slate-100 truncate flex-1">{d.filename}</span>
                    {d.page_count ? <span className="text-xs text-slate-400">{d.page_count}p</span> : null}
                    {on && <CheckCircle2 size={16} className="text-violet-500 shrink-0" />}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* 2. Setup */}
      <section className="glass-card rounded-2xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">2. Course setup</h2>
        <label className="block text-xs text-slate-600 dark:text-slate-400">Course title
          <input value={title} onChange={e => setTitle(e.target.value)} maxLength={120} placeholder="The Water Cycle" className={clsx(fieldCls, 'mt-1')} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-slate-600 dark:text-slate-400">Grade
            <select value={grade} onChange={e => setGrade(e.target.value)} className={clsx(fieldCls, 'mt-1')}>
              <option value="">Any</option>
              {Array.from({ length: 13 }, (_, g) => <option key={g} value={g}>{g === 0 ? 'KG' : g}</option>)}
            </select>
          </label>
          <label className="block text-xs text-slate-600 dark:text-slate-400">Subject
            <input value={subject} onChange={e => setSubject(e.target.value)} maxLength={120} placeholder="Science" className={clsx(fieldCls, 'mt-1')} />
          </label>
        </div>
        <label className="block text-xs text-slate-600 dark:text-slate-400">Learning goal
          <input value={goal} onChange={e => setGoal(e.target.value)} maxLength={600} placeholder="By the end, students can explain…" className={clsx(fieldCls, 'mt-1')} />
        </label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block text-xs text-slate-600 dark:text-slate-400">Steps
            <input type="number" min={1} max={30} value={targetSteps} onChange={e => setTargetSteps(e.target.value)} placeholder="auto" className={clsx(fieldCls, 'mt-1')} />
          </label>
          <label className="block text-xs text-slate-600 dark:text-slate-400">Minutes / lesson
            <input type="number" min={5} max={240} value={sessionMinutes} onChange={e => setSessionMinutes(e.target.value)} placeholder="auto" className={clsx(fieldCls, 'mt-1')} />
          </label>
          <label className="block text-xs text-slate-600 dark:text-slate-400">Language
            <input value={language} onChange={e => setLanguage(e.target.value)} maxLength={40} placeholder="English" className={clsx(fieldCls, 'mt-1')} />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
          <input type="checkbox" checked={followOrder} onChange={e => setFollowOrder(e.target.checked)} className="accent-violet-600" />
          Follow the document's order
        </label>
      </section>

      <div className="flex justify-end">
        <button onClick={toEstimate} disabled={busy || !title.trim() || picked.length === 0}
          className="btn-primary flex items-center gap-2 disabled:opacity-50">
          {busy ? <Loader2 size={16} className="animate-spin" /> : null} Continue to estimate
        </button>
      </div>
    </div>
  )
}
