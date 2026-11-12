// Course-builder pieces from #16 (frontend-changes.md §8.2/§8.4): cited source
// preview, quiz preview, course details (title/description/icon/tags/hero),
// preview as student, and drag-and-drop reordering.
import { useEffect, useRef, useState } from 'react'
import { BookOpen, Eye, FileText, ImagePlus, Loader2, X } from 'lucide-react'
import clsx from 'clsx'
import MarkdownContent from '../MarkdownContent'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  generateCourseHero, getSourceChunks, previewStepQuiz, schoolErrorMessage,
  type CourseDraft, type CourseStep, type QuizPreviewQuestion, type SourceChunk,
} from '../../lib/schoolApi'

const fieldCls = 'w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

export function Sheet({ title, onClose, wide, children }: { title: string; onClose: () => void; wide?: boolean; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className={clsx('glass-card rounded-2xl p-5 w-full max-h-[85vh] overflow-y-auto', wide ? 'max-w-3xl' : 'max-w-lg')}>
        <div className="flex items-center justify-between mb-4 gap-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 truncate">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 shrink-0"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

const pages = (c: SourceChunk) =>
  c.page_start ? (c.page_end && c.page_end !== c.page_start ? `pp. ${c.page_start}–${c.page_end}` : `p. ${c.page_start}`) : null

// ── Cited source text ──────────────────────────────────────────────────────
export function SourcesModal({ schoolId, jid, chunkIds, title, onClose }: {
  schoolId: string; jid: string; chunkIds: string[]; title: string; onClose: () => void
}) {
  const { getToken } = useAuth()
  const [chunks, setChunks] = useState<SourceChunk[] | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let live = true
    ;(async () => {
      const token = await getToken(); if (!token) return
      try { const r = await getSourceChunks(schoolId, jid, chunkIds, token); if (live) setChunks(r.chunks) }
      catch { if (live) setError(true) }
    })()
    return () => { live = false }
  }, [schoolId, jid, chunkIds, getToken])
  return (
    <Sheet title={`Sources · ${title}`} onClose={onClose} wide>
      {error ? <p className="text-sm text-rose-600 dark:text-rose-400">Couldn't load the source text.</p>
        : chunks === null ? <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>
        : chunks.length === 0 ? <p className="text-sm text-slate-500 dark:text-slate-400">No source sections for this step.</p>
        : (
          <ul className="space-y-3" data-testid="source-chunks">
            {chunks.map(c => (
              <li key={c.id} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mb-1.5 flex-wrap">
                  <FileText size={12} /> {c.filename}
                  {pages(c) && <span>· {pages(c)}</span>}
                  {c.heading_path.length > 0 && <span className="truncate">· {c.heading_path.join(' › ')}</span>}
                </p>
                <p className="text-sm text-slate-700 dark:text-slate-200 whitespace-pre-line leading-relaxed">{c.text}</p>
              </li>
            ))}
          </ul>
        )}
    </Sheet>
  )
}

// ── Quiz preview (nothing saved) ───────────────────────────────────────────
export function QuizPreviewModal({ schoolId, jid, step, onClose }: {
  schoolId: string; jid: string; step: CourseStep; onClose: () => void
}) {
  const { getToken } = useAuth()
  const [qs, setQs] = useState<QuizPreviewQuestion[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [shown, setShown] = useState<Record<number, boolean>>({})
  const started = useRef(false)
  const load = async () => {
    setQs(null); setError(null); setShown({})
    const token = await getToken(); if (!token) return
    try { setQs((await previewStepQuiz(schoolId, jid, step.id, token)).questions) }
    catch (err) { setError(schoolErrorMessage(apiErrorCode(err), "Couldn't generate sample questions.")) }
  }
  useEffect(() => { if (!started.current) { started.current = true; load() } })  // once
  return (
    <Sheet title={`Quiz preview · ${step.title}`} onClose={onClose}>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Sample questions students might get for this step. Nothing is saved; students get their own questions. Uses a little of the school's AI budget.</p>
      {error ? <p className="text-sm text-rose-600 dark:text-rose-400" role="alert">{error}</p>
        : qs === null ? <div className="flex justify-center py-6"><Loader2 className="animate-spin text-violet-500" /></div>
        : (
          <ol className="space-y-3" data-testid="quiz-preview">
            {qs.map((q, i) => (
              <li key={i} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{i + 1}. {q.question}</p>
                {shown[i]
                  ? <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1.5">Answer: {q.answer}</p>
                  : <button onClick={() => setShown(s => ({ ...s, [i]: true }))} className="text-xs text-violet-600 dark:text-violet-400 mt-1.5 hover:underline">Show answer</button>}
              </li>
            ))}
          </ol>
        )}
      {(qs || error) && <button onClick={load} className="btn-ghost !py-1.5 !px-3 text-xs mt-4">Try other questions</button>}
    </Sheet>
  )
}

// ── Course details: title / description / icon / tags / hero ─────────────
export function CourseDetailsModal({ schoolId, jid, draft, fallbackTitle, working, onSave, onHero, onClose }: {
  schoolId: string; jid: string; draft: CourseDraft; fallbackTitle: string; working: boolean
  onSave: (patch: { title?: string; description?: string; icon?: string; tags?: string[] }) => Promise<void>
  onHero: (url: string) => void
  onClose: () => void
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [title, setTitle] = useState(draft.meta.title || fallbackTitle)
  const [description, setDescription] = useState(draft.meta.description ?? '')
  const [icon, setIcon] = useState(draft.meta.icon ?? '')
  const [tags, setTags] = useState((draft.meta.tags ?? []).join(', '))
  const [hero, setHero] = useState<string | null>((draft.meta.hero_image_url as string | null) ?? null)
  const [heroBusy, setHeroBusy] = useState(false)

  const makeHero = async () => {
    const token = await getToken(); if (!token) return
    setHeroBusy(true)
    try { const r = await generateCourseHero(schoolId, jid, token); setHero(r.hero_image_url); onHero(r.hero_image_url); addToast('Cover image ready ✓') }
    catch (err) { addToast(schoolErrorMessage(apiErrorCode(err)), 'error') }
    finally { setHeroBusy(false) }
  }
  const save = async () => {
    await onSave({
      title: title.trim() || fallbackTitle,
      description: description.trim(),
      icon: icon.trim(),
      tags: tags.split(',').map(t => t.trim()).filter(Boolean),
    })
    onClose()
  }
  return (
    <Sheet title="Course details" onClose={onClose}>
      <form onSubmit={e => { e.preventDefault(); save() }} className="space-y-3">
        <div className="grid grid-cols-[4.5rem_1fr] gap-3">
          <label className="text-xs text-slate-600 dark:text-slate-400">Icon
            <input value={icon} onChange={e => setIcon(e.target.value)} maxLength={8} placeholder="🌋" aria-label="Course icon" className={clsx(fieldCls, 'mt-1 text-center text-lg')} />
          </label>
          <label className="text-xs text-slate-600 dark:text-slate-400">Title
            <input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} className={clsx(fieldCls, 'mt-1')} />
          </label>
        </div>
        <label className="block text-xs text-slate-600 dark:text-slate-400">Description
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={2000} className={clsx(fieldCls, 'mt-1 resize-y')} />
        </label>
        <label className="block text-xs text-slate-600 dark:text-slate-400">Tags (comma-separated)
          <input value={tags} onChange={e => setTags(e.target.value)} placeholder="earth science, grade 6" className={clsx(fieldCls, 'mt-1')} />
        </label>
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 flex items-center gap-3">
          {hero
            ? <img src={hero} alt="Course cover" className="w-20 h-12 object-cover rounded-lg" />
            : <div className="w-20 h-12 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400"><ImagePlus size={18} /></div>}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-slate-600 dark:text-slate-300">Cover image</p>
            <p className="text-[11px] text-slate-400">Optional. Generated by AI from the title; uses the school's budget.</p>
          </div>
          <button type="button" onClick={makeHero} disabled={heroBusy} className="btn-ghost !py-1.5 !px-3 text-xs shrink-0 flex items-center gap-1">
            {heroBusy ? <Loader2 size={12} className="animate-spin" /> : <ImagePlus size={12} />} {hero ? 'Regenerate' : 'Generate'}
          </button>
        </div>
        <button type="submit" disabled={working} className="btn-primary w-full disabled:opacity-50">Save details</button>
      </form>
    </Sheet>
  )
}

// ── Preview as student (read-only) ─────────────────────────────────────────
export function StudentPreview({ draft, fallbackTitle, onClose }: { draft: CourseDraft; fallbackTitle: string; onClose: () => void }) {
  const [open, setOpen] = useState<string | null>(draft.steps[0]?.id ?? null)
  const minutes = draft.steps.reduce((n, s) => n + (s.estimated_minutes ?? 0), 0)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[var(--bg)]" role="dialog" aria-modal="true" aria-label="Preview as student" data-testid="student-preview">
      <div className="sticky top-0 z-10 bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-200 text-sm px-4 py-2 flex items-center gap-2">
        <Eye size={15} className="shrink-0" />
        <span className="flex-1 min-w-0">Preview — this is how students will see the draft. Nothing here is saved or published.</span>
        <button onClick={onClose} className="shrink-0 font-semibold hover:underline">Close</button>
      </div>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
        {typeof draft.meta.hero_image_url === 'string' && draft.meta.hero_image_url && (
          <img src={draft.meta.hero_image_url} alt="" className="w-full h-40 object-cover rounded-2xl" />
        )}
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            {draft.meta.icon && <span aria-hidden="true">{draft.meta.icon}</span>} {draft.meta.title || fallbackTitle}
          </h1>
          {draft.meta.description && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{draft.meta.description}</p>}
          <p className="text-xs text-slate-400 mt-2 flex items-center gap-1.5"><BookOpen size={12} /> {draft.steps.length} steps{minutes ? ` · about ${minutes} min` : ''}</p>
        </div>
        <ol className="space-y-3">
          {draft.steps.map((s, i) => (
            <li key={s.id} className="glass-card rounded-2xl overflow-hidden">
              <button onClick={() => setOpen(open === s.id ? null : s.id)} className="w-full text-left p-4 flex items-start gap-3" aria-expanded={open === s.id}>
                <span className="w-7 h-7 rounded-full bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300 text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">{s.title}</span>
                  {s.core_question && <span className="block text-xs text-slate-500 dark:text-slate-400 mt-0.5">{s.core_question}</span>}
                </span>
              </button>
              {open === s.id && (
                <div className="px-4 pb-4 border-t border-slate-100 dark:border-slate-800 pt-3">
                  {s.body_md?.trim() ? <MarkdownContent content={s.body_md} /> : <p className="text-sm text-slate-400 italic">This step has no content yet.</p>}
                  <p className="text-[11px] text-slate-400 mt-3">Students take a short quiz here before moving on.</p>
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

// ── Drag-and-drop reorder (HTML5, no library; buttons remain for keyboard) ──
export function useDragReorder(ids: string[], onReorder: (order: string[]) => void) {
  const [dragging, setDragging] = useState<string | null>(null)
  const [over, setOver] = useState<string | null>(null)
  const props = (id: string) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => { setDragging(id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', id) },
    onDragOver: (e: React.DragEvent) => { if (dragging && dragging !== id) { e.preventDefault(); setOver(id) } },
    onDragLeave: () => setOver(o => (o === id ? null : o)),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault()
      const from = dragging
      setDragging(null); setOver(null)
      if (!from || from === id) return
      const order = ids.filter(x => x !== from)
      order.splice(order.indexOf(id) + (ids.indexOf(from) < ids.indexOf(id) ? 1 : 0), 0, from)
      onReorder(order)
    },
    onDragEnd: () => { setDragging(null); setOver(null) },
    'data-dragging': dragging === id ? 'true' : undefined,
    className: clsx(dragging === id && 'opacity-50', over === id && 'ring-2 ring-violet-400'),
  })
  return props
}
