import { useCallback, useEffect, useState } from 'react'
import { BellRing, Loader2, TrendingDown } from 'lucide-react'
import {
  adminGetLearningFunnel, adminGetNotificationQueue,
  type LearningFunnel, type NotificationQueueStats,
} from '../../../lib/api'
import { selectCls } from '../constants'

const STAGES: { key: keyof LearningFunnel['by_step'][number]; label: string }[] = [
  { key: 'opened', label: 'Opened' },
  { key: 'read', label: 'Read to the end' },
  { key: 'quiz_seen', label: 'Saw the quiz' },
  { key: 'answered', label: 'Answered it' },
  { key: 'completed', label: 'Completed' },
]

const ago = (s: number | null) => (s == null ? '—' : s < 3600 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} days`)

// Admin → Funnel: where learners stop (F1.2) and whether the notification queue is healthy (F0.1).
export function LearningFunnelPanel({ getToken }: { getToken: () => Promise<string | null> }) {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<LearningFunnel | null>(null)
  const [queue, setQueue] = useState<NotificationQueueStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = await getToken(); if (!token) return
    try {
      const [f, q] = await Promise.all([adminGetLearningFunnel(days, token), adminGetNotificationQueue(token)])
      setData(f); setQueue(q); setError(null)
    } catch { setError("Couldn't load the learning funnel.") }
  }, [days, getToken])
  useEffect(() => { setData(null); load() }, [load])

  const queueBad = queue && (queue.totals.pending > 1000 || queue.users_with_over_20_pending > 0)
  return (
    <section className="glass-card rounded-xl p-5 mb-6 space-y-4" data-testid="learning-funnel-panel">
      <div className="flex items-center gap-2 flex-wrap">
        <TrendingDown size={14} className="text-violet-500" />
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Learning funnel</h2>
        <span className="text-xs text-slate-400">learners per step position, last {days} days</span>
        <select value={days} onChange={e => setDays(Number(e.target.value))} className={`${selectCls} ml-auto`} aria-label="Period">
          {[7, 30, 90].map(d => <option key={d} value={d}>{d} days</option>)}
        </select>
      </div>

      {error && <p className="text-xs text-rose-500">{error}</p>}
      {!data && !error && <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 size={12} className="animate-spin" /> Loading…</div>}

      {data && (
        <>
          <p className="text-xs text-slate-500">
            {data.totals.learners} learners · {data.totals.journeys_completed} journeys finished · median {data.totals.median_step_seconds != null ? `${Math.round(data.totals.median_step_seconds)} s` : '—'} on a step
            · quiz ready in {data.quiz_generation.median_ms != null ? `${(data.quiz_generation.median_ms / 1000).toFixed(1)} s` : '—'} (median), {data.quiz_generation.p95_ms != null ? `${(data.quiz_generation.p95_ms / 1000).toFixed(1)} s` : '—'} (95th percentile)
          </p>
          {data.by_step.length === 0 ? (
            <p className="text-xs text-slate-400">No events yet — they appear as signed-in learners open steps.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-1 pr-3 font-medium">Step</th>
                    {STAGES.map(s => <th key={s.key} className="py-1 pr-3 font-medium text-right">{s.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.by_step.map(row => (
                    <tr key={row.step_index} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1.5 pr-3 font-mono text-slate-500">#{row.step_index + 1}</td>
                      {STAGES.map(s => {
                        const n = Number(row[s.key]); const base = Number(row.opened) || 0
                        return (
                          <td key={s.key} className="py-1.5 pr-3 text-right tabular-nums text-slate-700 dark:text-slate-200">
                            {n}{s.key !== 'opened' && base > 0 && <span className="text-slate-400"> · {Math.round((n / base) * 100)}%</span>}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {queue && (
        <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 flex-wrap text-xs" data-testid="notification-queue-health">
          <BellRing size={13} className={queueBad ? 'text-rose-500' : 'text-emerald-500'} />
          <span className="font-semibold text-slate-600 dark:text-slate-300">Notification queue</span>
          <span className="text-slate-500">
            {queue.totals.pending} pending · {queue.totals.due} due · oldest due {ago(queue.totals.oldest_due_seconds)}
          </span>
          {queueBad && <span className="text-rose-600 dark:text-rose-400 font-medium">backlog — check the queue processor</span>}
        </div>
      )}
    </section>
  )
}
