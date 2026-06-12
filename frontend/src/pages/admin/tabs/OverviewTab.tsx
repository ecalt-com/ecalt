import { Loader2 } from 'lucide-react'
import type { Stats, PlanRow, FeatureUsageData } from '../types'
import { INTERACTION_LABELS } from '../constants'
import { fmtCents } from '../utils'
import { StatCard } from '../components/StatCard'
import { FeatureTrendChart } from '../components/FeatureTrendChart'

interface OverviewTabProps {
  stats: Stats | null
  plans: PlanRow[]
  featureUsage: FeatureUsageData | null
}

export function OverviewTab({ stats, plans, featureUsage }: OverviewTabProps) {
  return (
    <>
      {stats ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <StatCard label="Total users"      value={stats.total_users} />
          <StatCard label="DAU"              value={stats.dau} />
          <StatCard label="Messages today"   value={stats.messages_today} />
          <StatCard label="Monthly API cost" value={`$${(stats.monthly_api_cost_cents / 100).toFixed(2)}`} />
        </div>
      ) : (
        <div className="flex items-center gap-2 text-slate-500 text-sm mb-8">
          <Loader2 size={14} className="animate-spin" /> Loading stats…
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Active Plans</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {plans.filter(p => p.is_active).map(p => (
          <div key={p.plan_id} className="glass-card rounded-xl p-3 flex items-center justify-between">
            <span className="text-xs text-slate-700 dark:text-slate-300 font-medium">{p.name}</span>
            <span className="text-xs text-slate-500">
              {p.base_price_cents === 0 ? 'Free' : `$${(p.base_price_cents / 100).toFixed(0)}/mo`}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-8">
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">
          Feature Usage — {new Date().toLocaleString('default', { month: 'long', year: 'numeric' })}
        </h2>

        {!featureUsage ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm mb-6">
            <Loader2 size={14} className="animate-spin" /> Loading feature data…
          </div>
        ) : (
          <>
            <div className="glass-card rounded-xl overflow-hidden mb-6">
              {featureUsage.this_month.length === 0 ? (
                <p className="text-xs text-slate-400 px-4 py-6 text-center">No feature usage data for this month yet.</p>
              ) : (
                <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Feature</th>
                      <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Users</th>
                      <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Requests</th>
                      <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Cost</th>
                      <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden md:table-cell">Cost/req</th>
                      <th className="px-4 py-2.5 text-slate-500 font-semibold hidden lg:table-cell w-40">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {featureUsage.this_month.map(r => {
                      const totalCost = featureUsage.this_month.reduce((s, x) => s + Number(x.total_cost_cents), 0)
                      const share = totalCost > 0 ? (Number(r.total_cost_cents) / totalCost) * 100 : 0
                      return (
                        <tr key={r.interaction_type} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                          <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                            {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-500 hidden sm:table-cell">{r.unique_users}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-500">{Number(r.total_requests).toLocaleString()}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">{fmtCents(Number(r.total_cost_cents))}</td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-400 hidden md:table-cell">
                            {r.avg_cost_per_request_cents != null ? `$${Number(r.avg_cost_per_request_cents).toFixed(4)}` : '—'}
                          </td>
                          <td className="px-4 py-2.5 hidden lg:table-cell">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                <div className="h-full rounded-full bg-violet-500" style={{ width: `${share}%` }} />
                              </div>
                              <span className="text-xs tabular-nums text-slate-400 w-7 text-right shrink-0">{Math.round(share)}%</span>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                </div>
              )}
            </div>

            <div className="glass-card rounded-xl p-5 mb-6">
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">6-Month Cost Trend per Feature</h2>
              {featureUsage.trend.length === 0 ? (
                <p className="text-xs text-slate-400">No trend data yet.</p>
              ) : (
                <FeatureTrendChart trend={featureUsage.trend} />
              )}
            </div>

            <div className="glass-card rounded-xl p-5 mb-4">
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Model Distribution</h2>
              {featureUsage.models.length === 0 ? (
                <p className="text-xs text-slate-400">No model data for this month yet.</p>
              ) : (
                <div className="space-y-2.5">
                  {featureUsage.models.map(m => {
                    const maxCount = Math.max(...featureUsage.models.map(x => x.message_count), 1)
                    return (
                      <div key={m.model_used} className="flex items-center gap-3">
                        <span className="text-xs font-mono text-slate-600 dark:text-slate-400 w-36 shrink-0 truncate">{m.model_used}</span>
                        <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                          <div className="h-full rounded-full bg-violet-500/70" style={{ width: `${(m.message_count / maxCount) * 100}%` }} />
                        </div>
                        <span className="text-xs tabular-nums text-slate-500 w-20 text-right shrink-0">{m.message_count.toLocaleString()} calls</span>
                        <span className="text-xs tabular-nums text-slate-400 w-14 text-right shrink-0 hidden sm:block">{fmtCents(m.total_cost_cents)}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
