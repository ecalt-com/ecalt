import type { BeforeAfterRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

export default function BeforeAfterRenderer({ recipe }: { recipe: BeforeAfterRecipe }) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[recipe.before, recipe.after].map((state, i) => (
          <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-700/40 overflow-hidden">
            <div className={`px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider ${
              i === 0
                ? 'bg-slate-50 dark:bg-slate-800/40 text-slate-500 dark:text-slate-400'
                : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-300'
            }`}>
              {i === 0 ? 'Before' : 'After'} · {state.label}
            </div>
            <p className="px-3 py-2.5 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              {state.description}
            </p>
          </div>
        ))}
      </div>
    </VisualCard>
  )
}
