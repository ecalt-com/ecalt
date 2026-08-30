import { ArrowRight } from 'lucide-react'
import type { CauseEffectRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle, roleColor } from '../shared'

export default function CauseEffectRenderer({ recipe }: { recipe: CauseEffectRecipe }) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="flex flex-wrap items-center gap-2">
        {recipe.nodes.map((node, i) => (
          <div key={node.id} className="flex items-center gap-2">
            <div className={`px-3 py-2 rounded-xl border text-xs font-medium ${roleColor(node.role)}`}>
              <div className="text-[10px] uppercase tracking-wider opacity-70 mb-0.5">{node.role}</div>
              {node.label}
            </div>
            {i < recipe.nodes.length - 1 && (
              <ArrowRight size={14} className="text-slate-400 dark:text-slate-600 shrink-0" />
            )}
          </div>
        ))}
      </div>
    </VisualCard>
  )
}
