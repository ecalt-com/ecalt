import { AlertTriangle, Loader2, Cpu, Save, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'
import type { CostAnalysis, UsageByModel, DailyUsage, AIConfig, ModelOption, UserDetail } from '../types'
import { INTERACTION_LABELS, selectCls } from '../constants'
import { fmtCents, fmtMonth } from '../utils'
import { UserDetailPanel } from '../components/UserDetailPanel'

interface AIProvidersTabProps {
  costAnalysis: CostAnalysis | null
  usageByModel: UsageByModel[]
  dailyUsage: DailyUsage[]
  aiConfigs: AIConfig[]
  availableModels: Record<string, ModelOption[]>
  aiEdits: Record<string, AIConfig>
  savingAI: string | null
  totalMonthlyCost: number
  expandedUid: string | null
  userDetails: Record<string, UserDetail>
  loadingDetail: string | null
  onExpandUser: (uid: string) => void
  onSaveAI: (interactionType: string) => void
  onSetAiEdit: (interactionType: string, field: 'provider' | 'model', value: string) => void
}

export function AIProvidersTab({
  costAnalysis,
  usageByModel,
  dailyUsage,
  aiConfigs,
  availableModels,
  aiEdits,
  savingAI,
  totalMonthlyCost,
  expandedUid,
  userDetails,
  loadingDetail,
  onExpandUser,
  onSaveAI,
  onSetAiEdit,
}: AIProvidersTabProps) {
  return (
    <>
      {costAnalysis && (
        <>
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cost vs Revenue by Plan</h2>
          <div className="glass-card rounded-xl overflow-hidden mb-6">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Plan</th>
                  <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Users</th>
                  <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Avg/user</th>
                  <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Max/user</th>
                  <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Cost/Rev%</th>
                  <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Health</th>
                </tr>
              </thead>
              <tbody>
                {costAnalysis.plan_margins.map(r => {
                  const pct = Number(r.cost_revenue_pct)
                  const health = pct >= 60
                    ? { label: 'At risk', cls: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10' }
                    : pct >= 30
                      ? { label: 'Watch', cls: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10' }
                      : { label: 'Healthy', cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10' }
                  return (
                    <tr key={r.plan_id} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                      <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300 font-medium">{r.plan_name}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400">{r.active_users}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400 hidden sm:table-cell">{fmtCents(r.avg_spent_cents)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400 hidden sm:table-cell">{fmtCents(r.max_spent_cents)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400">
                        {r.price_cents > 0 ? `${pct}%` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {r.price_cents > 0
                          ? <span className={clsx('text-[10px] font-semibold px-1.5 py-0.5 rounded', health.cls)}>{health.label}</span>
                          : <span className="text-[10px] text-slate-400">—</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {costAnalysis.at_risk_users.length > 0 && (
            <>
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={13} className="text-amber-500 shrink-0" />
                <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                  Users Near Budget Limit
                  <span className="ml-2 text-amber-500">({costAnalysis.at_risk_users.length} above 75%)</span>
                </h2>
              </div>
              <div className="glass-card rounded-xl overflow-hidden mb-6">
                <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                  {costAnalysis.at_risk_users.map(u => {
                    const isExpanded = expandedUid === u.uid
                    const detail = userDetails[u.uid]
                    const isLoadingThis = loadingDetail === u.uid
                    const pct = Math.min(100, u.pct_used)
                    const barColor = pct >= 90 ? 'bg-rose-500' : 'bg-amber-400'
                    const txtColor = pct >= 90 ? 'text-rose-500' : 'text-amber-500'
                    return (
                      <div key={u.uid}>
                        <div
                          className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                          onClick={() => onExpandUser(u.uid)}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{u.display_name ?? u.email ?? u.uid}</p>
                            <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                          </div>
                          <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono shrink-0 hidden sm:block">{u.plan_id}</span>
                          <div className="shrink-0 flex flex-col items-end gap-0.5 w-32">
                            <div className="flex items-center gap-1.5 w-full">
                              <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                                <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
                              </div>
                              <span className={clsx('text-[10px] tabular-nums font-semibold w-10 text-right', txtColor)}>{u.pct_used}%</span>
                            </div>
                            <span className="text-[10px] text-slate-400 tabular-nums">{fmtCents(u.spent_cents)} / {fmtCents(u.budget_cents)}</span>
                          </div>
                          <div className="text-slate-400 shrink-0">
                            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="border-t border-slate-100 dark:border-slate-700/50 px-4 pb-5 pt-4">
                            <UserDetailPanel detail={detail} isLoading={isLoadingThis} />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}

          {costAnalysis.by_interaction.length > 0 && (
            <>
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cost by Feature (this month)</h2>
              <div className="glass-card rounded-xl p-4 mb-6">
                {(() => {
                  const maxCost = Math.max(...costAnalysis.by_interaction.map(r => r.total_cost_cents), 1)
                  return (
                    <div className="space-y-2.5">
                      {costAnalysis.by_interaction.map(r => (
                        <div key={r.interaction_type} className="flex items-center gap-3">
                          <span className="text-xs text-slate-600 dark:text-slate-400 w-28 shrink-0 truncate">
                            {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                          </span>
                          <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                            <div className="h-full rounded-full bg-violet-500" style={{ width: `${(r.total_cost_cents / maxCost) * 100}%` }} />
                          </div>
                          <span className="text-xs tabular-nums font-medium text-slate-700 dark:text-slate-300 w-14 text-right shrink-0">{fmtCents(r.total_cost_cents)}</span>
                          <span className="text-[10px] tabular-nums text-slate-400 w-16 text-right shrink-0 hidden sm:block">
                            {(r.total_requests ?? 0).toLocaleString()} req
                          </span>
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </div>
            </>
          )}

          {costAnalysis.cache_trend.length > 0 && (
            <>
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cache Hit Rate (6 months)</h2>
              <div className="glass-card rounded-xl p-4 mb-8">
                <div className="flex items-end gap-2 h-16">
                  {costAnalysis.cache_trend.map(r => {
                    const pct = Number(r.cache_hit_pct)
                    return (
                      <div
                        key={r.period_start}
                        className="flex-1 flex flex-col justify-end min-w-0"
                        title={`${fmtMonth(r.period_start)}: ${pct}% cache hit`}
                      >
                        <div className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t" style={{ height: `${Math.max(pct, 4)}%` }} />
                      </div>
                    )
                  })}
                </div>
                <div className="flex gap-2 mt-2">
                  {costAnalysis.cache_trend.map(r => (
                    <div key={r.period_start} className="flex-1 text-center min-w-0">
                      <p className="text-[9px] text-slate-400 truncate">{fmtMonth(r.period_start)}</p>
                      <p className="text-[9px] font-semibold text-violet-500 tabular-nums">{r.cache_hit_pct}%</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="border-t border-slate-200 dark:border-slate-700/50 mb-8" />
        </>
      )}

      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Usage This Month</h2>
      {usageByModel.length > 0 ? (
        <div className="glass-card rounded-xl overflow-hidden mb-8">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Model</th>
                <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Messages</th>
                <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Est. Cost</th>
                <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Share</th>
              </tr>
            </thead>
            <tbody>
              {usageByModel.map(r => (
                <tr key={r.model_used} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <Cpu size={11} className="text-slate-400 shrink-0" />
                      <span className="font-mono text-slate-700 dark:text-slate-300">{r.model_used}</span>
                      {r.model_used.startsWith('gpt') || r.model_used.startsWith('o1')
                        ? <span className="text-[9px] bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5 rounded-full">OpenAI</span>
                        : <span className="text-[9px] bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 px-1.5 py-0.5 rounded-full">Anthropic</span>
                      }
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{r.message_count.toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">${(r.total_cost_cents / 100).toFixed(4)}</td>
                  <td className="px-4 py-2.5 text-right text-slate-500">
                    {totalMonthlyCost > 0 ? `${Math.round((r.total_cost_cents / totalMonthlyCost) * 100)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300 font-semibold">Total</td>
                <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-300 font-semibold">
                  {usageByModel.reduce((s, r) => s + r.message_count, 0).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-300 font-semibold">
                  ${(totalMonthlyCost / 100).toFixed(4)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <p className="text-xs text-slate-400 mb-8">No usage data yet this month.</p>
      )}

      {dailyUsage.length > 0 && (
        <div className="glass-card rounded-xl p-4 mb-8">
          <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-3">Daily Messages (last 14 days)</p>
          <div className="flex items-end gap-1 h-16">
            {dailyUsage.map(d => {
              const max = Math.max(...dailyUsage.map(x => x.messages), 1)
              const pct = Math.round((d.messages / max) * 100)
              return (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1" title={`${d.day}: ${d.messages}`}>
                  <div className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t" style={{ height: `${Math.max(pct, 4)}%` }} />
                </div>
              )
            })}
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[9px] text-slate-400">{dailyUsage[0]?.day}</span>
            <span className="text-[9px] text-slate-400">{dailyUsage[dailyUsage.length - 1]?.day}</span>
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Model Routing</h2>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
        Set which provider and model handles each interaction type. Changes take effect immediately for new conversations.
      </p>
      <div className="space-y-3">
        {aiConfigs.map(cfg => {
          const pending = aiEdits[cfg.interaction_type] ?? cfg
          const isDirty = !!aiEdits[cfg.interaction_type]
          const models = availableModels[pending.provider] ?? []
          return (
            <div key={cfg.interaction_type} className="glass-card rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    {INTERACTION_LABELS[cfg.interaction_type] ?? cfg.interaction_type}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono">{cfg.interaction_type}</p>
                </div>
                {isDirty && (
                  <button
                    onClick={() => onSaveAI(cfg.interaction_type)}
                    disabled={savingAI === cfg.interaction_type}
                    className="flex items-center gap-1.5 text-xs bg-violet-600 hover:bg-violet-500 text-white px-3 py-1.5 rounded-lg transition-colors"
                  >
                    {savingAI === cfg.interaction_type ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                    Save
                  </button>
                )}
              </div>
              <div className="flex gap-3 flex-wrap">
                <label className="text-xs text-slate-500">
                  Provider
                  <select
                    value={pending.provider}
                    onChange={e => onSetAiEdit(cfg.interaction_type, 'provider', e.target.value)}
                    className={`block mt-1 ${selectCls}`}
                  >
                    {Object.keys(availableModels).map(p => (
                      <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500 flex-1 min-w-[180px]">
                  Model
                  <select
                    value={pending.model}
                    onChange={e => onSetAiEdit(cfg.interaction_type, 'model', e.target.value)}
                    className={`block mt-1 w-full ${selectCls}`}
                  >
                    {models.map(m => (
                      <option key={m.id} value={m.id}>{m.label}</option>
                    ))}
                  </select>
                </label>
                <div className="text-xs text-slate-400 self-end pb-1.5">
                  {pending.provider === 'anthropic' ? '🟣 Anthropic' : '🟢 OpenAI'}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
