import { Loader2 } from 'lucide-react'
import clsx from 'clsx'
import type { RevenueData } from '../types'
import { StatCard } from '../components/StatCard'

interface RevenueTabProps { revenue: RevenueData | null }

export function RevenueTab({ revenue }: RevenueTabProps) {
  if (!revenue) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Loading revenue data…
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <StatCard label="MRR (USD)" value={`$${(revenue.summary.total_mrr_usd_cents / 100).toFixed(2)}`} />
        <StatCard label="MRR (INR)" value={`₹${(revenue.summary.total_mrr_inr_paise / 100).toFixed(0)}`} />
        <StatCard label="Paid users" value={String(revenue.summary.total_paid_users)} />
        <StatCard label="ARPU (USD)" value={`$${(revenue.summary.arpu_usd_cents / 100).toFixed(2)}`} />
      </div>

      <div className="glass-card rounded-xl p-5 mb-4">
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Plan Distribution</h2>
        {revenue.plan_distribution.length === 0 ? (
          <p className="text-xs text-slate-400">No active subscriptions yet.</p>
        ) : (() => {
          const maxCount = Math.max(...revenue.plan_distribution.map(p => p.user_count), 1)
          return (
            <div className="space-y-3">
              {revenue.plan_distribution.map(p => (
                <div key={p.plan_id} className="flex items-center gap-3">
                  <span className="text-xs text-slate-700 dark:text-slate-300 w-24 shrink-0 font-medium truncate">{p.plan_name}</span>
                  <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                    <div className="h-full rounded-full bg-violet-500" style={{ width: `${(p.user_count / maxCount) * 100}%` }} />
                  </div>
                  <span className="text-xs text-slate-500 w-14 text-right tabular-nums shrink-0">{p.user_count} users</span>
                  <span className="text-xs text-slate-400 w-20 text-right tabular-nums hidden sm:block shrink-0">
                    {p.mrr_usd_cents > 0
                      ? `$${(p.mrr_usd_cents / 100).toFixed(0)}/mo`
                      : p.mrr_inr_paise > 0
                        ? `₹${(p.mrr_inr_paise / 100).toFixed(0)}/mo`
                        : '—'}
                  </span>
                </div>
              ))}
            </div>
          )
        })()}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="glass-card rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Status Breakdown</h2>
          {(() => {
            const total = revenue.status_breakdown.reduce((s, r) => s + r.user_count, 0)
            const colors: Record<string, string> = {
              active: 'bg-emerald-500',
              trialing: 'bg-violet-500',
              cancelled: 'bg-rose-400',
              no_subscription: 'bg-slate-300 dark:bg-slate-600',
            }
            const labels: Record<string, string> = {
              active: 'Active', trialing: 'Trial', cancelled: 'Cancelled', no_subscription: 'Free',
            }
            return (
              <div className="space-y-2.5">
                {revenue.status_breakdown.map(r => (
                  <div key={r.status} className="flex items-center gap-2">
                    <span className="text-xs text-slate-600 dark:text-slate-400 w-20 shrink-0">
                      {labels[r.status] ?? r.status}
                    </span>
                    <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full', colors[r.status] ?? 'bg-slate-400')}
                        style={{ width: `${total > 0 ? (r.user_count / total) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-xs tabular-nums text-slate-500 w-8 text-right shrink-0">{r.user_count}</span>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>

        <div className="glass-card rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Gateway Split</h2>
          {revenue.gateway_split.length === 0 ? (
            <p className="text-xs text-slate-400">No paid subscriptions yet.</p>
          ) : (() => {
            const totalSubs = revenue.gateway_split.reduce((s, r) => s + r.subscriptions, 0)
            return (
              <div className="space-y-2.5">
                {revenue.gateway_split.map(r => (
                  <div key={r.payment_gateway} className="flex items-center gap-2">
                    <span className="text-xs text-slate-600 dark:text-slate-400 w-28 shrink-0">
                      {r.payment_gateway === 'stripe' ? 'Stripe (USD)' : r.payment_gateway === 'razorpay' ? 'Razorpay (INR)' : r.payment_gateway}
                    </span>
                    <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full', r.payment_gateway === 'stripe' ? 'bg-violet-500' : 'bg-amber-400')}
                        style={{ width: `${totalSubs > 0 ? (r.subscriptions / totalSubs) * 100 : 0}%` }}
                      />
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs tabular-nums text-slate-500">{r.subscriptions} subs</p>
                      <p className="text-xs tabular-nums text-slate-400">
                        {r.total_usd_cents > 0
                          ? `$${(r.total_usd_cents / 100).toFixed(0)}/mo`
                          : r.total_inr_paise > 0
                            ? `₹${(r.total_inr_paise / 100).toFixed(0)}/mo`
                            : '—'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>
      </div>
    </>
  )
}
