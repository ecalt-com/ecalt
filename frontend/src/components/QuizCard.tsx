import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { Lightbulb, Loader2, Award, RotateCcw, SkipForward } from 'lucide-react'
import { generateQuizSet, getQuizHint, submitQuizAnswer, skipStepQuiz } from '../lib/api'
import type { QuizSet, QuizHint, QuizResult, QuizVerdict } from '../lib/types'

// ── 3-tier verdict display config ────────────────────────────────────────────
const VERDICT_CONFIG: Record<QuizVerdict, { icon: string; label: string; cardCls: string; textCls: string }> = {
  excellent: {
    icon: '✦',
    label: 'Spot on!',
    cardCls: 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/60 dark:bg-emerald-500/10',
    textCls: 'text-emerald-700 dark:text-emerald-300',
  },
  on_track: {
    icon: '→',
    label: 'Right direction',
    cardCls: 'border-amber-200 dark:border-amber-500/30 bg-amber-50/60 dark:bg-amber-500/10',
    textCls: 'text-amber-700 dark:text-amber-300',
  },
  off_track: {
    icon: '◎',
    label: "Let's build on that",
    cardCls: 'border-violet-200 dark:border-violet-500/30 bg-violet-50/60 dark:bg-violet-500/10',
    textCls: 'text-violet-700 dark:text-violet-300',
  },
}

function getVerdict(r: QuizResult): QuizVerdict {
  if (r.verdict) return r.verdict
  return r.is_correct ? 'excellent' : 'off_track'
}

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
  // Mobile bottom-sheet: which question is being answered (-1 = none)
  const [activeSheetIdx, setActiveSheetIdx] = useState<number | null>(null)
  const sheetTextareaRef = useRef<HTMLTextAreaElement>(null)

  const correctCount = results ? results.filter(r => r.is_correct).length : 0

  const resizeTextarea = useCallback((el: HTMLTextAreaElement | null) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [])

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
    setActiveSheetIdx(null)
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

              {/* Mobile: tap-to-answer button that opens bottom sheet */}
              <button
                onClick={() => setActiveSheetIdx(i)}
                className={clsx(
                  'sm:hidden w-full text-left text-sm px-3 py-2.5 rounded-lg border min-h-[44px] transition-colors',
                  answers[i]?.trim()
                    ? 'text-slate-800 dark:text-slate-200 border-violet-300 dark:border-violet-600 bg-violet-50/50 dark:bg-violet-500/10'
                    : 'text-slate-400 dark:text-slate-600 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900',
                )}
              >
                {answers[i]?.trim() || 'Tap to answer…'}
              </button>

              {/* Desktop: inline textarea + hint */}
              <div className="hidden sm:flex items-start gap-2">
                <textarea
                  rows={2}
                  value={answers[i] ?? ''}
                  onChange={e => {
                    setAnswers(prev => prev.map((a, j) => (j === i ? e.target.value : a)))
                    resizeTextarea(e.target)
                  }}
                  placeholder="Your answer…"
                  className={clsx(
                    'flex-1 text-sm px-3 py-2 rounded-lg border transition-colors resize-none overflow-hidden',
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

        {/* Mobile bottom sheet for answering */}
        {activeSheetIdx !== null && (() => {
          const si = activeSheetIdx
          const sq = quizSet.questions[si]
          const sHints = hints[si] ?? []
          const sHintsRemaining = sq.hint_available - sHints.length
          return (
            <div className="sm:hidden fixed inset-0 z-50 flex flex-col justify-end">
              {/* Backdrop */}
              <div
                className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
                onClick={() => setActiveSheetIdx(null)}
              />
              {/* Sheet */}
              <div className="relative bg-white dark:bg-slate-900 rounded-t-2xl shadow-2xl flex flex-col max-h-[78vh]">
                {/* Handle */}
                <div className="flex justify-center pt-3 pb-1 shrink-0">
                  <div className="w-10 h-1 rounded-full bg-slate-200 dark:bg-slate-700" />
                </div>

                {/* Scrollable question + hints area */}
                <div className="overflow-y-auto flex-1 px-4 py-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-slate-400">Question {si + 1}</p>
                    <span className={clsx(
                      'text-xs font-semibold px-1.5 py-0.5 rounded shrink-0',
                      DIFFICULTY_COLORS[sq.difficulty] ?? DIFFICULTY_COLORS.exploratory
                    )}>
                      {sq.difficulty}
                    </span>
                  </div>
                  {sq.intro_phrase && (
                    <p className="text-xs text-slate-400 dark:text-slate-500 italic">{sq.intro_phrase}</p>
                  )}
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200 leading-snug">
                    {sq.question}
                  </p>
                  {sHints.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      {sHints.map(h => (
                        <div key={h.hint_num} className="flex gap-2 text-xs">
                          <span className="text-violet-400 font-semibold shrink-0">Hint {h.hint_num}</span>
                          <span className="text-slate-600 dark:text-slate-400">{h.hint_text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Fixed answer area above keyboard */}
                <div className="shrink-0 px-4 pt-3 pb-8 border-t border-slate-100 dark:border-slate-800 space-y-3">
                  <div className="flex items-start gap-2">
                    <textarea
                      ref={sheetTextareaRef}
                      autoFocus
                      rows={3}
                      value={answers[si] ?? ''}
                      onChange={e => {
                        setAnswers(prev => prev.map((a, j) => (j === si ? e.target.value : a)))
                        resizeTextarea(e.target)
                      }}
                      placeholder="Your answer…"
                      className={clsx(
                        'flex-1 text-sm px-3 py-2 rounded-lg border transition-colors resize-none overflow-hidden',
                        'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                        'border-slate-200 dark:border-slate-700',
                        'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                        'placeholder:text-slate-300 dark:placeholder:text-slate-600',
                      )}
                    />
                    <button
                      onClick={() => handleHint(si)}
                      disabled={sHintsRemaining <= 0 || loadingHint !== null}
                      title={sHintsRemaining > 0 ? `Hint (${sHintsRemaining} left)` : 'No hints left'}
                      className={clsx(
                        'inline-flex items-center gap-1 text-xs px-2.5 min-h-[44px] rounded-lg border transition-colors shrink-0',
                        'border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400',
                        'hover:bg-slate-50 active:bg-slate-50 dark:hover:bg-slate-800 dark:active:bg-slate-800',
                        'disabled:opacity-40 disabled:cursor-not-allowed',
                      )}
                    >
                      {loadingHint === si ? <Loader2 size={11} className="animate-spin" /> : <Lightbulb size={11} />}
                      {sHintsRemaining}
                    </button>
                  </div>
                  <button
                    onClick={() => setActiveSheetIdx(null)}
                    className="w-full flex items-center justify-center text-sm py-2.5 min-h-[44px] rounded-lg font-semibold bg-violet-600 text-white hover:bg-violet-700 active:bg-violet-700 transition-colors"
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          )
        })()}

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
    const excellentCount = results.filter(r => getVerdict(r) === 'excellent').length
    const onTrackCount   = results.filter(r => getVerdict(r) === 'on_track').length
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
        {phase === 'passed' ? (
          <div className="rounded-lg bg-emerald-50 dark:bg-emerald-500/10 px-3 py-3 text-center space-y-1">
            <p className="flex items-center justify-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <Award size={13} />
              {excellentCount === quizSet.questions.length
                ? `Flawless — ${correctCount}/${quizSet.questions.length} spot on!`
                : onTrackCount > 0
                  ? `Step complete — ${excellentCount} excellent, ${onTrackCount} on the right track`
                  : `Quiz passed — ${correctCount}/${quizSet.questions.length} correct`}
            </p>
            <p className="text-xs text-emerald-700/70 dark:text-emerald-400/70">
              Step complete. The next step is unlocked.
            </p>
          </div>
        ) : (
          <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-3 text-center space-y-2">
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              {correctCount}/{quizSet.questions.length} correct — you need {quizSet.pass_threshold} to move on.
            </p>
            <p className="text-xs text-slate-500">Review the feedback below, then try a fresh set — or skip.</p>
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
            const verdict  = getVerdict(r)
            const vcfg     = VERDICT_CONFIG[verdict]
            return (
              <div
                key={q.quiz_id}
                className={clsx('rounded-lg border p-3 space-y-2', vcfg.cardCls)}
              >
                {/* Question */}
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 leading-snug">{q.question}</p>

                {/* Verdict badge + personalised feedback */}
                <div className={clsx('rounded-md px-3 py-2 space-y-1')}>
                  <p className={clsx('text-xs font-semibold', vcfg.textCls)}>
                    {vcfg.icon} {vcfg.label}
                  </p>
                  {r.feedback && (
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      {r.feedback}
                    </p>
                  )}
                  {r.missed && verdict !== 'excellent' && (
                    <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed mt-1 italic">
                      Worth noting: {r.missed}
                    </p>
                  )}
                </div>

                {/* User's answer */}
                <div className="space-y-0.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Your answer</p>
                  <p className={clsx('text-xs leading-relaxed', vcfg.textCls)}>{r.user_answer}</p>
                </div>

                {/* Explanation — always shown */}
                <div className="space-y-0.5 border-t border-slate-100 dark:border-slate-700/40 pt-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Explanation</p>
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                    {r.explanation || r.correct_answer}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return null
}
