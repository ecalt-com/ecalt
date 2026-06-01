import { useState, useRef } from 'react'
import clsx from 'clsx'
import { Check, X, Lightbulb, Loader2, ChevronRight } from 'lucide-react'
import { generateQuiz, getQuizHint, submitQuizAnswer } from '../lib/api'
import type { QuizQuestion, QuizHint, QuizResult } from '../lib/types'

type Phase = 'trigger' | 'loading' | 'question' | 'submitted'

interface QuizCardProps {
  concept: string
  context: string
  getToken: () => Promise<string | null>
}

const DIFFICULTY_COLORS: Record<string, string> = {
  surface:     'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-400/10',
  exploratory: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-400/10',
  deep:        'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10',
  research:    'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-400/10',
}

export default function QuizCard({ concept, context, getToken }: QuizCardProps) {
  const [phase, setPhase] = useState<Phase>('trigger')
  const [quiz, setQuiz] = useState<QuizQuestion | null>(null)
  const [hints, setHints] = useState<QuizHint[]>([])
  const [loadingHint, setLoadingHint] = useState(false)
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<QuizResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const hintsUsed = hints.length
  const hintsRemaining = quiz ? quiz.hint_available - hintsUsed : 3

  async function handleStart() {
    setPhase('loading')
    setError(null)
    try {
      const token = await getToken()
      if (!token) { setPhase('trigger'); return }
      const q = await generateQuiz({ concept, context, base_depth: 'exploratory' }, token)
      setQuiz(q)
      setPhase('question')
      setTimeout(() => inputRef.current?.focus(), 50)
    } catch {
      setError('Could not generate a question. Try again.')
      setPhase('trigger')
    }
  }

  async function handleHint() {
    if (!quiz || hintsRemaining <= 0 || loadingHint) return
    setLoadingHint(true)
    try {
      const token = await getToken()
      if (!token) return
      const hint = await getQuizHint(quiz.quiz_id, token)
      setHints(prev => [...prev, hint])
    } catch {
      // non-critical — hint failure doesn't block anything
    } finally {
      setLoadingHint(false)
    }
  }

  async function handleSubmit() {
    if (!quiz || !answer.trim() || submitting) return
    setSubmitting(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await submitQuizAnswer(quiz.quiz_id, { user_answer: answer.trim() }, token)
      setResult(res)
      setPhase('submitted')
    } catch {
      setError('Could not submit. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  if (phase === 'trigger') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
        <button
          onClick={handleStart}
          className="flex items-center gap-1.5 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 font-medium transition-colors group"
        >
          <Lightbulb size={12} className="group-hover:scale-110 transition-transform" />
          Something to pause on
          <ChevronRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
        </button>
        {error && <p className="mt-1 text-[10px] text-rose-500">{error}</p>}
      </div>
    )
  }

  if (phase === 'loading') {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Loader2 size={12} className="animate-spin" />
          One moment…
        </div>
      </div>
    )
  }

  if (phase === 'question' && quiz) {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
        {/* Intro + difficulty */}
        <div className="flex items-start justify-between gap-3">
          <p className="text-[11px] text-slate-400 dark:text-slate-500 italic">{quiz.intro_phrase}</p>
          <span className={clsx(
            'text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0',
            DIFFICULTY_COLORS[quiz.difficulty] ?? DIFFICULTY_COLORS.exploratory
          )}>
            {quiz.difficulty}
          </span>
        </div>

        {/* Question */}
        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 leading-snug">
          {quiz.question}
        </p>

        {/* Hints revealed */}
        {hints.length > 0 && (
          <div className="space-y-1.5">
            {hints.map(h => (
              <div key={h.hint_num} className="flex gap-2 text-xs">
                <span className="text-violet-400 font-semibold shrink-0">Hint {h.hint_num}</span>
                <span className="text-slate-600 dark:text-slate-400">{h.hint_text}</span>
              </div>
            ))}
          </div>
        )}

        {/* Answer input */}
        <input
          ref={inputRef}
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Your answer…"
          className={clsx(
            'w-full text-sm px-3 py-2 rounded-lg border transition-colors',
            'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200',
            'border-slate-200 dark:border-slate-700',
            'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
            'placeholder:text-slate-300 dark:placeholder:text-slate-600',
          )}
        />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleHint}
            disabled={hintsRemaining <= 0 || loadingHint}
            className={clsx(
              'flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border transition-colors',
              'border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400',
              'hover:bg-slate-50 dark:hover:bg-slate-800',
              'disabled:opacity-40 disabled:cursor-not-allowed',
            )}
          >
            {loadingHint ? <Loader2 size={11} className="animate-spin" /> : <Lightbulb size={11} />}
            {hintsRemaining > 0 ? `Hint (${hintsRemaining} left)` : 'No hints left'}
          </button>

          <button
            onClick={handleSubmit}
            disabled={!answer.trim() || submitting}
            className={clsx(
              'ml-auto flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg font-semibold transition-colors',
              'bg-violet-600 text-white hover:bg-violet-700',
              'disabled:opacity-40 disabled:cursor-not-allowed',
            )}
          >
            {submitting ? <Loader2 size={11} className="animate-spin" /> : null}
            {submitting ? 'Checking…' : 'Submit'}
          </button>
        </div>

        {error && <p className="text-[10px] text-rose-500">{error}</p>}
      </div>
    )
  }

  if (phase === 'submitted' && result) {
    return (
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
        {/* Correct / incorrect banner */}
        <div className={clsx(
          'flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-lg',
          result.is_correct
            ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400'
        )}>
          {result.is_correct
            ? <><Check size={13} /> You saw it independently.</>
            : <><X size={13} /> The answer is below — here's why it works.</>
          }
        </div>

        {/* Correct answer */}
        {!result.is_correct && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-0.5">Answer</p>
            <p className="text-sm text-slate-700 dark:text-slate-300 font-medium">{result.correct_answer}</p>
          </div>
        )}

        {/* Explanation */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-0.5">Why</p>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{result.answer_explanation}</p>
        </div>

        {/* Stats */}
        <p className="text-[10px] text-slate-400 dark:text-slate-600">
          {result.hints_used === 0 ? 'No hints used.' : `${result.hints_used} hint${result.hints_used > 1 ? 's' : ''} used.`}
          {' '}Depth: {result.difficulty}.
        </p>
      </div>
    )
  }

  return null
}
