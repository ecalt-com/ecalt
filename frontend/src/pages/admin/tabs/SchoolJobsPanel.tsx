import { useCallback, useEffect, useState } from 'react'
import { Activity, Loader2, RefreshCw, RotateCcw, XCircle } from 'lucide-react'
import clsx from 'clsx'
import { apiErrorCode } from '../../../lib/api'
import {
  adminCancelJob, adminListJobs, adminRetryJob, schoolErrorMessage,
  type AdminJob, type AdminJobState, type JobQueueHealth,
} from '../../../lib/schoolApi'
import { selectCls } from '../constants'

const STATUS_CLS: Record<string, string> = {
  failed: 'text-rose-700 bg-rose-50 dark:text-rose-400 dark:bg-rose-400/10',
  queued: 'text-amber-700 bg-amber-50 dark:text-amber-400 dark:bg-amber-400/10',
  running: 'text-sky-700 bg-sky-50 dark:text-sky-400 dark:bg-sky-400/10',
  cancelled: 'text-slate-500 bg-slate-100 dark:bg-slate-700/50',
}

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—')

// Admin → Schools → Background jobs (SC-805/806): failed and stuck jobs across
// every school, with retry / cancel. The scheduler also alerts on these.
export function SchoolJobsPanel({ getToken }: { getToken: () => Promise<string | null> }) {
  const [state, setState] = useState<AdminJobState>('attention')
  const [jobs, setJobs] = useState<AdminJob[] | null>(null)
  const [health, setHealth] = useState<JobQueueHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [acting, setActing] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = await getToken(); if (!token) return
    try {
      const r = await adminListJobs(state, token)
      setJobs(r.jobs); setHealth(r.health); setError(null)
    } catch (err) { setError(schoolErrorMessage(apiErrorCode(err), "Couldn't load jobs.")) }
  }, [state, getToken])
  useEffect(() => { setJobs(null); load() }, [load])

  const act = async (job: AdminJob, fn: typeof adminRetryJob | typeof adminCancelJob) => {
    const token = await getToken(); if (!token) return
    setActing(job.id)
    try { await fn(job.id, token); await load() }
    catch (err) { setError(schoolErrorMessage(apiErrorCode(err))) }
    finally { setActing(null) }
  }

  const alert = health && (health.stuck_queued + health.stuck_running + health.failed_last_hour) > 0
  return (
    <section className="glass-card rounded-xl p-4 space-y-3" data-testid="school-jobs-panel">
      <div className="flex items-center gap-2 flex-wrap">
        <Activity size={14} className={alert ? 'text-rose-500' : 'text-violet-500'} />
        <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Background jobs</h3>
        {health && (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {health.queued} queued · {health.running} running · {health.failed_last_day} failed today
            {(health.stuck_queued + health.stuck_running) > 0 && (
              <span className="text-rose-600 dark:text-rose-400 font-medium"> · {health.stuck_queued + health.stuck_running} stuck — is the worker running?</span>
            )}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <select value={state} onChange={e => setState(e.target.value as AdminJobState)} className={selectCls} aria-label="Job filter">
            <option value="attention">Needs attention</option>
            <option value="failed">Failed (7 days)</option>
            <option value="stuck">Stuck</option>
            <option value="active">Queued or running</option>
          </select>
          <button onClick={load} className="p-1.5 rounded-lg text-slate-400 hover:text-violet-600" aria-label="Refresh jobs"><RefreshCw size={14} /></button>
        </div>
      </div>
      {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
      {jobs === null ? <div className="flex justify-center py-4"><Loader2 className="animate-spin text-violet-500" size={16} /></div>
        : jobs.length === 0 ? <p className="text-xs text-slate-500 dark:text-slate-400">Nothing here.</p>
        : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {jobs.map(j => (
              <li key={j.id} className="py-2 flex items-start gap-3 flex-wrap">
                <span className={clsx('text-[10px] font-semibold px-2 py-0.5 rounded-full mt-0.5', STATUS_CLS[j.status] ?? STATUS_CLS.cancelled)}>{j.status}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-800 dark:text-slate-100">{j.kind} · {j.school_name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Created {when(j.created_at)} · attempt {j.attempts}/{j.max_attempts}{j.cancel_requested ? ' · cancel requested' : ''}
                  </p>
                  {j.error && <p className="text-xs text-rose-600 dark:text-rose-400 mt-0.5 break-words">{j.error}</p>}
                </div>
                <div className="flex items-center gap-1">
                  {(j.status === 'failed' || j.status === 'cancelled') && (
                    <button onClick={() => act(j, adminRetryJob)} disabled={acting === j.id}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:text-violet-600 disabled:opacity-40">
                      {acting === j.id ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />} Retry
                    </button>
                  )}
                  {(j.status === 'queued' || j.status === 'running') && (
                    <button onClick={() => act(j, adminCancelJob)} disabled={acting === j.id || j.cancel_requested}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:text-rose-600 disabled:opacity-40">
                      <XCircle size={12} /> Cancel
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
    </section>
  )
}
