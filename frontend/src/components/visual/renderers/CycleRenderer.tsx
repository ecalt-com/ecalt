import { ArrowRight, RotateCcw } from 'lucide-react'
import type { CycleRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

export default function CycleRenderer({ recipe }: { recipe: CycleRecipe }) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="flex flex-wrap items-center gap-2">
        {recipe.nodes.map((node, i) => (
          <div key={node.id} className="flex items-center gap-2">
            <span className="px-3 py-2 rounded-xl border border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/25 dark:bg-violet-500/10 dark:text-violet-300 text-xs font-medium">
              {node.label}
            </span>
            {i < recipe.nodes.length - 1 && (
              <ArrowRight size={14} className="text-slate-400 dark:text-slate-600 shrink-0" />
            )}
          </div>
        ))}
        {recipe.looping && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 ml-1">
            <RotateCcw size={13} />
            <span>repeats</span>
          </div>
        )}
      </div>
    </VisualCard>
  )
}
