import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { Check, X, Lightbulb, Loader2, Award, RotateCcw, SkipForward } from 'lucide-react'
import { generateQuizSet, getQuizHint, submitQuizAnswer, skipStepQuiz } from '../lib/api'
import type { QuizSet, QuizHint, QuizResult } from '../lib/types'

type Phase = 'loading' | 'active' | 'passed' | 'failed' | 'skipped' | 'error' | 'budget'

interface QuizCardProps {
  concept: string
  context: string
  getToken: () => Promise<string | null>
  journeyId: string
  stepId: string
  // Called once when the user passes (or skips) the quiz — completes the step.
  onPassed?: () => void
}

const DIFFICULTY_COLORS: Record<string, string> = {
  surface:     'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-400/10',
  exploratory: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-400/10',
  deep:        'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10',
  research:    'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-400/10',
}

export default function QuizCard({ concept, context, getToken, journeyId, stepId, onPassed }: QuizCardProps) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [quizSet, setQuizSet] = useState<QuizSet | null>(null)
  const [answers, setAnswers] = useState<string[]>([])
  const [results, setResults] = useState<QuizResult[] | null>(null)
  const [hints, setHints] = useState<Record<number, QuizHint[]>>({})
  const [loadingHint, setLoadingHint] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [confirmingSkip, setConfirmingSkip] = useState(false)
  const [skipping, setSkipping] = useState(false)
  const completedFired = useRef(false)

  const correctCount = results ? results.filter(r => r.is_correct).length : 0

  function fireCompleted() {
    if (!completedFired.current) {
      completedFired.current = true
      onPassed?.()
    }
  }

  async function loadSet() {
    setPhase('loading')
    setQuizSet(null)
    setAnswers([])
    setResults(null)
    setHints({})
    setSubmitError(null)
    setConfirmingSkip(false)
    try {
      const token = await getToken()
      if (!token) return // guests never reach here — StepNode doesn't render the quiz
      const set = await generateQuizSet(
        { concept, context, journey_id: journeyId, step_id: stepId, num_questions: 3 },
        token,
      )
      if (!set.questions.length) { setPhase('error'); return }
      setQuizSet(set)
      setAnswers(set.questions.map(() => ''))
      setPhase('active')
    } catch (e: unknown) {
      setPhase((e as { status?: number })?.status === 402 ? 'budget' : 'error')
    }
  }

  // The quiz is mandatory — it loads as soon as the step content is read.
  useEffect(() => {
    loadSet()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journeyId, stepId])

  async function handleHint(index: number) {
    const question = quizSet?.questions[index]
    if (!question || loadingHint !== null) return
    const used = hints[index]?.length ?? 0
    if (used >= question.hint_available) return
    setLoadingHint(index)
    try {
      const token = await getToken()
      if (!token) return
      const hint = await getQuizHint(question.quiz_id, token)
      setHints(prev => ({ ...prev, [index]: [...(prev[index] ?? []), hint] }))
    } catch {
      // non-critical — hint failure doesn't block anything
    } finally {
      setLoadingHint(null)
    }
  }

  // All answers go in together — one submit for the whole set.
  async function handleSubmitAll() {
    if (!quizSet || submitting) return
    if (answers.some(a => !a.trim())) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const token = await getToken()
      if (!token) return
      const res = await Promise.all(
        quizSet.questions.map((q, i) =>
          submitQuizAnswer(q.quiz_id, { user_answer: answers[i].trim() }, token),
        ),
      )
      setResults(res)
      const correct = res.filter(r => r.is_correct).length
      if (correct >= quizSet.pass_threshold) {
        setPhase('passed')
        fireCompleted()
      } else {
        setPhase('failed')
      }
    } catch {
      // A partial submit leaves some questions consumed server-side, so the
      // safe recovery is a fresh set — not resubmitting this one.
      setSubmitError("Couldn't submit your answers. Grab a fresh quiz and try again.")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSkip() {
    if (skipping) return
    setSkipping(true)
    try {
      const token = await getToken()
      if (!token) return
      await skipStepQuiz(journeyId, stepId, token)
      setPhase('skipped')
      fireCompleted()
    } catch {
      setConfirmingSkip(false)
      setSubmitError("Couldn't skip the quiz — try again.")
    } finally {
      setSkipping(false)
    }
  }

  const skipControl = confirmingSkip ? (
    <div className="rounded-lg border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3 py-2.5 space-y-2">
      <p className="text-xs text-amber-800 dark:text-amber-300 font-medium">
        Skip this quiz? You'll finish the step without testing what you learned.
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={handleSkip}
          disabled={skipping}
          className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 min-h-[44px] rounded-lg font-semibold bg-amber-600 text-white hover:bg-amber-700 active:bg-amber-700 transition-colors disabled:opacity-50"
        >
          {skipping ? <Loader2 size={11} className="animate-spin" /> : <SkipForward size={11} />}
          Skip anyway
        </button>
        <button
          onClick={() => setConfirmingSkip(false)}
          className="inline-flex items-center text-xs px-2.5 py-1.5 min-h-[44px] rounded-lg border border-amber-300 dark:border-amber-500/40 text-amber-800 dark:text-amber-300 hover:bg-amber-100 active:bg-amber-100 dark:hover:bg-amber-500/20 dark:active:bg-amber-500/20 transition-colors"
        >
          Keep going
        </button>
      </div>
    </div>
  ) : (
    <button
      onClick={() => setConfirmingSkip(true)}
      className="inline-flex items-center gap-1 text-xs min-h-[44px] px-1 text-slate-400 hover:text-slate-600 active:text-slate-600 dark:hover:text-slate-300 dark:active:text-slate-300 transition-colors"
    >
      <SkipForward size={11} />
      Skip quiz
    </button>
  )

  if (phase === 'loading') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Loader2 size={12} className="animate-spin" />
          Preparing your quiz…
        </div>
      </div>
    )
  }

  if (phase === 'budget') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 text-center space-y-2">
        <p className="text-xs text-slate-600 dark:text-slate-400">
          The quiz needs AI budget you've used up for this period.
        </p>
        <Link to="/pricing" className="text-xs text-violet-600 dark:text-violet-400 hover:underline font-medium">
          Upgrade or apply a promo code →
        </Link>
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 text-center space-y-2">
        <p className="text-xs text-rose-500">Couldn't load the quiz for this step.</p>
        <div className="flex items-center justify-center gap-4">
          <button onClick={loadSet} className="text-xs text-violet-500 hover:underline">
            Try again
          </button>
          {skipControl}
        </div>
      </div>
    )
  }

  if (phase === 'skipped') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
        <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-3 text-center">
          <p className="flex items-center justify-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400">
            <SkipForward size={13} />
            Quiz skipped — step complete.
          </p>
        </div>
      </div>
    )
  }

  if (phase === 'active' && quizSet) {
    const allAnswered = answers.every(a => a.trim())
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {quizSet.questions.length} questions · {quizSet.pass_threshold} correct to pass
          </p>
          {!confirmingSkip && skipControl}
        </div>
        {confirmingSkip && skipControl}

        {quizSet.questions.map((q, i) => {
          const qHints = hints[i] ?? []
          const hintsRemaining = q.hint_available - qHints.length
          return (
            <div key={q.quiz_id} className="space-y-2">
              <div className="flex items-start justify-between gap-3">
                <p className="text-xs font-semibold text-slate-400">Question {i + 1}</p>
                <span className={clsx(
                  'text-xs font-semibold px-1.5 py-0.5 rounded shrink-0',
                  DIFFICULTY_COLORS[q.difficulty] ?? DIFFICULTY_COLORS.exploratory
                )}>
                  {q.difficulty}
                </span>
              </div>
              {q.intro_phrase && (
                <p className="text-xs text-slate-400 dark:text-slate-500 italic">{q.intro_phrase}</p>
              )}
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200 leading-snug">
                {q.question}
              </p>

              {qHints.length > 0 && (
                <div className="space-y-1.5">
                  {qHints.map(h => (
                    <div key={h.hint_num} className="flex gap-2 text-xs">
                      <span className="text-violet-400 font-semibold shrink-0">Hint {h.hint_num}</span>
                      <span className="text-slate-600 dark:text-slate-400">{h.hint_text}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  value={answers[i] ?? ''}
                  onChange={e => setAnswers(prev => prev.map((a, j) => (j === i ? e.target.value : a)))}
                  placeholder="Your answer…"
                  className={clsx(
                    'flex-1 text-sm px-3 py-2 rounded-lg border transition-colors',
                    'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                    'border-slate-200 dark:border-slate-700',
                    'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                    'placeholder:text-slate-300 dark:placeholder:text-slate-600',
                  )}
                />
                <button
                  onClick={() => handleHint(i)}
                  disabled={hintsRemaining <= 0 || loadingHint !== null}
                  title={hintsRemaining > 0 ? `Hint (${hintsRemaining} left)` : 'No hints left'}
                  className={clsx(
                    'inline-flex items-center gap-1 text-xs px-2.5 min-h-[44px] rounded-lg border transition-colors shrink-0',
                    'border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400',
                    'hover:bg-slate-50 active:bg-slate-50 dark:hover:bg-slate-800 dark:active:bg-slate-800',
                    'disabled:opacity-40 disabled:cursor-not-allowed',
                  )}
                >
                  {loadingHint === i ? <Loader2 size={11} className="animate-spin" /> : <Lightbulb size={11} />}
                  {hintsRemaining}
                </button>
              </div>
            </div>
          )
        })}

        <button
          onClick={handleSubmitAll}
          disabled={!allAnswered || submitting}
          className={clsx(
            'w-full flex items-center justify-center gap-1.5 text-xs px-3 py-2.5 min-h-[44px] rounded-lg font-semibold transition-colors',
            'bg-violet-600 text-white hover:bg-violet-700 active:bg-violet-700',
            'disabled:opacity-40 disabled:cursor-not-allowed',
          )}
        >
          {submitting ? <Loader2 size={12} className="animate-spin" /> : null}
          {submitting ? 'Checking…' : allAnswered ? 'Submit all answers' : 'Answer every question to submit'}
        </button>

        {submitError && (
          <div className="text-center space-y-1">
            <p className="text-xs text-rose-500">{submitError}</p>
            <button onClick={loadSet} className="text-xs text-violet-500 hover:underline">
              Get a fresh quiz
            </button>
          </div>
        )}
      </div>
    )
  }

  if ((phase === 'passed' || phase === 'failed') && quizSet && results) {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
        {phase === 'passed' ? (
          <div className="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 px-3 py-3 text-center space-y-1">
            <p className="flex items-center justify-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <Award size={13} />
              Quiz passed — {correctCount}/{quizSet.questions.length} correct
            </p>
            <p className="text-xs text-emerald-700/70 dark:text-emerald-400/70">
              Step complete. The next step is unlocked.
            </p>
          </div>
        ) : (
          <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-3 text-center space-y-2">
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              {correctCount}/{quizSet.questions.length} correct — you need {quizSet.pass_threshold} to finish this step.
            </p>
            <p className="text-xs text-slate-500">Review the answers below, then try a fresh set — or skip.</p>
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={loadSet}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 min-h-[44px] rounded-lg font-semibold bg-violet-600 text-white hover:bg-violet-700 active:bg-violet-700 transition-colors"
              >
                <RotateCcw size={11} />
                Retry quiz
              </button>
              {skipControl}
            </div>
          </div>
        )}

        {/* Per-question review */}
        <div className="space-y-3">
          {quizSet.questions.map((q, i) => {
            const r = results[i]
            if (!r) return null
            return (
              <div key={q.quiz_id} className="rounded-lg border border-slate-100 dark:border-slate-800 p-3 space-y-1.5">
                <div className="flex items-start gap-2">
                  {r.is_correct
                    ? <Check size={13} className="text-emerald-500 mt-0.5 shrink-0" />
                    : <X size={13} className="text-rose-400 mt-0.5 shrink-0" />}
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-300 leading-snug">{q.question}</p>
                </div>
                {!r.is_correct && (
                  <p className="text-xs text-slate-700 dark:text-slate-300 pl-5">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400 mr-1">Answer</span>
                    {r.correct_answer}
                  </p>
                )}
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed pl-5">{r.answer_explanation}</p>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return null
}
