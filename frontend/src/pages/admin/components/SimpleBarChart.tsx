interface BarDatum {
  label: string
  value: number
  tooltip?: string
  secondaryLabel?: string
}

interface SimpleBarChartProps {
  data: BarDatum[]
  height?: string
  gap?: string
  showEndLabels?: boolean
  showPerBarLabels?: boolean
  maxValue?: number
}

export function SimpleBarChart({
  data,
  height = 'h-16',
  gap = 'gap-1',
  showEndLabels = false,
  showPerBarLabels = false,
  maxValue,
}: SimpleBarChartProps) {
  const max = maxValue ?? Math.max(...data.map(d => d.value), 1)

  return (
    <>
      <div className={`flex items-end ${gap} ${height}`}>
        {data.map((d, i) => {
          const pct = Math.round((d.value / max) * 100)
          return (
            <div
              key={i}
              className="flex-1 flex flex-col justify-end min-w-0"
              title={d.tooltip ?? `${d.label}: ${d.value}`}
            >
              <div
                className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t"
                style={{ height: `${Math.max(pct, 4)}%` }}
              />
            </div>
          )
        })}
      </div>

      {showEndLabels && data.length > 0 && (
        <div className="flex justify-between mt-1">
          <span className="text-[9px] text-slate-400">{data[0].label}</span>
          <span className="text-[9px] text-slate-400">{data[data.length - 1].label}</span>
        </div>
      )}

      {showPerBarLabels && (
        <div className={`flex ${gap} mt-2`}>
          {data.map((d, i) => (
            <div key={i} className="flex-1 text-center min-w-0">
              <p className="text-[9px] text-slate-400 truncate">{d.label}</p>
              {d.secondaryLabel && (
                <p className="text-[9px] font-semibold text-violet-500 tabular-nums">{d.secondaryLabel}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
