import { BarChart2 } from 'lucide-react'
import clsx from 'clsx'
import { Loader2 } from 'lucide-react'
import type { UserDetail } from '../types'
import { INTERACTION_LABELS } from '../constants'
import { fmtCents, fmtTokens, fmtMonth } from '../utils'
import { BudgetBar } from './BudgetBar'

interface UserDetailPanelProps {
  detail: UserDetail | undefined
  isLoading: boolean
}

export function UserDetailPanel({ detail, isLoading }: UserDetailPanelProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-slate-400 text-xs py-4 justify-center">
        <Loader2 size={13} className="animate-spin" /> Loading usage detail…
      </div>
    )
  }

  if (!detail) {
    return <p className="text-xs text-slate-400 text-center py-4">Failed to load detail.</p>
  }

  return (
    <div className="space-y-5">
      {/* Profile meta */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {[
          { label: 'Plan',        value: detail.profile.plan_name },
          { label: 'Status',      value: detail.profile.sub_status },
          { label: 'Streak',      value: `${detail.profile.streak_days} days` },
          { label: 'Age group',   value: detail.profile.age_group_flag ?? '—' },
          { label: 'Last active', value: detail.profile.last_active_date ? new Date(detail.profile.last_active_date).toLocaleDateString() : '—' },
          { label: 'Joined',      value: new Date(detail.profile.created_at).toLocaleDateString() },
          { label: 'Gateway',     value: detail.profile.payment_gateway ?? '—' },
          { label: 'Account',     value: detail.profile.account_status },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
            <p className="font-medium text-slate-700 dark:text-slate-200 mt-0.5 truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* Current month usage */}
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
          <BarChart2 size={11} /> This Month
        </p>
        <BudgetBar
          spent={detail.current_month.spent_cents}
          budget={detail.current_month.budget_cents ?? 0}
        />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Requests',      value: String(detail.current_month.message_count) },
            { label: 'Input tokens',  value: fmtTokens(detail.current_month.input_tokens) },
            { label: 'Output tokens', value: fmtTokens(detail.current_month.output_tokens) },
            { label: 'Cached tokens', value: fmtTokens(detail.current_month.cached_input_tokens) },
          ].map(({ label, value }) => (
            <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5 text-xs">
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
              <p className="font-bold text-slate-800 dark:text-slate-100 tabular-nums mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Breakdown by feature */}
      {detail.breakdown.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Usage by Feature</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/60">
                  <th className="text-left py-1.5 pr-3 text-slate-400 font-semibold">Feature</th>
                  <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">Req</th>
                  <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">In</th>
                  <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">Out</th>
                  <th className="text-right py-1.5 pl-2 text-slate-400 font-semibold">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                {detail.breakdown.map(r => (
                  <tr key={r.interaction_type}>
                    <td className="py-1.5 pr-3 text-slate-700 dark:text-slate-300 font-medium">
                      {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                    </td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{r.request_count}</td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{fmtTokens(r.input_tokens)}</td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{fmtTokens(r.output_tokens)}</td>
                    <td className="py-1.5 pl-2 text-right tabular-nums font-medium text-slate-700 dark:text-slate-300">{fmtCents(r.estimated_cost_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Monthly history */}
      {detail.history.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">12-Month History</p>
          <div className="space-y-1.5">
            {(() => {
              const maxCost = Math.max(...detail.history.map(r => r.estimated_cost_cents), 1)
              return detail.history.map(r => (
                <div key={r.period_start} className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-400 w-14 shrink-0">{fmtMonth(r.period_start)}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-violet-500"
                      style={{ width: `${(r.estimated_cost_cents / maxCost) * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] tabular-nums text-slate-500 w-10 text-right">{fmtCents(r.estimated_cost_cents)}</span>
                  <span className="text-[10px] tabular-nums text-slate-400 w-10 text-right hidden sm:block">{r.message_count} req</span>
                </div>
              ))
            })()}
          </div>
        </div>
      )}

      {/* Lifetime stats */}
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Lifetime</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
          {[
            { label: 'Total cost',     value: fmtCents(detail.lifetime.lifetime_cost_cents) },
            { label: 'Total requests', value: String(detail.lifetime.lifetime_message_count) },
            { label: 'Chat messages',  value: String(detail.lifetime.lifetime_chat_messages) },
            { label: 'Conversations',  value: String(detail.lifetime.total_conversations) },
            { label: 'Input tokens',   value: fmtTokens(detail.lifetime.lifetime_input_tokens) },
            { label: 'First active',   value: detail.lifetime.first_active_month ? fmtMonth(detail.lifetime.first_active_month) : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5">
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
              <p className="font-bold text-slate-800 dark:text-slate-100 tabular-nums mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Coupon redemptions */}
      {detail.coupons.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Coupons Redeemed</p>
          <div className="space-y-1.5">
            {detail.coupons.map(c => (
              <div key={c.code} className="flex items-center gap-3 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-lg px-3 py-2">
                <code className={clsx(
                  'font-bold px-1.5 py-0.5 rounded text-[10px]',
                  c.is_active
                    ? 'text-violet-700 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/15'
                    : 'text-slate-500 bg-slate-200 dark:bg-slate-700'
                )}>{c.code}</code>
                <span className="text-slate-600 dark:text-slate-400 flex-1 truncate">{c.description}</span>
                {c.credit_applied_cents > 0 && (
                  <span className="text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0">+{fmtCents(c.credit_applied_cents)}</span>
                )}
                {c.bonus_messages_applied > 0 && (
                  <span className="text-blue-600 dark:text-blue-400 tabular-nums shrink-0">+{c.bonus_messages_applied} msg</span>
                )}
                {!c.is_active && (
                  <span className="text-slate-400 text-[10px] shrink-0">expired</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
