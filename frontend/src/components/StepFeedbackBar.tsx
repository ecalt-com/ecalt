import { useState } from 'react'
import clsx from 'clsx'
import { ThumbsUp, ThumbsDown, RefreshCw, Loader2, Check } from 'lucide-react'
import { submitStepFeedback, regenerateStepContent, type StepFeedbackTag } from '../lib/api'
import { useToast } from '../lib/ToastContext'

const DOWN_TAGS: { tag: StepFeedbackTag; label: string }[] = [
  { tag: 'too_generic',  label: 'Too generic' },
  { tag: 'too_basic',    label: 'Too basic' },
  { tag: 'too_advanced', label: 'Too advanced' },
  { tag: 'inaccurate',   label: "Something's off" },
]

interface StepFeedbackBarProps {
  journeyId: string
  stepId: string
  getToken: () => Promise<string | null>
  // Called with the fresh content after an explicit regenerate completes.
  onRegenerated: (content: string) => void
}

/**
 * Thumbs + tag feedback for a step's lesson content, plus a "Fresh take"
 * regenerate action. Negative tags trigger a background rewrite server-side;
 * the regenerate button rewrites synchronously and swaps the content in place.
 */
export default function StepFeedbackBar({ journeyId, stepId, getToken, onRegenerated }: StepFeedbackBarProps) {
  const { addToast } = useToast()
  const [rating, setRating] = useState<'up' | 'down' | null>(null)
  const [showTags, setShowTags] = useState(false)
  const [tagSent, setTagSent] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  const send = async (body: { rating: 'up' | 'down'; tag?: StepFeedbackTag }) => {
    const token = await getToken()
    if (!token) return null
    return submitStepFeedback(journeyId, stepId, body, token)
  }

  const handleUp = async () => {
    setRating('up')
    setShowTags(false)
    try {
      await send({ rating: 'up' })
    } catch {
      /* feedback is best-effort — never interrupt the learner */
    }
  }

  const handleDown = () => {
    setRating('down')
    setShowTags(true)
  }

  const handleTag = async (tag: StepFeedbackTag) => {
    setTagSent(true)
    setShowTags(false)
    try {
      const res = await send({ rating: 'down', tag })
      if (res?.regenerating) {
        addToast('Got it — rewriting this step for you. Check back in a minute.', 'info')
      } else {
        addToast('Thanks for the feedback')
      }
    } catch {
      addToast("Couldn't send feedback", 'error')
      setTagSent(false)
    }
  }

  const handleRegenerate = async () => {
    if (regenerating) return
    setRegenerating(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await regenerateStepContent(journeyId, stepId, token)
      onRegenerated(res.content)
      addToast('Fresh take ready')
    } catch (e: any) {
      if (e?.status === 402) addToast('Plan budget used up — upgrade to keep generating', 'error')
      else if (e?.status === 429) addToast('Regeneration limit reached — try again later', 'error')
      else addToast("Couldn't regenerate right now. Try again.", 'error')
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-slate-400 dark:text-slate-600 mr-1">Was this helpful?</span>
        <button
          onClick={handleUp}
          disabled={rating === 'up'}
          aria-label="Helpful"
          className={clsx(
            'p-1.5 rounded-lg border transition-colors',
            rating === 'up'
              ? 'border-emerald-300 bg-emerald-50 text-emerald-600 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-400'
              : 'border-slate-200 text-slate-400 hover:text-emerald-500 hover:border-emerald-300 dark:border-slate-700 dark:text-slate-500 dark:hover:text-emerald-400'
          )}
        >
          <ThumbsUp size={13} />
        </button>
        <button
          onClick={handleDown}
          disabled={tagSent}
          aria-label="Not helpful"
          className={clsx(
            'p-1.5 rounded-lg border transition-colors',
            rating === 'down'
              ? 'border-rose-300 bg-rose-50 text-rose-500 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-400'
              : 'border-slate-200 text-slate-400 hover:text-rose-500 hover:border-rose-300 dark:border-slate-700 dark:text-slate-500 dark:hover:text-rose-400'
          )}
        >
          <ThumbsDown size={13} />
        </button>

        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 hover:text-violet-500 dark:text-slate-500 dark:hover:text-violet-400 transition-colors disabled:opacity-60"
        >
          {regenerating
            ? <><Loader2 size={12} className="animate-spin" />Writing a fresh take…</>
            : <><RefreshCw size={12} />Fresh take</>}
        </button>
      </div>

      {showTags && !tagSent && (
        <div className="mt-2 flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-slate-400 dark:text-slate-600">What went wrong?</span>
          {DOWN_TAGS.map(({ tag, label }) => (
            <button
              key={tag}
              onClick={() => handleTag(tag)}
              className="text-xs px-2 py-1 rounded-full border border-slate-200 text-slate-500 hover:border-violet-300 hover:text-violet-600 dark:border-slate-700 dark:text-slate-400 dark:hover:border-violet-400/40 dark:hover:text-violet-400 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {tagSent && (
        <p className="mt-2 text-xs text-slate-400 dark:text-slate-600 flex items-center gap-1">
          <Check size={11} className="text-emerald-500" />
          Thanks — this makes the next version better.
        </p>
      )}
    </div>
  )
}
