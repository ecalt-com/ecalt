import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Loader2, MessageSquare, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { apiErrorCode } from '../../lib/api'
import {
  getStudentDrilldown, getStudentTranscript, getStudentTranscripts,
  type StudentDrilldown as Drilldown, type TranscriptMessage, type TranscriptSummary,
} from '../../lib/schoolApi'

const fmtWhen = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '')

const FLAG_LABEL: Record<string, string> = {
  overdue: 'Overdue',
  low_quiz_accuracy: 'Low quiz scores',
  heavy_hints: 'Needs many hints',
  stalled: 'Stalled',
}

// Student drill-down (frontend-changes.md §10, SC-701/702): per assigned course,
// step completion plus quiz attempts / accuracy / hints, with "needs attention"
// flags. Opened from the class progress matrix; read-only.
export default function StudentDrilldown({ schoolId, classId, studentUid, studentName, onClose }: {
  schoolId: string; classId: string; studentUid: string; studentName: string; onClose: () => void
}) {
  const { getToken } = useAuth()
  const [data, setData] = useState<Drilldown | null>(null)
  const [error, setError] = useState(false)
  // Tutor transcripts (D4): null = loading, 'disabled' = school turned it off.
  const [transcripts, setTranscripts] = useState<TranscriptSummary[] | 'disabled' | null>(null)
  const [openConv, setOpenConv] = useState<string | null>(null)
  const [messages, setMessages] = useState<TranscriptMessage[] | null>(null)

  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const d = await getStudentDrilldown(schoolId, classId, studentUid, token)
        if (live) setData(d)
      } catch {
        if (live) setError(true)
      }
    })()
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const t = await getStudentTranscripts(schoolId, classId, studentUid, token)
        if (live) setTranscripts(t.conversations)
      } catch (err) {
        if (live) setTranscripts(apiErrorCode(err) === 'transcript_access_disabled' ? 'disabled' : [])
      }
    })()
    return () => { live = false }
  }, [schoolId, classId, studentUid, getToken])

  const openConversation = async (id: string) => {
    if (openConv === id) { setOpenConv(null); return }
    setOpenConv(id)
    setMessages(null)
    try {
      const token = await getToken()
      if (!token) return
      const t = await getStudentTranscript(schoolId, classId, studentUid, id, token)
      setMessages(t.messages)
    } catch {
      setMessages([])
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-20 bg-slate-900/70 backdrop-blur-sm overflow-y-auto"
         role="dialog" aria-modal="true" aria-label={`${studentName} progress`} onClick={onClose}>
      <div className="glass-card rounded-2xl p-5 w-full max-w-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{data?.student.display_name ?? studentName}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={18} /></button>
        </div>

        {!data && !error && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>}
        {error && <p className="text-sm text-rose-600 dark:text-rose-400" role="alert">Couldn't load this student's progress.</p>}

        {data && data.courses.length === 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">No courses assigned to this class yet.</p>
        )}

        <div className="space-y-5">
          {data?.courses.map(c => (
            <section key={c.assignment_id}>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-lg" aria-hidden="true">{c.icon}</span>
                <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{c.title}</h3>
                <span className="text-xs text-slate-500 dark:text-slate-400">{c.done_steps}/{c.total_steps} steps · {c.percent}%</span>
                {c.quiz_accuracy !== null && <span className="text-xs text-slate-500 dark:text-slate-400">· {c.quiz_accuracy}% quiz</span>}
                {c.flags.map(f => (
                  <span key={f} className="text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300">
                    {FLAG_LABEL[f] ?? f}
                  </span>
                ))}
              </div>
              <ul className="space-y-1">
                {c.steps.map((s, i) => (
                  <li key={s.step_id} className="flex items-center gap-2 text-xs py-1 border-b border-slate-100/70 dark:border-slate-800/60 last:border-0">
                    {s.completed
                      ? <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
                      : <Circle size={14} className="text-slate-300 dark:text-slate-600 shrink-0" />}
                    <span className={clsx('flex-1 min-w-0 truncate', s.completed ? 'text-slate-700 dark:text-slate-200' : 'text-slate-500 dark:text-slate-400')}>
                      {i + 1}. {s.title ?? 'Step'}
                    </span>
                    {s.quiz_attempts > 0 && (
                      <span className="text-slate-400 dark:text-slate-500 shrink-0">
                        {s.quiz_correct}/{s.quiz_attempts} correct{s.hints_used > 0 ? ` · ${s.hints_used} hint${s.hints_used === 1 ? '' : 's'}` : ''}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        {/* Tutor transcripts (D4) — shown only when the school allows it. */}
        {Array.isArray(transcripts) && transcripts.length > 0 && (
          <section className="mt-5 pt-4 border-t border-slate-200/70 dark:border-slate-700/50">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-2">
              <MessageSquare size={14} className="text-violet-500" /> Tutor conversations
            </h3>
            <ul className="space-y-1">
              {transcripts.map(t => (
                <li key={t.id} className="rounded-lg border border-slate-200/70 dark:border-slate-700/50">
                  <button
                    onClick={() => openConversation(t.id)}
                    className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <span className="truncate text-slate-700 dark:text-slate-200">{t.title || 'Tutor chat'}</span>
                    <span className="text-slate-400 dark:text-slate-500 shrink-0">{t.message_count} msg · {fmtWhen(t.last_active)}</span>
                  </button>
                  {openConv === t.id && (
                    <div className="px-3 pb-3 pt-1 space-y-2 border-t border-slate-100/70 dark:border-slate-800/60">
                      {messages === null ? (
                        <div className="flex justify-center py-3"><Loader2 size={14} className="animate-spin text-violet-500" /></div>
                      ) : messages.length === 0 ? (
                        <p className="text-xs text-slate-400 py-2">No messages.</p>
                      ) : messages.map((m, i) => (
                        <div key={i} className={clsx('text-xs rounded-lg px-2.5 py-1.5',
                          m.role === 'user'
                            ? 'bg-violet-50 dark:bg-violet-500/10 text-slate-700 dark:text-slate-200'
                            : 'bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-300')}>
                          <span className="block text-[10px] uppercase tracking-wide text-slate-400 mb-0.5">{m.role === 'user' ? 'Student' : 'Tutor'}</span>
                          {m.content}
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}
