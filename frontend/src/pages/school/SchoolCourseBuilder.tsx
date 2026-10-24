import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, ChevronUp, Eye, History,
  Loader2, Pencil, Plus, RefreshCw, Rocket, Trash2, X,
} from 'lucide-react'
import clsx from 'clsx'
import MarkdownContent from '../../components/MarkdownContent'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import { useSchoolJob } from '../../lib/useSchoolJob'
import {
  addCourseStep, approveOutline, cancelSchoolJob, deleteCourseStep, DRAFT_BUSY, duplicateCourse,
  getCourse, listCourseVersions, patchCourseStep, publishCourse,
  regenerateCourseStep, reorderCourseSteps, restoreCourseVersion, schoolErrorMessage,
  type Course, type CourseStep, type CourseVersion,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className="glass-card rounded-2xl p-5 max-w-md w-full max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

function stepBadge(s: CourseStep) {
  if (s.flags?.length) return { label: 'Needs check', cls: 'text-amber-600 dark:text-amber-400', icon: <AlertTriangle size={12} /> }
  if (s.edited_by_teacher || s.origin === 'teacher') return { label: 'Edited', cls: 'text-sky-600 dark:text-sky-400', icon: <Pencil size={12} /> }
  return { label: 'AI', cls: 'text-slate-400', icon: <CheckCircle2 size={12} /> }
}

// /school/courses/:courseId (frontend-changes.md §8.2–8.5).
export default function SchoolCourseBuilder() {
  const { courseId = '' } = useParams()
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()

  const [course, setCourse] = useState<Course | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [buildJobId, setBuildJobId] = useState<string | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [showPublish, setShowPublish] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [working, setWorking] = useState(false)

  const reload = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      setCourse(await getCourse(school.id, courseId, token))
      setError(null)
    } catch (err) {
      setError(apiErrorCode(err) ?? 'unknown')
    }
  }, [school.id, courseId, getToken])

  useEffect(() => { reload() }, [reload])

  const draft = course?.draft ?? null
  const busy = !!draft && DRAFT_BUSY.includes(draft.status)

  // Poll the course while a job is running (works even without a job id, e.g.
  // after navigating in from the create wizard mid-outline).
  useEffect(() => {
    if (!busy) return
    const t = window.setInterval(reload, 3000)
    return () => window.clearInterval(t)
  }, [busy, reload])

  // When we started a build in-session, poll the job for its progress numbers.
  const job = useSchoolJob(school.id, busy ? buildJobId : null, () => { setBuildJobId(null); reload() })

  // Centralised mutation runner: applies the returned course, handles conflicts.
  const run = useCallback(async (fn: (token: string, revision: number) => Promise<Course>) => {
    const token = await getToken()
    if (!token || !course?.draft) return
    setWorking(true)
    try {
      setCourse(await fn(token, course.draft.revision))
    } catch (err) {
      const code = apiErrorCode(err)
      if (code === 'draft_conflict') { addToast('This course changed elsewhere — reloading.', 'info'); await reload() }
      else addToast(schoolErrorMessage(code), 'error')
    } finally { setWorking(false) }
  }, [getToken, course, addToast, reload])

  const steps = draft?.steps ?? []
  const selected = useMemo(() => steps.find(s => s.id === sel) ?? steps[0] ?? null, [steps, sel])

  // ── Loading / error / published-no-draft ────────────────────────────────
  if (!course && !error) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-violet-500" /></div>
  if (error) {
    return (
      <div className="glass-card rounded-2xl p-6 text-center space-y-3">
        <p className="text-sm text-rose-600 dark:text-rose-400">{schoolErrorMessage(error, "Couldn't load this course.")}</p>
        <Link to="/school/courses" className="text-sm text-violet-600 dark:text-violet-400">← Back to courses</Link>
      </div>
    )
  }
  const c = course!

  const header = (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <Link to="/school/courses" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
        <ArrowLeft size={14} /> Courses
      </Link>
      <div className="flex items-center gap-2">
        <button onClick={() => setShowVersions(true)} className="btn-ghost !py-1.5 !px-3 flex items-center gap-1.5 text-sm">
          <History size={14} /> Versions
        </button>
        {draft?.status === 'built' && (
          <button onClick={() => setShowPublish(true)} className="btn-primary !py-1.5 !px-3 flex items-center gap-1.5 text-sm">
            <Rocket size={14} /> Publish
          </button>
        )}
      </div>
    </div>
  )

  // ── Busy: outline / build in progress ───────────────────────────────────
  if (busy) {
    const done = job?.progress?.steps_done
    const total = job?.progress?.steps_total
    const pct = done !== undefined && total ? Math.round((done / total) * 100) : null
    const outlining = draft!.status === 'outlining'
    return (
      <div className="space-y-5">
        {header}
        <div className="glass-card rounded-2xl p-8 text-center space-y-4">
          <Loader2 size={28} className="animate-spin text-violet-500 mx-auto" />
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {outlining ? 'Reading your document…' : 'Building step content…'}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {outlining ? 'Drafting a grounded outline from your material.' : 'Writing each step from the source, then fact-checking it.'}
            </p>
          </div>
          {pct !== null && (
            <div className="max-w-sm mx-auto">
              <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                <div className="h-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{done} / {total} steps</p>
            </div>
          )}
          {buildJobId && (
            <button
              onClick={async () => { const t = await getToken(); if (t && buildJobId) { await cancelSchoolJob(school.id, buildJobId, t); addToast('Cancelling…'); } }}
              className="text-xs text-slate-500 hover:text-rose-600 dark:text-slate-400"
            >Cancel</button>
          )}
          <p className="text-xs text-slate-400">You can leave this page — it'll keep working.</p>
        </div>
      </div>
    )
  }

  // ── Published with no working draft ─────────────────────────────────────
  if (c.status === 'published' && !draft) {
    return (
      <div className="space-y-5">
        {header}
        <div className="glass-card rounded-2xl p-6 text-center space-y-3">
          <CheckCircle2 size={26} className="text-emerald-500 mx-auto" />
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{c.title}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">Published{c.published_version ? ` (v${c.published_version})` : ''} and live for assigned classes.</p>
          <button
            onClick={async () => { const t = await getToken(); if (!t) return; setWorking(true); try { const d = await duplicateCourse(school.id, c.journey_id, t); navigate(`/school/courses/${d.journey_id}`) } finally { setWorking(false) } }}
            disabled={working}
            className="btn-primary inline-flex items-center gap-2"
          >{working ? <Loader2 size={16} className="animate-spin" /> : <Pencil size={16} />} Edit as a new draft</button>
        </div>
        {showVersions && <VersionsDrawer schoolId={school.id} jid={c.journey_id} onClose={() => setShowVersions(false)} onRestored={(nc) => { setShowVersions(false); setCourse(nc) }} />}
      </div>
    )
  }

  // ── Outline review ──────────────────────────────────────────────────────
  if (draft?.status === 'outline_ready' || draft?.status === 'outline_failed') {
    if (draft.status === 'outline_failed') {
      return (
        <div className="space-y-5">{header}
          <div className="glass-card rounded-2xl p-6 text-center text-sm text-rose-600 dark:text-rose-400">
            The outline couldn't be generated. Try again from the course list, or check the source document.
          </div>
        </div>
      )
    }
    const skipped = draft.meta.skipped_sections ?? []
    const approve = async () => {
      const token = await getToken(); if (!token) return
      setWorking(true)
      try { const h = await approveOutline(school.id, c.journey_id, token); setBuildJobId(h.job_id); await reload() }
      catch (err) { addToast(schoolErrorMessage(apiErrorCode(err)), 'error') }
      finally { setWorking(false) }
    }
    const move = (id: string, dir: -1 | 1) => {
      const order = steps.map(s => s.id)
      const i = order.indexOf(id); const j = i + dir
      if (j < 0 || j >= order.length) return
      ;[order[i], order[j]] = [order[j], order[i]]
      run((t, rev) => reorderCourseSteps(school.id, c.journey_id, order, rev, t))
    }
    return (
      <div className="space-y-5">
        {header}
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">{draft.meta.title || c.title}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Review the outline. Reorder, rename, add or remove steps, then approve to write the content.</p>
        </div>

        <ul className="space-y-2">
          {steps.map((s, i) => (
            <li key={s.id} className="glass-card rounded-2xl p-4 flex items-start gap-3">
              <span className="text-xs font-mono text-slate-400 mt-1 w-5 text-right">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <input
                  defaultValue={s.title}
                  onBlur={e => { if (e.target.value.trim() && e.target.value !== s.title) run((t, rev) => patchCourseStep(school.id, c.journey_id, s.id, { title: e.target.value.trim(), expected_revision: rev }, t)) }}
                  className="w-full bg-transparent text-sm font-semibold text-slate-900 dark:text-slate-100 focus:outline-none focus:border-b focus:border-violet-400"
                />
                {s.core_question && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{s.core_question}</p>}
                {s.citations?.length > 0 && <p className="text-[11px] text-slate-400 mt-1">{s.citations.length} source section{s.citations.length === 1 ? '' : 's'}</p>}
              </div>
              <div className="flex items-center gap-0.5 shrink-0">
                <button onClick={() => move(s.id, -1)} disabled={i === 0 || working} aria-label="Move up" className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 disabled:opacity-30"><ChevronUp size={15} /></button>
                <button onClick={() => move(s.id, 1)} disabled={i === steps.length - 1 || working} aria-label="Move down" className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 disabled:opacity-30"><ChevronDown size={15} /></button>
                <button onClick={() => run((t, rev) => deleteCourseStep(school.id, c.journey_id, s.id, rev, t))} disabled={working} aria-label="Delete step" className="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 disabled:opacity-30"><Trash2 size={15} /></button>
              </div>
            </li>
          ))}
        </ul>

        <button onClick={() => setShowAdd(true)} className="btn-ghost !py-2 !px-4 flex items-center gap-1.5 text-sm"><Plus size={14} /> Add a step</button>

        {skipped.length > 0 && (
          <div className="glass-card rounded-2xl p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Not covered</h3>
            <ul className="space-y-1.5">
              {skipped.map((sk, i) => (
                <li key={i} className="text-sm text-slate-600 dark:text-slate-300 flex items-start gap-2">
                  <span className="text-slate-400 mt-0.5">•</span>
                  <span>{sk.title || 'Section'}{sk.reason ? ` — ${sk.reason}` : ''}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex justify-end sticky bottom-4">
          <button onClick={approve} disabled={working || steps.length === 0} className="btn-primary flex items-center gap-2 shadow-lg">
            {working ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Approve outline & build
          </button>
        </div>

        {showAdd && <AddStepModal onClose={() => setShowAdd(false)} onAdd={async (title) => { await run((t, rev) => addCourseStep(school.id, c.journey_id, { title, expected_revision: rev }, t)); setShowAdd(false) }} />}
        {showVersions && <VersionsDrawer schoolId={school.id} jid={c.journey_id} onClose={() => setShowVersions(false)} onRestored={(nc) => { setShowVersions(false); setCourse(nc) }} />}
      </div>
    )
  }

  // ── Step editor (built / build_failed) ──────────────────────────────────
  const missingBody = steps.filter(s => !s.body_md)
  const flagCount = steps.reduce((n, s) => n + (s.flags?.length ?? 0), 0)

  return (
    <div className="space-y-4">
      {header}
      {draft?.status === 'build_failed' && (
        <div className="glass-card rounded-2xl p-4 text-sm text-rose-600 dark:text-rose-400">Some steps failed to build. Regenerate them, or approve the outline again.</div>
      )}
      <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">{draft?.meta.title || c.title}</h1>

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        {/* left: step list */}
        <aside className="glass-card rounded-2xl p-2 h-fit lg:sticky lg:top-24">
          <ul className="space-y-0.5">
            {steps.map((s, i) => {
              const b = stepBadge(s)
              return (
                <li key={s.id}>
                  <button onClick={() => setSel(s.id)}
                    className={clsx('w-full text-left px-3 py-2 rounded-xl flex items-center gap-2 transition-colors',
                      selected?.id === s.id ? 'bg-violet-100 dark:bg-violet-500/15' : 'hover:bg-slate-100/70 dark:hover:bg-slate-800/50')}>
                    <span className="text-[11px] font-mono text-slate-400 w-4 shrink-0">{i + 1}</span>
                    <span className="text-sm text-slate-800 dark:text-slate-100 truncate flex-1">{s.title}</span>
                    <span className={clsx('shrink-0', b.cls)} title={b.label}>{b.icon}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <button onClick={() => setShowAdd(true)} className="w-full mt-1 px-3 py-2 rounded-xl text-sm text-slate-500 hover:bg-slate-100/70 dark:hover:bg-slate-800/50 flex items-center gap-1.5"><Plus size={14} /> Add step</button>
        </aside>

        {/* center + right */}
        {selected ? (
          <StepPane
            key={selected.id}
            step={selected}
            working={working}
            onSave={(patch) => run((t, rev) => patchCourseStep(school.id, c.journey_id, selected.id, { ...patch, expected_revision: rev }, t))}
            onDelete={() => run((t, rev) => deleteCourseStep(school.id, c.journey_id, selected.id, rev, t))}
            onRegenerate={async (instruction, overwrite) => {
              const token = await getToken(); if (!token || !draft) return
              try {
                const h = await regenerateCourseStep(school.id, c.journey_id, selected.id, { instruction, overwrite_teacher_edits: overwrite, expected_revision: draft.revision }, token)
                setBuildJobId(h.job_id); addToast('Regenerating this step…'); await reload()
              } catch (err) {
                const code = apiErrorCode(err)
                if (code === 'teacher_edits_protected') return 'protected'
                addToast(schoolErrorMessage(code), 'error')
              }
            }}
          />
        ) : (
          <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-500 dark:text-slate-400">This course has no steps yet.</div>
        )}
      </div>

      {showAdd && <AddStepModal onClose={() => setShowAdd(false)} onAdd={async (title) => { await run((t, rev) => addCourseStep(school.id, c.journey_id, { title, expected_revision: rev }, t)); setShowAdd(false) }} />}
      {showVersions && <VersionsDrawer schoolId={school.id} jid={c.journey_id} onClose={() => setShowVersions(false)} onRestored={(nc) => { setShowVersions(false); setCourse(nc) }} />}
      {showPublish && (
        <PublishDialog
          missingBody={missingBody.length}
          flagCount={flagCount}
          onClose={() => setShowPublish(false)}
          onPublish={async (summary) => {
            const token = await getToken(); if (!token || !draft) return
            setWorking(true)
            try {
              const updated = await publishCourse(school.id, c.journey_id, { change_summary: summary, expected_revision: draft.revision }, token)
              setCourse(updated); setShowPublish(false); addToast('Course published ✓')
            } catch (err) {
              const code = apiErrorCode(err)
              addToast(code === 'steps_incomplete' ? 'Some steps still need content.' : schoolErrorMessage(code), 'error')
            } finally { setWorking(false) }
          }}
        />
      )}
    </div>
  )
}

// ── Center/right pane for one step ─────────────────────────────────────────
function StepPane({ step, working, onSave, onDelete, onRegenerate }: {
  step: CourseStep
  working: boolean
  onSave: (patch: { title?: string; body_md?: string }) => void
  onDelete: () => void
  onRegenerate: (instruction: string | undefined, overwrite: boolean) => Promise<'protected' | void>
}) {
  const [title, setTitle] = useState(step.title)
  const [body, setBody] = useState(step.body_md ?? '')
  const [preview, setPreview] = useState(false)
  const [regen, setRegen] = useState<string | null>(null)
  const dirty = title !== step.title || body !== (step.body_md ?? '')

  const doRegen = async (overwrite: boolean) => {
    const res = await onRegenerate(regen?.trim() || undefined, overwrite)
    if (res === 'protected') {
      if (window.confirm('This step has your edits. Replace them with a fresh AI version?')) await onRegenerate(regen?.trim() || undefined, true)
    } else { setRegen(null) }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_260px] gap-4">
      {/* center: editor */}
      <div className="glass-card rounded-2xl p-4 space-y-3 min-w-0">
        <input value={title} onChange={e => setTitle(e.target.value)} className="w-full bg-transparent text-base font-semibold text-slate-900 dark:text-slate-100 focus:outline-none" />
        <div className="flex items-center gap-2">
          <button onClick={() => setPreview(false)} className={clsx('text-xs px-2.5 py-1 rounded-lg flex items-center gap-1', !preview ? 'bg-violet-600 text-white' : 'text-slate-500 dark:text-slate-400')}><Pencil size={12} /> Edit</button>
          <button onClick={() => setPreview(true)} className={clsx('text-xs px-2.5 py-1 rounded-lg flex items-center gap-1', preview ? 'bg-violet-600 text-white' : 'text-slate-500 dark:text-slate-400')}><Eye size={12} /> Preview</button>
          <div className="ml-auto flex items-center gap-1">
            <button onClick={() => setRegen(regen === null ? '' : null)} className="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1"><RefreshCw size={12} /> Regenerate</button>
            <button onClick={onDelete} disabled={working} aria-label="Delete step" className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400"><Trash2 size={14} /></button>
          </div>
        </div>

        {regen !== null && (
          <div className="rounded-xl border border-violet-200 dark:border-violet-500/30 p-3 space-y-2 bg-violet-50/50 dark:bg-violet-500/5">
            <input value={regen} onChange={e => setRegen(e.target.value)} placeholder="Optional instruction, e.g. 'make it simpler'" className={fieldCls} />
            <div className="flex gap-2">
              <button onClick={() => doRegen(false)} className="btn-primary !py-1.5 !px-3 text-xs flex items-center gap-1"><RefreshCw size={12} /> Regenerate step</button>
              <button onClick={() => setRegen(null)} className="btn-ghost !py-1.5 !px-3 text-xs">Cancel</button>
            </div>
          </div>
        )}

        {preview ? (
          <div className="prose-sm max-w-none rounded-xl border border-slate-200 dark:border-slate-700 p-3 min-h-[200px]">
            {body.trim() ? <MarkdownContent content={body} /> : <p className="text-sm text-slate-400">Nothing to preview yet.</p>}
          </div>
        ) : (
          <textarea value={body} onChange={e => setBody(e.target.value)} rows={16}
            placeholder="Step content (markdown)…" className={clsx(fieldCls, 'font-mono text-xs leading-relaxed resize-y')} />
        )}

        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">{step.estimated_minutes ? `~${step.estimated_minutes} min` : ''}</span>
          <button onClick={() => onSave({ title: title.trim() || step.title, body_md: body })} disabled={!dirty || working}
            className="btn-primary !py-1.5 !px-4 text-sm disabled:opacity-50 flex items-center gap-1.5">
            {working ? <Loader2 size={14} className="animate-spin" /> : null} {dirty ? 'Save step' : 'Saved'}
          </button>
        </div>
      </div>

      {/* right: sources + flags */}
      <aside className="glass-card rounded-2xl p-4 space-y-4 h-fit">
        {step.flags?.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-2 flex items-center gap-1.5"><AlertTriangle size={13} /> Check this</h3>
            <ul className="space-y-2">
              {step.flags.map((f, i) => (
                <li key={i} className="text-xs text-slate-600 dark:text-slate-300">
                  {f.claim && <p className="italic">"{f.claim}"</p>}
                  {f.reason && <p className="text-slate-500 dark:text-slate-400 mt-0.5">{f.reason}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {step.key_facts?.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Key facts from source</h3>
            <ul className="space-y-1">
              {step.key_facts.map((k, i) => <li key={i} className="text-xs text-slate-600 dark:text-slate-300 flex gap-1.5"><span className="text-slate-400">•</span><span>{k}</span></li>)}
            </ul>
          </div>
        )}
        <p className="text-[11px] text-slate-400">
          {step.citations?.length ?? 0} source section{(step.citations?.length ?? 0) === 1 ? '' : 's'}
          {step.origin === 'teacher' ? ' · teacher-authored' : ''}
        </p>
      </aside>
    </div>
  )
}

function AddStepModal({ onClose, onAdd }: { onClose: () => void; onAdd: (title: string) => void }) {
  const [title, setTitle] = useState('')
  return (
    <Modal title="Add a step" onClose={onClose}>
      <form onSubmit={e => { e.preventDefault(); if (title.trim()) onAdd(title.trim()) }} className="space-y-3">
        <input value={title} onChange={e => setTitle(e.target.value)} autoFocus maxLength={200} placeholder="Step title" className={fieldCls} />
        <p className="text-xs text-slate-500 dark:text-slate-400">A teacher-authored step starts empty — you'll write its content by hand (the AI can't ground it to a source).</p>
        <button type="submit" disabled={!title.trim()} className="btn-primary w-full disabled:opacity-50">Add step</button>
      </form>
    </Modal>
  )
}

function PublishDialog({ missingBody, flagCount, onClose, onPublish }: {
  missingBody: number; flagCount: number; onClose: () => void; onPublish: (summary: string) => void
}) {
  const [summary, setSummary] = useState('')
  const [ack, setAck] = useState(false)
  const blocked = missingBody > 0
  const needAck = flagCount > 0 && !ack
  return (
    <Modal title="Publish course" onClose={onClose}>
      <div className="space-y-4">
        <ul className="space-y-2 text-sm">
          <li className="flex items-center gap-2">
            {missingBody === 0 ? <CheckCircle2 size={15} className="text-emerald-500" /> : <AlertTriangle size={15} className="text-rose-500" />}
            <span className={missingBody === 0 ? 'text-slate-700 dark:text-slate-200' : 'text-rose-600 dark:text-rose-400'}>
              {missingBody === 0 ? 'Every step has content' : `${missingBody} step${missingBody === 1 ? '' : 's'} still need content`}
            </span>
          </li>
          {flagCount > 0 && (
            <li className="flex items-start gap-2">
              <AlertTriangle size={15} className="text-amber-500 mt-0.5" />
              <label className="text-slate-700 dark:text-slate-200">
                <input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} className="accent-violet-600 mr-1.5" />
                {flagCount} unresolved "check this" flag{flagCount === 1 ? '' : 's'} — publish anyway
              </label>
            </li>
          )}
        </ul>
        <label className="block text-xs text-slate-600 dark:text-slate-400">Change summary (optional)
          <input value={summary} onChange={e => setSummary(e.target.value)} maxLength={500} placeholder="What changed in this version" className={clsx(fieldCls, 'mt-1')} />
        </label>
        <button onClick={() => onPublish(summary.trim())} disabled={blocked || needAck}
          className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
          <Rocket size={16} /> Publish to students
        </button>
      </div>
    </Modal>
  )
}

function VersionsDrawer({ schoolId, jid, onClose, onRestored }: {
  schoolId: string; jid: string; onClose: () => void; onRestored: (c: Course) => void
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [versions, setVersions] = useState<CourseVersion[] | null>(null)
  const [busy, setBusy] = useState(false)
  const didLoad = useRef(false)

  useEffect(() => {
    if (didLoad.current) return
    didLoad.current = true
    ;(async () => {
      const token = await getToken(); if (!token) return
      try { setVersions((await listCourseVersions(schoolId, jid, token)).versions) }
      catch (err) { addToast(schoolErrorMessage(apiErrorCode(err)), 'error'); setVersions([]) }
    })()
  }, [schoolId, jid, getToken, addToast])

  const restore = async (v: number) => {
    const token = await getToken(); if (!token) return
    setBusy(true)
    try { onRestored(await restoreCourseVersion(schoolId, jid, v, token)); addToast('Restored as a new draft ✓') }
    catch (err) { addToast(schoolErrorMessage(apiErrorCode(err)), 'error') }
    finally { setBusy(false) }
  }

  return (
    <Modal title="Version history" onClose={onClose}>
      {versions === null ? (
        <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>
      ) : versions.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">No published versions yet.</p>
      ) : (
        <ul className="space-y-2">
          {versions.map(v => (
            <li key={v.version} className="flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Version {v.version}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                  {new Date(v.created_at).toLocaleDateString()}{v.created_by_name ? ` · ${v.created_by_name}` : ''}{v.change_summary ? ` · ${v.change_summary}` : ''}
                </p>
              </div>
              <button onClick={() => restore(v.version)} disabled={busy} className="btn-ghost !py-1.5 !px-3 text-xs shrink-0">Restore</button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}
