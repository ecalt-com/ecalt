import { ArrowRight } from 'lucide-react'
import type { ProcessFlowRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle, roleColor } from '../shared'

// Node order from the recipe is already left-to-right (spec section 11.1) —
// v1 renders that order directly rather than laying out the full
// nodes/connections graph, which would need a real graph-layout engine for
// marginal benefit at this stage.
export default function ProcessFlowRenderer({ recipe }: { recipe: ProcessFlowRecipe }) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="flex flex-wrap items-center gap-2">
        {recipe.nodes.map((node, i) => (
          <div key={node.id} className="flex items-center gap-2">
            <span className={`px-3 py-2 rounded-xl border text-xs font-medium ${roleColor(node.role)}`}>
              {node.label}
            </span>
            {i < recipe.nodes.length - 1 && (
              <ArrowRight size={14} className="text-slate-400 dark:text-slate-600 shrink-0" />
            )}
          </div>
        ))}
      </div>
    </VisualCard>
  )
}
