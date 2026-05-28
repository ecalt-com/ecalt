import clsx from 'clsx'
import { calcPct, fmtCents, fmtPct } from '../utils'

interface BudgetBarProps { spent: number; budget: number }

export function BudgetBar({ spent, budget }: BudgetBarProps) {
  const p = calcPct(spent, budget)
  const barCls = p >= 90 ? 'bg-rose-500' : p >= 70 ? 'bg-amber-400' : 'bg-emerald-500'
  const txtCls = p >= 90 ? 'text-rose-500' : p >= 70 ? 'text-amber-500' : 'text-emerald-600 dark:text-emerald-400'
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-slate-600 dark:text-slate-300">
          {fmtCents(spent)}<span className="text-slate-400"> / {fmtCents(budget)}</span>
        </span>
        <span className={clsx('font-semibold tabular-nums', txtCls)}>{fmtPct(spent, budget)}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
        <div
          className={clsx('h-full rounded-full', barCls)}
          style={{ width: `${Math.max(spent > 0 ? 0.5 : 0, p)}%` }}
        />
      </div>
    </div>
  )
}
