import type { QuantityComparisonRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

// Bars scale linearly against the max value, axis starts at zero — server
// validation already rejects negative values (spec section 11.9: avoid
// misleading scale).
export default function QuantityComparisonRenderer({ recipe }: { recipe: QuantityComparisonRecipe }) {
  const max = Math.max(...recipe.items.map(i => i.value), 1)
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="space-y-2.5">
        {recipe.items.map(item => (
          <div key={item.id}>
            <div className="flex items-baseline justify-between text-xs mb-1">
              <span className="font-medium text-slate-700 dark:text-slate-200">{item.label}</span>
              <span className="text-slate-500 dark:text-slate-400 tabular-nums">
                {item.value}{item.unit ? ` ${item.unit}` : ''}
              </span>
            </div>
            <div className="h-2.5 rounded-full bg-slate-100 dark:bg-slate-800/60 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
                style={{ width: `${Math.max((item.value / max) * 100, 2)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </VisualCard>
  )
}
