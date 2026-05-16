import { useState } from 'react'
import clsx from 'clsx'
import { BookOpen, Wrench, Zap, Compass, Check, ChevronDown, Loader2 } from 'lucide-react'
import type { JourneyStep } from '../lib/types'
import { getStepContent } from '../lib/api'
import MarkdownContent from './MarkdownContent'

const typeConfig = {
  concept:   { icon: BookOpen, color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 border-violet-200 dark:bg-violet-400/10 dark:border-violet-400/20', label: 'Learn' },
  practice:  { icon: Wrench,   color: 'text-cyan-600 dark:text-cyan-400',     bg: 'bg-cyan-50 border-cyan-200 dark:bg-cyan-400/10 dark:border-cyan-400/20',         label: 'Practice' },
  challenge: { icon: Zap,      color: 'text-amber-600 dark:text-amber-400',   bg: 'bg-amber-50 border-amber-200 dark:bg-amber-400/10 dark:border-amber-400/20',     label: 'Challenge' },
  explore:   { icon: Compass,  color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-400/10 dark:border-emerald-400/20', label: 'Explore' },
}

interface StepNodeProps {
  step: JourneyStep
  index: number
  isLast: boolean
  journeyId: string
  getToken: () => Promise<string | null>
  onToggle?: (id: string) => void | Promise<void>
}

export default function StepNode({ step, index, isLast, journeyId, getToken, onToggle }: StepNodeProps) {
  const config = typeConfig[step.type]
  const Icon = config.icon
  const [expanded, setExpanded] = useState(false)
  const [content, setContent] = useState<string | null>(null)
  const [loadingContent, setLoadingContent] = useState(false)
  const [contentError, setContentError] = useState<string | null>(null)

  const handleExpand = async () => {
    const next = !expanded
    setExpanded(next)
    if (next && content === null && !loadingContent) {
      setLoadingContent(true)
      setContentError(null)
      try {
        const token = await getToken()
        const res = await getStepContent(journeyId, step.id, token ?? undefined)
        setContent(res.content)
      } catch {
        setContentError('Could not load lesson content. Try again.')
      } finally {
        setLoadingContent(false)
      }
    }
  }

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <button
          onClick={() => onToggle?.(step.id)}
          className={clsx(
            'w-10 h-10 rounded-full border-2 flex items-center justify-center shrink-0 transition-all duration-200',
            step.completed
              ? 'bg-violet-600 border-violet-600 text-white'
              : 'border-slate-200 bg-white text-slate-500 hover:border-violet-400 hover:text-violet-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500 dark:hover:border-violet-500/50 dark:hover:text-violet-400'
          )}
        >
          {step.completed ? <Check size={16} /> : <span className="text-xs font-bold">{index + 1}</span>}
        </button>
        {!isLast && <div className="step-connector flex-1 my-1" />}
      </div>

      <div className={clsx('pb-8 flex-1', isLast && 'pb-0')}>
        <div
          className={clsx(
            'glass-card rounded-xl transition-all duration-200',
            expanded ? 'border-violet-200 dark:border-violet-500/30' : 'hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer'
          )}
        >
          {/* Header row */}
          <button
            onClick={handleExpand}
            className="w-full p-4 flex items-start gap-3 text-left"
          >
            <div className={clsx('p-1.5 rounded-lg border shrink-0', config.bg)}>
              <Icon size={14} className={config.color} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={clsx('text-xs font-medium', config.color)}>{config.label}</span>
                <span className="text-xs text-slate-400 dark:text-slate-600">· {step.estimated_minutes} min</span>
              </div>
              <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1 leading-snug">{step.title}</h4>
              <p className="text-xs text-slate-500 leading-relaxed">{step.description}</p>
            </div>
            <ChevronDown
              size={14}
              className={clsx(
                'text-slate-400 shrink-0 mt-1 transition-transform duration-200',
                expanded && 'rotate-180'
              )}
            />
          </button>

          {/* Expanded content */}
          {expanded && (
            <div className="px-4 pb-4 pt-0 border-t border-slate-100 dark:border-slate-800">
              {loadingContent && (
                <div className="flex items-center gap-2 py-6 justify-center text-slate-400 text-xs">
                  <Loader2 size={14} className="animate-spin" />
                  Generating lesson…
                </div>
              )}
              {contentError && !loadingContent && (
                <div className="py-4 text-center">
                  <p className="text-xs text-rose-500 mb-2">{contentError}</p>
                  <button
                    onClick={() => { setContent(null); setContentError(null); handleExpand() }}
                    className="text-xs text-violet-500 hover:underline"
                  >
                    Retry
                  </button>
                </div>
              )}
              {content && !loadingContent && (
                <div className="pt-4">
                  <MarkdownContent content={content} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
