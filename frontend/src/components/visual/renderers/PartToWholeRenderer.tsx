import type { PartToWholeRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

interface Props {
  recipe: PartToWholeRecipe
  onInteraction?: (data: Record<string, unknown>) => void
}

export default function PartToWholeRenderer({ recipe, onInteraction }: Props) {
  return (
    <VisualCard>
      <VisualTitle>{recipe.whole || recipe.title}</VisualTitle>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {recipe.parts.map(part => (
          <details
            key={part.id}
            className="rounded-xl border border-slate-200 dark:border-slate-700/40 px-3 py-2 group"
            onToggle={e => {
              if ((e.target as HTMLDetailsElement).open) {
                onInteraction?.({ action: 'part_expanded', partId: part.id })
              }
            }}
          >
            <summary className="text-sm font-medium text-slate-700 dark:text-slate-200 cursor-pointer list-none flex items-center justify-between">
              {part.label}
              <span className="text-slate-400 dark:text-slate-600 text-xs group-open:rotate-180 transition-transform">▾</span>
            </summary>
            {part.description && (
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mt-1.5">{part.description}</p>
            )}
          </details>
        ))}
      </div>
    </VisualCard>
  )
}
