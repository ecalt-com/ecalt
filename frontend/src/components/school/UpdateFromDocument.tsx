import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Check, FilePlus2, Loader2, Minus, Pencil, Plus, X } from 'lucide-react'
import clsx from 'clsx'
import MarkdownContent from '../MarkdownContent'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import { useSchoolJob } from '../../lib/useSchoolJob'
import {
  applyProposals, decideProposal, getCourseProposals, listDocuments, schoolErrorMessage,
  startCourseUpdate,
  type Course, type CourseProposal, type SchoolDocument, type UpdateMode,
} from '../../lib/schoolApi'

const fieldCls = 'w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

type Phase = 'pick' | 'working' | 'review' | 'empty' | 'failed'

const OP = {
  modify: { label: 'Update', cls: 'text-sky-600 dark:text-sky-400 bg-sky-100/70 dark:bg-sky-500/15', icon: <Pencil size={12} /> },
  add: { label: 'New step', cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-100/70 dark:bg-emerald-500/15', icon: <Plus size={12} /> },
  remove: { label: 'Remove', cls: 'text-rose-600 dark:text-rose-400 bg-rose-100/70 dark:bg-rose-500/15', icon: <Minus size={12} /> },
} as const

// Teacher update-from-document flow (M6 SC-606): pick a ready document + mode,
// run the propose-update job, review each proposed change side-by-side, then
// apply the accepted ones into a new draft the teacher reviews and publishes.
export default function UpdateFromDocument({ schoolId, jid, onClose, onApplied }: {
  schoolId: string
  jid: string
  onClose: () => void
  onApplied: (course: Course) => void
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()

  const [phase, setPhase] = useState<Phase>('pick')
  const [docs, setDocs] = useState<SchoolDocument[] | null>(null)
  const [docId, setDocId] = useState('')
  const [mode, setMode] = useState<UpdateMode>('revise')
  const [jobId, setJobId] = useState<string | null>(null)
  const [proposals, setProposals] = useState<CourseProposal[]>([])
  const [working, setWorking] = useState(false)
  const didLoad = useRef(false)

  useEffect(() => {
    if (didLoad.current) return
    didLoad.current = true
    ;(async () => {
      const token = await getToken(); if (!token) return
      try {
        const ready = (await listDocuments(schoolId, token)).documents.filter(d => d.status === 'ready')
        setDocs(ready)
        if (ready[0]) setDocId(ready[0].id)
      } catch { setDocs([]) }
    })()
  }, [schoolId, getToken])

  const loadProposals = useCallback(async () => {
    const token = await getToken(); if (!token) return
    const list = (await getCourseProposals(schoolId, jid, token)).proposals
    setProposals(list)
    setPhase(list.length ? 'review' : 'empty')
  }, [schoolId, jid, getToken])

  useSchoolJob(schoolId, jobId, (job) => {
    setJobId(null)
    if (job.status === 'succeeded') loadProposals()
    else setPhase('failed')
  })

  const start = async () => {
    const token = await getToken(); if (!token || !docId) return
    setWorking(true)
    try {
      const h = await startCourseUpdate(schoolId, jid, docId, mode, token)
      setJobId(h.job_id); setPhase('working')
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    } finally { setWorking(false) }
  }

  const decide = async (p: CourseProposal, decision: 'accept' | 'reject') => {
    const token = await getToken(); if (!token) return
    const next = decision === 'accept' ? 'accepted' : 'rejected'
    setProposals(ps => ps.map(x => (x.id === p.id ? { ...x, status: next } : x)))
    try { await decideProposal(schoolId, jid, p.id, decision, token) }
    catch (err) { addToast(schoolErrorMessage(apiErrorCode(err)), 'error'); loadProposals() }
  }

  const apply = async () => {
    const token = await getToken(); if (!token) return
    setWorking(true)
    try {
      const course = await applyProposals(schoolId, jid, token)
      addToast('Update applied — review the new draft, then publish ✓')
      onApplied(course)
    } catch (err) {
      const code = apiErrorCode(err)
      addToast(code === 'nothing_to_apply' ? 'Accept at least one change first.' : schoolErrorMessage(code), 'error')
    } finally { setWorking(false) }
  }

  const acceptedCount = proposals.filter(p => p.status === 'accepted').length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Update from a document">
      <div className="glass-card rounded-2xl p-5 w-full max-w-3xl max-h-[88vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <FilePlus2 size={18} className="text-violet-500" /> Update from a document
          </h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={16} /></button>
        </div>

        {/* ── Pick a document + mode ── */}
        {phase === 'pick' && (
          <div className="space-y-4 overflow-y-auto">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Pick an uploaded document with the new material. We'll compare it to the published course and propose changes for you to review — nothing goes to students until you apply and publish.
            </p>
            {docs === null ? (
              <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>
            ) : docs.length === 0 ? (
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 text-sm text-slate-500 dark:text-slate-400">
                No ready documents yet. <Link to="/school/documents" className="text-violet-600 dark:text-violet-400" onClick={onClose}>Upload one first →</Link>
              </div>
            ) : (
              <>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Document
                  <select value={docId} onChange={e => setDocId(e.target.value)} className={clsx(fieldCls, 'mt-1')}>
                    {docs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
                  </select>
                </label>
                <fieldset className="space-y-2">
                  <legend className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">How should we use it?</legend>
                  {([
                    ['revise', 'Revise', 'A new edition of the same material — update changed steps and add new sections.'],
                    ['supplement', 'Supplement', 'Extra material — only add new steps, leave the existing ones alone.'],
                  ] as const).map(([val, label, desc]) => (
                    <label key={val} className={clsx('flex items-start gap-2.5 p-3 rounded-xl border cursor-pointer',
                      mode === val ? 'border-violet-400 bg-violet-50/50 dark:bg-violet-500/5' : 'border-slate-200 dark:border-slate-700')}>
                      <input type="radio" name="mode" checked={mode === val} onChange={() => setMode(val)} className="accent-violet-600 mt-0.5" />
                      <span>
                        <span className="block text-sm font-medium text-slate-800 dark:text-slate-100">{label}</span>
                        <span className="block text-xs text-slate-500 dark:text-slate-400">{desc}</span>
                      </span>
                    </label>
                  ))}
                </fieldset>
                <div className="flex justify-end">
                  <button onClick={start} disabled={!docId || working} className="btn-primary flex items-center gap-2 disabled:opacity-50">
                    {working ? <Loader2 size={16} className="animate-spin" /> : <FilePlus2 size={16} />} Propose changes
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Job running ── */}
        {phase === 'working' && (
          <div className="py-12 text-center space-y-3">
            <Loader2 size={28} className="animate-spin text-violet-500 mx-auto" />
            <p className="text-sm text-slate-600 dark:text-slate-300">Comparing the document to the course and drafting changes…</p>
            <p className="text-xs text-slate-400">This can take a minute. You can close this and come back.</p>
          </div>
        )}

        {/* ── No changes ── */}
        {phase === 'empty' && (
          <div className="py-12 text-center space-y-3">
            <Check size={28} className="text-emerald-500 mx-auto" />
            <p className="text-sm text-slate-600 dark:text-slate-300">No changes suggested — the course already matches this document.</p>
            <button onClick={onClose} className="btn-ghost">Close</button>
          </div>
        )}

        {/* ── Job failed ── */}
        {phase === 'failed' && (
          <div className="py-12 text-center space-y-3">
            <AlertTriangle size={26} className="text-rose-500 mx-auto" />
            <p className="text-sm text-rose-600 dark:text-rose-400">Couldn't propose an update. Check the document is readable and try again.</p>
            <button onClick={() => setPhase('pick')} className="btn-ghost">Try again</button>
          </div>
        )}

        {/* ── Review proposals ── */}
        {phase === 'review' && (
          <>
            <div className="overflow-y-auto space-y-3 flex-1 -mx-1 px-1">
              {proposals.map(p => <ProposalCard key={p.id} p={p} onDecide={decide} />)}
            </div>
            <div className="flex items-center justify-between gap-3 pt-4 mt-1 border-t border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {acceptedCount} of {proposals.length} change{proposals.length === 1 ? '' : 's'} accepted
              </span>
              <button onClick={apply} disabled={acceptedCount === 0 || working} className="btn-primary flex items-center gap-2 disabled:opacity-50">
                {working ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />} Apply {acceptedCount || ''} to a new draft
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function ProposalCard({ p, onDecide }: { p: CourseProposal; onDecide: (p: CourseProposal, d: 'accept' | 'reject') => void }) {
  const [open, setOpen] = useState(false)
  const op = OP[p.op]
  const hasBodies = p.op !== 'remove' && (p.new_body || p.old_body)
  return (
    <div className={clsx('rounded-2xl border p-4',
      p.status === 'accepted' ? 'border-emerald-300 dark:border-emerald-500/40 bg-emerald-50/40 dark:bg-emerald-500/5'
        : p.status === 'rejected' ? 'border-slate-200 dark:border-slate-700 opacity-55'
          : 'border-slate-200 dark:border-slate-700')}>
      <div className="flex items-start gap-3">
        <span className={clsx('shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium', op.cls)}>{op.icon} {op.label}</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{p.title || 'Step'}</p>
          {p.reason && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{p.reason}</p>}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {p.diff && (p.diff.added > 0 || p.diff.removed > 0) && (
              <span className="text-[11px] font-mono text-slate-400">
                <span className="text-emerald-600 dark:text-emerald-400">+{p.diff.added}</span>{' '}
                <span className="text-rose-600 dark:text-rose-400">−{p.diff.removed}</span> lines
              </span>
            )}
            {p.suggestion_only && (
              <span className="text-[11px] text-amber-600 dark:text-amber-400 inline-flex items-center gap-1">
                <AlertTriangle size={11} /> Suggestion — this step was teacher-edited
              </span>
            )}
            {hasBodies && (
              <button onClick={() => setOpen(o => !o)} className="text-[11px] text-violet-600 dark:text-violet-400">
                {open ? 'Hide' : 'Compare'}
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => onDecide(p, 'accept')} aria-label="Accept"
            className={clsx('p-1.5 rounded-lg', p.status === 'accepted' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400')}><Check size={15} /></button>
          <button onClick={() => onDecide(p, 'reject')} aria-label="Reject"
            className={clsx('p-1.5 rounded-lg', p.status === 'rejected' ? 'bg-slate-500 text-white' : 'text-slate-400 hover:text-rose-600 dark:hover:text-rose-400')}><X size={15} /></button>
        </div>
      </div>

      {open && hasBodies && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
          {p.op === 'modify' && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-1.5">Current</p>
              <div className="prose-sm max-w-none opacity-70">{p.old_body ? <MarkdownContent content={p.old_body} /> : <p className="text-xs text-slate-400">—</p>}</div>
            </div>
          )}
          <div className={clsx('rounded-xl border p-3 min-w-0', p.op === 'modify' ? 'border-sky-300 dark:border-sky-500/40' : 'border-emerald-300 dark:border-emerald-500/40')}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-1.5">{p.op === 'modify' ? 'Proposed' : 'New content'}</p>
            <div className="prose-sm max-w-none">{p.new_body ? <MarkdownContent content={p.new_body} /> : <p className="text-xs text-slate-400">—</p>}</div>
          </div>
        </div>
      )}
    </div>
  )
}
