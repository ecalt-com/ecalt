import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import type { ProgressiveSequenceRecipe } from '../../../lib/types'
import { VisualCard, VisualTitle } from '../shared'
import { useReducedMotion } from '../../../lib/useReducedMotion'

const AUTO_ADVANCE_MS = 4000

interface Props {
  recipe: ProgressiveSequenceRecipe
  onInteraction?: (data: Record<string, unknown>) => void
  onComplete?: () => void
}

// Highest-priority native renderer (spec section 11.10) — this is what
// replaces a lot of "just generate a short video" requests: one idea at a
// time, learner-paced, no runtime generation cost.
export default function ProgressiveSequenceRenderer({ recipe, onInteraction, onComplete }: Props) {
  const [index, setIndex] = useState(0)
  const reducedMotion = useReducedMotion()
  const autoPlay = recipe.autoPlay && !reducedMotion
  const completedRef = useRef(false)
  const total = recipe.steps.length
  const isLast = index === total - 1

  useEffect(() => {
    if (isLast && !completedRef.current) {
      completedRef.current = true
      onComplete?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLast])

  useEffect(() => {
    if (!autoPlay || isLast) return
    const t = setTimeout(() => setIndex(i => Math.min(i + 1, total - 1)), AUTO_ADVANCE_MS)
    return () => clearTimeout(t)
  }, [autoPlay, isLast, index, total])

  const step = recipe.steps[index]

  return (
    <VisualCard>
      <VisualTitle>{recipe.title}</VisualTitle>
      <div className="rounded-xl border border-slate-200 dark:border-slate-700/40 bg-slate-50/60 dark:bg-slate-800/30 px-4 py-3 min-h-[4.5rem]">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-violet-500 dark:text-violet-400 mb-1">
          Step {index + 1} of {total} · {step.label}
        </div>
        <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{step.content}</p>
      </div>

      <div className="flex items-center justify-between mt-3">
        <button
          onClick={() => { setIndex(i => Math.max(i - 1, 0)); onInteraction?.({ action: 'previous', toIndex: index - 1 }) }}
          disabled={index === 0}
          className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-violet-600 dark:hover:text-violet-400 disabled:opacity-30 disabled:pointer-events-none"
        >
          <ChevronLeft size={14} /> Previous
        </button>

        <div className="flex items-center gap-1.5">
          {recipe.steps.map((s, i) => (
            <span
              key={s.id}
              className={`w-1.5 h-1.5 rounded-full ${i === index ? 'bg-violet-500' : 'bg-slate-200 dark:bg-slate-700'}`}
            />
          ))}
        </div>

        {isLast ? (
          <button
            onClick={() => { setIndex(0); onInteraction?.({ action: 'replay' }) }}
            className="flex items-center gap-1 text-xs font-medium text-violet-500 hover:text-violet-600"
          >
            <RotateCcw size={12} /> Replay
          </button>
        ) : (
          <button
            onClick={() => { setIndex(i => Math.min(i + 1, total - 1)); onInteraction?.({ action: 'next', toIndex: index + 1 }) }}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-violet-600 dark:hover:text-violet-400"
          >
            Next <ChevronRight size={14} />
          </button>
        )}
      </div>
    </VisualCard>
  )
}
