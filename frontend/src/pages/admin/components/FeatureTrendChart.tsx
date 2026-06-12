import { INTERACTION_LABELS, FEATURE_COLORS, OTHER_COLOR } from '../constants'
import { fmtCents, fmtMonth } from '../utils'
import type { FeatureTrendPoint } from '../types'

export function FeatureTrendChart({ trend }: { trend: FeatureTrendPoint[] }) {
  const featureTotals: Record<string, number> = {}
  trend.forEach(r => {
    featureTotals[r.interaction_type] = (featureTotals[r.interaction_type] ?? 0) + Number(r.total_requests)
  })
  const topFeatures = Object.entries(featureTotals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([k]) => k)

  const byMonth: Record<string, Record<string, number>> = {}
  trend.forEach(r => {
    if (!byMonth[r.period_start]) byMonth[r.period_start] = {}
    const key = topFeatures.includes(r.interaction_type) ? r.interaction_type : '__other__'
    byMonth[r.period_start][key] = (byMonth[r.period_start][key] ?? 0) + Number(r.total_cost_cents)
  })
  const uniqueMonths = Object.keys(byMonth).sort()
  const hasOther = trend.some(r => !topFeatures.includes(r.interaction_type))
  const displayFeatures = hasOther ? [...topFeatures, '__other__'] : topFeatures
  const maxGroupVal = Math.max(
    ...uniqueMonths.map(m => displayFeatures.reduce((s, f) => s + (byMonth[m]?.[f] ?? 0), 0)),
    1,
  )

  return (
    <>
      <div className="flex items-end gap-3 h-24">
        {uniqueMonths.map(month => (
          <div key={month} className="flex-1 flex flex-col justify-end min-w-0">
            <div className="flex items-end gap-0.5 h-20">
              {displayFeatures.map((feat, i) => {
                const val = byMonth[month]?.[feat] ?? 0
                const pct = (val / maxGroupVal) * 100
                const color = feat === '__other__' ? OTHER_COLOR : (FEATURE_COLORS[i] ?? OTHER_COLOR)
                return (
                  <div
                    key={feat}
                    className="flex-1 flex items-end min-w-0 h-full"
                    title={`${feat === '__other__' ? 'Other' : (INTERACTION_LABELS[feat] ?? feat)}: ${fmtCents(val)}`}
                  >
                    <div
                      className={`w-full rounded-t ${color}`}
                      style={{ height: val > 0 ? `${Math.max(pct, 4)}%` : '0' }}
                    />
                  </div>
                )
              })}
            </div>
            <p className="text-[9px] text-slate-400 text-center mt-1 truncate">{fmtMonth(month)}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 mt-3">
        {displayFeatures.map((feat, i) => (
          <div key={feat} className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-sm ${feat === '__other__' ? OTHER_COLOR : (FEATURE_COLORS[i] ?? OTHER_COLOR)}`} />
            <span className="text-xs text-slate-500">
              {feat === '__other__' ? 'Other' : (INTERACTION_LABELS[feat] ?? feat)}
            </span>
          </div>
        ))}
      </div>
    </>
  )
}
