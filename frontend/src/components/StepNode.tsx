import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { BookOpen, Wrench, Zap, Compass, Check, ChevronDown, Loader2, Lock } from 'lucide-react'
import type { JourneyStep, StepVisualResponse } from '../lib/types'
import { getStepContent, getStepVisual } from '../lib/api'
import MarkdownContent from './MarkdownContent'
import QuizCard from './QuizCard'
import StepFeedbackBar from './StepFeedbackBar'
import StepUpgradePanel from './StepUpgradePanel'
import VisualLearningObject from './visual/VisualLearningObject'

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
  // Controlled expansion — when provided, the parent owns open/closed state
  // (e.g. so a "Start Journey" button can open a step). Omit both for the
  // original self-managed behaviour.
  expanded?: boolean
  onExpandToggle?: (id: string) => void
  // Sequential gating: a locked step can't be expanded or completed until the
  // previous step is done.
  locked?: boolean
}

export default function StepNode({ step, index, isLast, journeyId, getToken, onToggle, expanded: controlledExpanded, onExpandToggle, locked = false }: StepNodeProps) {
  const config = typeConfig[step.type]
  const Icon = config.icon
  const [internalExpanded, setInternalExpanded] = useState(false)
  const expanded = controlledExpanded ?? internalExpanded
  const headerRef = useRef<HTMLButtonElement>(null)
  const prevExpanded = useRef(false)

  // Scroll the step header into view when the step is opened, but only if it
  // isn't already visible. requestAnimationFrame runs after React paints so the
  // header has its real position. We target the HEADER button (not the whole
  // container) so async quiz content loading below never affects the target.
  useLayoutEffect(() => {
    if (expanded && !prevExpanded.current && !locked) {
      requestAnimationFrame(() => {
        const el = headerRef.current
        if (!el) return
        const rect = el.getBoundingClientRect()
        const navHeight = 80
        if (rect.top < navHeight || rect.top > window.innerHeight - 80) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      })
    }
    prevExpanded.current = expanded
  }, [expanded, locked])
  const [content, setContent] = useState<string | null>(null)
  const [visual, setVisual] = useState<StepVisualResponse | null>(null)
  const [loadingContent, setLoadingContent] = useState(false)
  const [contentError, setContentError] = useState<string | null>(null)
  const [budgetExceeded, setBudgetExceeded] = useState(false)
  const [isGuest, setIsGuest] = useState(false)
  // Whether the quiz is required for this visit: steps completed before this
  // session never re-quiz, and a step stays mounted through its pass screen.
  const quizRequired = useRef(!step.completed)

  const handleExpand = () => {
    if (locked) return
    if (onExpandToggle) onExpandToggle(step.id)
    else setInternalExpanded(prev => !prev)
  }

  const loadContent = async () => {
    setLoadingContent(true)
    setContentError(null)
    try {
      const token = await getToken()
      const res = await getStepContent(journeyId, step.id, token ?? undefined)
      setContent(res.content)
      // Best-effort, non-blocking — a visual is a bonus, never a requirement
      // for the lesson to render (VISUAL_INTELLIGENCE_ENABLED is off by
      // default server-side, so this normally just returns "pending").
      getStepVisual(journeyId, step.id, token ?? undefined).then(setVisual).catch(() => {})
      if (!token) {
        // Guests can't take quizzes (auth required) — for them, viewing the
        // content still completes the step locally. Signed-in users complete
        // a step by passing its quiz instead.
        setIsGuest(true)
        if (!step.completed) onToggle?.(step.id)
      }
    } catch (e: any) {
      if (e?.status === 402) {
        setBudgetExceeded(true)
      } else {
        setContentError('Could not load lesson content. Try again.')
      }
    } finally {
      setLoadingContent(false)
    }
  }

  // Fetch on first expansion, whether triggered by a click here or by the
  // parent (Start Journey / Continue). Errors don't refetch automatically —
  // the Retry button below drives that explicitly.
  useEffect(() => {
    if (expanded && !locked && content === null && !loadingContent && !budgetExceeded) {
      loadContent()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded])

  return (
    <div id={`step-${step.id}`} className="flex gap-3 sm:gap-4 scroll-mt-24">
      <div className="flex flex-col items-center">
        {/* Status indicator — completion happens through the step flow, not by clicking here */}
        <div
          className={clsx(
            'w-10 h-10 rounded-full border-2 flex items-center justify-center shrink-0 transition-all duration-200',
            step.completed
              ? 'bg-violet-600 border-violet-600 text-white'
              : locked
                ? 'border-slate-200 bg-slate-50 text-slate-300 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-700'
                : 'border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500'
          )}
        >
          {step.completed ? <Check size={16} /> : locked ? <Lock size={13} /> : <span className="text-xs font-bold">{index + 1}</span>}
        </div>
        {!isLast && <div className="step-connector flex-1 my-1" />}
      </div>

      <div className={clsx('pb-8 flex-1', isLast && 'pb-0')}>
        <div
          className={clsx(
            'glass-card rounded-xl transition-all duration-200',
            locked
              ? 'opacity-60'
              : expanded ? 'border-violet-200 dark:border-violet-500/30' : 'hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer'
          )}
        >
          {/* Header row */}
          <button
            ref={headerRef}
            onClick={handleExpand}
            disabled={locked}
            className={clsx(
              'w-full p-4 flex items-start gap-3 text-left scroll-mt-24',
              locked ? 'cursor-not-allowed' : 'active:bg-slate-50 dark:active:bg-slate-800/60',
            )}
          >
            <div className={clsx('p-1.5 rounded-lg border shrink-0', config.bg)}>
              <Icon size={14} className={config.color} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={clsx('text-xs font-medium', config.color)}>{config.label}</span>
                <span className="text-xs text-slate-400 dark:text-slate-600">· {step.estimated_minutes} min</span>
                {!step.completed && (
                  <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-violet-50 dark:bg-violet-400/10 text-violet-600 dark:text-violet-400">
                    Quiz · 2/3 to pass
                  </span>
                )}
              </div>
              <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1 leading-snug">{step.title}</h4>
              <p className="text-xs text-slate-500 leading-relaxed">{step.description}</p>
              {locked && (
                <p className="text-xs text-slate-400 dark:text-slate-600 mt-1.5 flex items-center gap-1">
                  <Lock size={10} />Complete the previous step to unlock
                </p>
              )}
            </div>
            {locked ? (
              <Lock size={14} className="text-slate-300 dark:text-slate-700 shrink-0 mt-1" />
            ) : (
              <ChevronDown
                size={14}
                className={clsx(
                  'text-slate-400 shrink-0 mt-1 transition-transform duration-200',
                  expanded && 'rotate-180'
                )}
              />
            )}
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
              {budgetExceeded && !loadingContent && (
                <StepUpgradePanel />
              )}
              {contentError && !loadingContent && !budgetExceeded && (
                <div className="py-4 text-center">
                  <p className="text-xs text-rose-500 mb-2">{contentError}</p>
                  <button
                    onClick={() => { setContent(null); setContentError(null); loadContent() }}
                    className="text-xs text-violet-500 hover:underline"
                  >
                    Retry
                  </button>
                </div>
              )}
              {content && !loadingContent && (
                <div className="pt-4">
                  <MarkdownContent content={content} />
                  {visual?.status === 'ready' && (
                    <div className="mt-4">
                      <VisualLearningObject
                        journeyId={journeyId}
                        stepId={step.id}
                        stepVisual={visual}
                        getToken={getToken}
                      />
                    </div>
                  )}
                  {!isGuest && (
                    <StepFeedbackBar
                      journeyId={journeyId}
                      stepId={step.id}
                      getToken={getToken}
                      onRegenerated={setContent}
                    />
                  )}
                  {!isGuest && quizRequired.current && (
                    <QuizCard
                      concept={step.title}
                      context={content}
                      getToken={getToken}
                      journeyId={journeyId}
                      stepId={step.id}
                      onPassed={() => onToggle?.(step.id)}
                    />
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
