import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Loader2, RotateCcw, XCircle } from 'lucide-react'
import Navigation from '../components/Navigation'
import { useAuth } from '../lib/AuthContext'
import {
  answerReviewItem, getReviewToday, startReviewItem,
  type ReviewItem,
} from '../lib/api'
import type { QuizQuestion, QuizResult } from '../lib/types'
import { usePageTitle } from '../lib/usePageTitle'

type Graded = QuizResult & { box: number; next_review_in_days: number }
type Phase = 'loading' | 'question' | 'feedback' | 'done' | 'error'

const dayLabel = (n: number) => (n === 1 ? 'tomorrow' : `in ${n} days`)

// Today's review (F1.3): a few questions from steps the learner already finished,
// spaced further apart each time they get one right.
export default function Review() {
  usePageTitle("Today's review")
  const navigate = useNavigate()
  const { user, loading: authLoading, getToken } = useAuth()
  const [phase, setPhase] = useState<Phase>('loading')
  const [items, setItems] = useState<ReviewItem[]>([])
  const [index, setIndex] = useState(0)
  const [question, setQuestion] = useState<QuizQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [graded, setGraded] = useState<Graded | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [correct, setCorrect] = useState(0)
  const [skipped, setSkipped] = useState(0)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  // Open item i, skipping any whose stored questions are gone.
  const openItem = useCallback(async (list: ReviewItem[], i: number) => {
    const token = await getToken()
    if (!token) return
    for (let n = i; n < list.length; n++) {
      try {
        const q = await startReviewItem(list[n].item_id, token)
        setIndex(n); setQuestion(q); setAnswer(''); setGraded(null); setPhase('question')
        return
      } catch (e) {
        if ((e as { status?: number })?.status !== 404) { setPhase('error'); return }
        setSkipped(s => s + 1)
      }
    }
    setPhase('done')
  }, [getToken])

  useEffect(() => {
    if (authLoading || !user) return
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const today = await getReviewToday(token)
        setItems(today.items)
        if (today.items.length === 0) { setPhase('done'); return }
        await openItem(today.items, 0)
      } catch { setPhase('error') }
    })()
  }, [authLoading, user, getToken, openItem])

  const submit = async () => {
    if (!question || !answer.trim() || submitting) return
    setSubmitting(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await answerReviewItem(items[index].item_id, { quiz_id: question.quiz_id, user_answer: answer.trim() }, token)
      setGraded(res)
      if (res.is_correct) setCorrect(c => c + 1)
      setPhase('feedback')
    } catch { setPhase('error') }
    finally { setSubmitting(false) }
  }

  const next = () => (index + 1 < items.length ? openItem(items, index + 1) : setPhase('done'))
  const item = items[index]
  const answered = Math.max(0, index + (phase === 'feedback' ? 1 : 0) - skipped)

  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-xl mx-auto" data-testid="review-page">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1">Today's review</h1>
          <p className="text-sm text-slate-500 mb-6">A few questions from what you've already learned. Getting one right moves it further out.</p>

          {phase === 'loading' && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>}

          {phase === 'error' && (
            <div className="glass-card rounded-2xl p-6 text-center space-y-3">
              <p className="text-sm text-rose-600 dark:text-rose-400">Couldn't load your review. Please try again.</p>
              <button onClick={() => window.location.reload()} className="text-xs text-violet-500 hover:underline inline-flex items-center gap-1">
                <RotateCcw size={11} /> Retry
              </button>
            </div>
          )}

          {(phase === 'question' || phase === 'feedback') && question && item && (
            <div className="glass-card rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Question {Math.min(index + 1, items.length)} of {items.length}</span>
                <span className="truncate ml-3">{item.journey_title ?? item.concept}</span>
              </div>
              {question.intro_phrase && <p className="text-xs text-violet-600 dark:text-violet-400">{question.intro_phrase}</p>}
              <p className="text-base font-medium text-slate-800 dark:text-slate-100 leading-snug" data-testid="review-question">{question.question}</p>

              {phase === 'question' && (
                <>
                  <textarea
                    value={answer}
                    onChange={e => setAnswer(e.target.value)}
                    rows={3}
                    aria-label="Your answer"
                    placeholder="Answer in your own words…"
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                  />
                  <button onClick={submit} disabled={!answer.trim() || submitting}
                    className="btn-primary w-full min-h-[44px] disabled:opacity-60 inline-flex items-center justify-center gap-2">
                    {submitting && <Loader2 size={14} className="animate-spin" />} Check my answer
                  </button>
                </>
              )}

              {phase === 'feedback' && graded && (
                <div className="space-y-3" data-testid="review-feedback">
                  <div className="flex items-start gap-2">
                    {graded.is_correct
                      ? <CheckCircle2 size={18} className="text-emerald-500 shrink-0 mt-0.5" />
                      : <XCircle size={18} className="text-rose-500 shrink-0 mt-0.5" />}
                    <p className="text-sm text-slate-700 dark:text-slate-200">{graded.feedback}</p>
                  </div>
                  {!graded.is_correct && (
                    <p className="text-sm text-slate-600 dark:text-slate-300"><span className="font-semibold">Answer:</span> {graded.correct_answer}</p>
                  )}
                  {graded.explanation && <p className="text-xs text-slate-500 leading-relaxed">{graded.explanation}</p>}
                  <p className="text-xs text-slate-400">You'll see this again {dayLabel(graded.next_review_in_days)}.</p>
                  <button onClick={next} className="btn-primary w-full min-h-[44px] inline-flex items-center justify-center gap-2">
                    {index + 1 < items.length ? 'Next question' : 'Finish'} <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>
          )}

          {phase === 'done' && (
            <div className="glass-card rounded-2xl p-8 text-center space-y-3" data-testid="review-done">
              <CheckCircle2 size={32} className="mx-auto text-emerald-500" />
              {answered > 0 ? (
                <p className="text-base font-semibold text-slate-800 dark:text-slate-100">
                  {correct} of {answered} right. Nice work — that counts toward your streak.
                </p>
              ) : (
                <p className="text-base font-semibold text-slate-800 dark:text-slate-100">Nothing to review right now.</p>
              )}
              <p className="text-sm text-slate-500">Finish a step and it joins your review automatically.</p>
              <Link to="/journeys" className="inline-block text-sm text-violet-600 dark:text-violet-400 hover:underline">Keep learning →</Link>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
