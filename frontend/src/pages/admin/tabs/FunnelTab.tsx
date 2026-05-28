import { Loader2 } from 'lucide-react'
import clsx from 'clsx'
import type { FunnelData } from '../types'
import { fmtMonth } from '../utils'

interface FunnelTabProps { funnelData: FunnelData | null }

export function FunnelTab({ funnelData }: FunnelTabProps) {
  if (!funnelData) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Loading funnel data…
      </div>
    )
  }

  return (
    <>
      <div className="glass-card rounded-xl p-5 mb-6">
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1">Free → Paid Conversion</h2>
        <p className="text-xs text-slate-400 mb-4">
          Last 180 days · {funnelData.conversion.total_signups_180d.toLocaleString()} signups
        </p>
        <div className="space-y-3 mb-4">
          {([
            { label: 'D30', pct: funnelData.conversion.converted_30d_pct, count: funnelData.conversion.converted_30d, desc: 'converted within 30 days' },
            { label: 'D60', pct: funnelData.conversion.converted_60d_pct, count: funnelData.conversion.converted_60d, desc: 'converted within 60 days' },
            { label: 'D90', pct: funnelData.conversion.converted_90d_pct, count: funnelData.conversion.converted_90d, desc: 'converted within 90 days' },
          ] as { label: string; pct: number; count: number; desc: string }[]).map(({ label, pct, count, desc }) => (
            <div key={label} className="flex items-center gap-3">
              <span className="text-xs font-mono text-slate-500 w-7 shrink-0">{label}</span>
              <div className="flex-1 h-3 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.max(pct > 0 ? 1 : 0, pct)}%` }} />
              </div>
              <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 w-12 text-right shrink-0">{pct}%</span>
              <span className="text-[11px] text-slate-400 hidden sm:block">({count} {desc})</span>
            </div>
          ))}
        </div>
        {funnelData.conversion.avg_days_to_convert != null && (
          <p className="text-xs text-slate-500">
            Avg time to convert: <span className="font-semibold text-slate-700 dark:text-slate-200">{funnelData.conversion.avg_days_to_convert} days</span>
            <span className="ml-2 text-[10px] text-slate-400">
              {funnelData.conversion.avg_days_to_convert < 7 ? '— excellent' : funnelData.conversion.avg_days_to_convert > 30 ? '— consider more nudges' : ''}
            </span>
          </p>
        )}
      </div>

      <div className="glass-card rounded-xl p-5 mb-6">
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">
          Activations vs Cancellations (last 6 months)
        </h2>
        {funnelData.monthly_churn.length === 0 ? (
          <p className="text-xs text-slate-400">No subscription data yet.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs mb-4">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700">
                    <th className="text-left px-3 py-2 text-slate-500 font-semibold">Month</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">New subs</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">Cancellations</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">Net</th>
                    <th className="px-3 py-2 w-40 hidden sm:table-cell" />
                  </tr>
                </thead>
                <tbody>
                  {funnelData.monthly_churn.map(r => {
                    const net = r.new_subscriptions - r.cancellations
                    const maxVal = Math.max(...funnelData.monthly_churn.map(x => x.new_subscriptions), 1)
                    return (
                      <tr key={r.month} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                        <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300 font-medium">{fmtMonth(r.month)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-emerald-600 dark:text-emerald-400 font-medium">{r.new_subscriptions}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-rose-500 dark:text-rose-400">{r.cancellations}</td>
                        <td className={clsx('px-3 py-2.5 text-right tabular-nums font-semibold', net >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400')}>
                          {net >= 0 ? `+${net}` : net}
                        </td>
                        <td className="px-3 py-2.5 hidden sm:table-cell">
                          <div className="flex items-center gap-1 h-3">
                            <div className="h-full rounded bg-emerald-500" style={{ width: `${(r.new_subscriptions / maxVal) * 100}%`, minWidth: r.new_subscriptions > 0 ? '2px' : '0' }} />
                            <div className="h-full rounded bg-rose-400" style={{ width: `${(r.cancellations / maxVal) * 100}%`, minWidth: r.cancellations > 0 ? '2px' : '0' }} />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-emerald-500" /><span className="text-[10px] text-slate-500">New</span></div>
              <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-rose-400" /><span className="text-[10px] text-slate-500">Cancelled</span></div>
            </div>
          </>
        )}
      </div>

      <div className="glass-card rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            Trial Exhausted — Never Upgraded
            <span className="ml-2 text-xs font-normal text-slate-400">{funnelData.trial_exhausted_never_upgraded.length} shown</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">Used 6+ messages but never paid — highest-intent re-engagement audience.</p>
        </div>
        {funnelData.trial_exhausted_never_upgraded.length === 0 ? (
          <p className="text-xs text-slate-400 px-5 py-6 text-center">No trial-exhausted users found.</p>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
            {funnelData.trial_exhausted_never_upgraded.map(u => {
              const signupDate = u.signup_date ? new Date(u.signup_date) : null
              const daysSinceSignup = signupDate ? Math.floor((Date.now() - signupDate.getTime()) / 86_400_000) : null
              return (
                <div key={u.uid} className="px-5 py-3 flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{u.display_name ?? u.email ?? u.uid}</p>
                    <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[10px] text-slate-500">{daysSinceSignup !== null ? `joined ${daysSinceSignup}d ago` : '—'}</p>
                    <p className="text-[10px] text-slate-400">{u.signup_date ?? '—'}</p>
                  </div>
                  <div className="shrink-0 text-right w-20 hidden sm:block">
                    <p className="text-xs tabular-nums font-medium text-amber-600 dark:text-amber-400">{u.lifetime_messages} msgs</p>
                    <p className="text-[10px] text-slate-400">used</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
