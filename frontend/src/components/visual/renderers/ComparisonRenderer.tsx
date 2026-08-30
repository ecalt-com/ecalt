import type { ComparisonRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

export default function ComparisonRenderer({ recipe }: { recipe: ComparisonRecipe }) {
  const cols = recipe.columns.length
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className={`grid grid-cols-1 gap-3 ${cols === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
        {recipe.columns.map(col => (
          <div key={col.id} className="rounded-xl border border-slate-200 dark:border-slate-700/40 overflow-hidden">
            <div className="px-3 py-2 bg-slate-50/80 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-700/30">
              <h5 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{col.label}</h5>
            </div>
            <ul className="px-3 py-2.5 space-y-1.5">
              {col.items.map((item, j) => (
                <li key={j} className="flex gap-2 items-start text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  <span className="text-violet-500 dark:text-violet-400 shrink-0 mt-[3px] text-[8px]">✦</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </VisualCard>
  )
}
