import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, BookOpen, Share2, Award } from 'lucide-react'
import Navigation from '../components/Navigation'
import StepNode from '../components/StepNode'
import PageMeta from '../components/PageMeta'
import { getJourney, getProgress, markStepComplete, markStepIncomplete } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'
import type { Journey as JourneyType, JourneyStep } from '../lib/types'

function CompletionOverlay({ journey, onDismiss }: { journey: JourneyType; onDismiss: () => void }) {
  const navigate = useNavigate()
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="animate-celebration glass-card rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl">
        <div className="text-6xl mb-4">{journey.icon}</div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300 text-xs font-semibold mb-4">
          <Award size={12} />
          Capability Earned
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Journey Complete!</h2>
        <p className="text-sm text-slate-500 mb-6">
          You've finished <span className="font-semibold text-slate-700 dark:text-slate-300">{journey.title}</span> and earned a capability badge.
        </p>
        <div className="flex flex-col gap-3">
          <button
            onClick={() => navigate('/passport')}
            className="btn-primary flex items-center justify-center gap-2"
          >
            <Award size={14} />
            View Passport
          </button>
          <button
            onClick={onDismiss}
            className="btn-ghost text-sm"
          >
            Keep exploring
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Journey() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user, getToken } = useAuth()
  const { addToast } = useToast()
  const [journey, setJourney] = useState<JourneyType | null>(null)
  const [steps, setSteps] = useState<JourneyStep[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCompletion, setShowCompletion] = useState(false)

  useEffect(() => {
    if (!id) return
    const load = async () => {
      try {
        const token = await getToken()
        const j = await getJourney(id, token ?? undefined)
        let completedIds: string[] = []
        if (token) {
          try {
            const prog = await getProgress(id, token)
            completedIds = prog.completed_step_ids
          } catch { /* guest — no progress */ }
        }
        setJourney(j)
        setSteps(j.steps.map(s => ({ ...s, completed: completedIds.includes(s.id) })))
      } catch (err: unknown) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const toggleStep = async (stepId: string) => {
    const step = steps.find(s => s.id === stepId)
    if (!step || !id) return

    const completing = !step.completed

    // Optimistic update + check for journey completion
    setSteps(prev => {
      const updated = prev.map(s => s.id === stepId ? { ...s, completed: completing } : s)
      if (completing && updated.every(s => s.completed)) {
        setShowCompletion(true)
      }
      return updated
    })

    addToast(completing ? 'Step complete ✓' : 'Step unmarked')

    if (user) {
      const token = await getToken()
      if (token) {
        try {
          if (step.completed) {
            await markStepIncomplete(id, stepId, token)
          } else {
            await markStepComplete(id, stepId, token)
          }
        } catch {
          // Revert on failure
          setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: step.completed } : s))
          addToast("Couldn't save — try again", 'error')
        }
      }
    }
  }

  const completed = steps.filter(s => s.completed).length
  const progress = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0

  const jsonLd = journey
    ? {
        '@context': 'https://schema.org',
        '@type': 'Course',
        name: journey.title,
        description: journey.description,
        provider: { '@type': 'Organization', name: 'ECALT', url: 'https://ecalt.vercel.app' },
        hasCourseInstance: { '@type': 'CourseInstance', courseMode: 'online' },
        educationalLevel: journey.difficulty,
        teaches: journey.tags.join(', '),
      }
    : undefined

  return (
    <>
      <PageMeta
        title={journey?.title}
        description={journey?.description}
        canonicalPath={id ? `/journey/${id}` : undefined}
        jsonLd={jsonLd}
      />
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative min-h-screen pt-24 pb-20 px-4 max-w-3xl mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 mb-8 transition-colors group"
        >
          <ArrowLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
          Back
        </button>

        {loading && (
          <div className="space-y-5">
            <div className="shimmer-bg h-9 w-2/3 rounded-xl" />
            <div className="shimmer-bg h-5 w-full rounded-xl" />
            <div className="shimmer-bg h-5 w-3/4 rounded-xl" />
          </div>
        )}

        {error && (
          <div className="glass rounded-2xl p-10 text-center border border-rose-200 dark:border-rose-500/20">
            <p className="text-rose-600 dark:text-rose-400 text-sm">{error}</p>
          </div>
        )}

        {journey && !loading && (
          <div className="animate-in">
            <div className="mb-10">
              <div className="flex items-start gap-3 mb-5">
                <span className="text-4xl sm:text-5xl shrink-0">{journey.icon}</span>
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Learning Journey</p>
                  <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight">{journey.title}</h1>
                </div>
              </div>

              <p className="text-slate-500 leading-relaxed mb-5">{journey.description}</p>

              <div className="flex flex-wrap gap-2 mb-5">
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
                  <BookOpen size={11} />{steps.length} steps
                </span>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
                  <Clock size={11} />~{journey.estimated_hours}h
                </span>
                <span className="px-3 py-1.5 rounded-full text-xs border border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300 capitalize">
                  {journey.difficulty}
                </span>
              </div>

              <div className="mb-6">
                <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                  <span>{completed} / {steps.length} completed</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-700"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button className="btn-primary text-center">
                  {completed === 0 ? 'Start Journey' : 'Continue'}
                </button>
                <button
                  onClick={() => navigator.clipboard?.writeText(window.location.href)}
                  className="btn-ghost flex items-center justify-center gap-1.5"
                >
                  <Share2 size={13} />Share
                </button>
              </div>
            </div>

            <div className="flex items-center gap-3 mb-8">
              <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
              <span className="text-xs text-slate-400 uppercase tracking-widest">Learning Path</span>
              <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
            </div>

            {steps.map((step, i) => (
              <StepNode
                key={step.id}
                step={step}
                index={i}
                isLast={i === steps.length - 1}
                journeyId={id!}
                getToken={getToken}
                onToggle={toggleStep}
              />
            ))}
          </div>
        )}
      </div>

      {showCompletion && journey && (
        <CompletionOverlay journey={journey} onDismiss={() => setShowCompletion(false)} />
      )}
    </>
  )
}
