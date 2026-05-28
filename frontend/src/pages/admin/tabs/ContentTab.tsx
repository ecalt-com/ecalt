import { Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'
import type { ContentData, StepDropoff } from '../types'
import { StatCard } from '../components/StatCard'

interface ContentTabProps {
  contentData: ContentData | null
  expandedJourneyId: string | null
  journeyDropoff: Record<string, StepDropoff[]>
  loadingDropoff: string | null
  onExpandJourney: (journeyId: string) => void
}

export function ContentTab({
  contentData,
  expandedJourneyId,
  journeyDropoff,
  loadingDropoff,
  onExpandJourney,
}: ContentTabProps) {
  if (!contentData) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Loading content data…
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <StatCard label="Journeys started"    value={String(contentData.completion_summary.journeys_started)} />
        <StatCard label="Users with progress" value={String(contentData.completion_summary.users_with_progress)} />
        <StatCard label="Avg completion"      value={`${contentData.completion_summary.avg_completion_pct}%`} />
      </div>

      <div className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Top Journeys by Learners</h2>
        </div>
        {contentData.top_journeys.length === 0 ? (
          <p className="text-xs text-slate-400 px-5 py-6 text-center">No journey activity yet.</p>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
            {contentData.top_journeys.map(j => {
              const pct = Number(j.completion_pct)
              const barColor = pct >= 40 ? 'bg-violet-500' : pct >= 20 ? 'bg-amber-400' : 'bg-rose-400'
              const isExpanded = expandedJourneyId === j.id
              const dropoff = journeyDropoff[j.id]
              const isLoadingThis = loadingDropoff === j.id
              const maxCompletions = dropoff ? Math.max(...dropoff.map(s => s.completions), 1) : 1
              return (
                <div key={j.id}>
                  <div
                    className="px-5 py-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                    onClick={() => onExpandJourney(j.id)}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      {j.icon && <span className="text-base shrink-0">{j.icon}</span>}
                      <p className="text-xs font-medium text-slate-800 dark:text-slate-200 flex-1 truncate">{j.title}</p>
                      <span className="text-[10px] text-slate-400 shrink-0 hidden sm:block">{j.difficulty ?? '—'}</span>
                      <span className="text-[10px] tabular-nums text-slate-500 shrink-0">{j.unique_learners} learners</span>
                      <span className={clsx(
                        'text-[10px] tabular-nums font-semibold shrink-0 w-10 text-right',
                        pct >= 40 ? 'text-violet-600 dark:text-violet-400' : pct >= 20 ? 'text-amber-500' : 'text-rose-500'
                      )}>{pct}%</span>
                      <div className="text-slate-400 shrink-0">
                        {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </div>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(pct > 0 ? 1 : 0, pct)}%` }} />
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="px-5 pb-4 pt-2 border-t border-slate-100 dark:border-slate-700/40 bg-slate-50/40 dark:bg-slate-800/20">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-2">Step drop-off</p>
                      {isLoadingThis && (
                        <div className="flex items-center gap-2 text-slate-400 text-xs py-2">
                          <Loader2 size={12} className="animate-spin" /> Loading…
                        </div>
                      )}
                      {!isLoadingThis && dropoff && dropoff.length === 0 && (
                        <p className="text-xs text-slate-400">No step data yet.</p>
                      )}
                      {!isLoadingThis && dropoff && dropoff.length > 0 && (
                        <div className="space-y-1.5">
                          {dropoff.map(s => (
                            <div key={s.step_id} className="flex items-center gap-2">
                              <span className="text-[10px] font-mono text-slate-500 w-24 shrink-0 truncate">{s.step_id}</span>
                              <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700/60 overflow-hidden">
                                <div className="h-full rounded-full bg-violet-500/70" style={{ width: `${(s.completions / maxCompletions) * 100}%` }} />
                              </div>
                              <span className="text-[10px] tabular-nums text-slate-500 w-10 text-right shrink-0">{s.completions}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Most Active Conversations (last 30 days)</h2>
        </div>
        {contentData.top_conversations.length === 0 ? (
          <p className="text-xs text-slate-400 px-5 py-6 text-center">No conversations in the last 30 days.</p>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
            {contentData.top_conversations.map(c => (
              <div key={c.id} className="px-5 py-3 flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{c.title ?? 'Untitled'}</p>
                  <p className="text-[11px] text-slate-500 truncate">{c.email ?? c.uid}</p>
                </div>
                <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 shrink-0">{c.message_count} msgs</span>
                {c.last_message_at && (
                  <span className="text-[10px] text-slate-400 shrink-0 hidden sm:block">
                    {new Date(c.last_message_at).toLocaleDateString('default', { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="glass-card rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Knowledge Graph Growth (last 14 days)</h2>
        {contentData.knowledge_growth.length === 0 ? (
          <p className="text-xs text-slate-400">No knowledge nodes discovered yet.</p>
        ) : (() => {
          const maxConcepts = Math.max(...contentData.knowledge_growth.map(d => d.new_concepts), 1)
          return (
            <>
              <div className="flex items-end gap-1 h-16 mb-2">
                {contentData.knowledge_growth.map(d => (
                  <div
                    key={d.day}
                    className="flex-1 flex flex-col justify-end min-w-0"
                    title={`${d.day}: ${d.new_concepts} concepts, ${d.unique_users} users`}
                  >
                    <div
                      className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t"
                      style={{ height: `${Math.max((d.new_concepts / maxConcepts) * 100, 4)}%` }}
                    />
                  </div>
                ))}
              </div>
              <div className="flex justify-between">
                <span className="text-[9px] text-slate-400">{contentData.knowledge_growth[0]?.day}</span>
                <span className="text-[9px] text-slate-400">{contentData.knowledge_growth[contentData.knowledge_growth.length - 1]?.day}</span>
              </div>
            </>
          )
        })()}
      </div>
    </>
  )
}
