import { useState } from 'react'
import type { TimelineRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'

const INITIAL_VISIBLE = 3

export default function TimelineRenderer({ recipe }: { recipe: TimelineRecipe }) {
  const [expanded, setExpanded] = useState(!recipe.progressiveReveal)
  const events = expanded ? recipe.events : recipe.events.slice(0, INITIAL_VISIBLE)
  const hidden = recipe.events.length - events.length

  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <ol className="space-y-0">
        {events.map((event, i) => (
          <li key={event.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-violet-500 dark:bg-violet-400 shrink-0 mt-1" />
              {i < events.length - 1 && <span className="step-connector w-[2px] flex-1 min-h-[1.5rem]" />}
            </div>
            <div className="pb-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400">
                {event.when}
              </div>
              <div className="text-sm text-slate-700 dark:text-slate-200 leading-snug">{event.label}</div>
            </div>
          </li>
        ))}
      </ol>
      {hidden > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="text-xs text-violet-500 hover:underline mt-1"
        >
          Show {hidden} more
        </button>
      )}
    </VisualCard>
  )
}
