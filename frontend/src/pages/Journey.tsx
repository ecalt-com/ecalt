import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, BookOpen, Share2, Award, TrendingUp, Loader2 } from 'lucide-react'
import Navigation from '../components/Navigation'
import StepNode from '../components/StepNode'
import PageMeta from '../components/PageMeta'
import { getJourney, getJourneys, getProgress, getJourneySuggestions, markStepComplete } from '../lib/api'
import type { JourneySuggestions } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'
import type { Journey as JourneyType, JourneyStep } from '../lib/types'

function CompletionOverlay({ journey, onDismiss }: { journey: JourneyType; onDismiss: () => void }) {
  const navigate = useNavigate()
  const { getToken } = useAuth()
  const [suggestions, setSuggestions] = useState<JourneySuggestions | null>(null)
  const [loadingSuggestions, setLoadingSuggestions] = useState(true)

  // What's next — fetched while the celebration shows. May AI-generate the
  // next level server-side, so this can take a few seconds; the overlay is
  // fully usable without it.
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const s = await getJourneySuggestions(journey.id, token)
        if (alive) setSuggestions(s)
      } catch { /* fall back to the default buttons */ }
      finally { if (alive) setLoadingSuggestions(false) }
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journey.id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto modal-overlay">
      <div className="animate-celebration glass-card rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl my-8">
        <div className="text-6xl mb-4">{journey.icon}</div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300 text-xs font-semibold mb-4">
          <Award size={12} />
          Capability Earned
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Journey Complete!</h2>
        <p className="text-sm text-slate-500 mb-6">
          You've finished <span className="font-semibold text-slate-700 dark:text-slate-300">{journey.title}</span> and earned a capability badge.
        </p>

        {loadingSuggestions && (
          <div className="flex items-center justify-center gap-2 text-xs text-slate-400 mb-6">
            <Loader2 size={12} className="animate-spin" />
            Finding what's next…
          </div>
        )}

        {suggestions?.next_level && (
          <button
            onClick={() => navigate(`/journey/${suggestions.next_level!.id}`)}
            className="w-full mb-3 p-4 rounded-2xl border border-violet-300 dark:border-violet-500/40 bg-violet-50 dark:bg-violet-500/10 text-left hover:border-violet-400 dark:hover:border-violet-400 transition-colors group"
          >
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-400 mb-1">
              <TrendingUp size={11} />
              Level up · {suggestions.next_level.difficulty}
            </p>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              {suggestions.next_level.icon} {suggestions.next_level.title}
            </p>
          </button>
        )}

        {suggestions && suggestions.similar.length > 0 && (
          <div className="mb-5 text-left">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Or try something new</p>
            <div className="space-y-2">
              {suggestions.similar.map(s => (
                <button
                  key={s.id}
                  onClick={() => navigate(`/journey/${s.id}`)}
                  className="w-full flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-violet-300 dark:hover:border-violet-600 transition-colors text-left"
                >
                  <span className="text-lg shrink-0">{s.icon}</span>
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">{s.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3">
          <button
            onClick={() => navigate('/passport')}
            className={suggestions?.next_level ? 'btn-ghost text-sm flex items-center justify-center gap-2' : 'btn-primary flex items-center justify-center gap-2'}
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
  const [related, setRelated] = useState<JourneyType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCompletion, setShowCompletion] = useState(false)
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    // Reset page state — the completion overlay navigates between journeys
    // on this same route, so the component instance survives the id change.
    setJourney(null)
    setSteps([])
    setRelated([])
    setError(null)
    setLoading(true)
    setShowCompletion(false)
    setExpandedStepId(null)

    // Client-side fallback when the suggestions endpoint is unavailable
    const relatedByTags = (j: JourneyType, token?: string) => {
      getJourneys(token).then(res => {
        const scored = res.journeys
          .filter(r => r.id !== id)
          .map(r => ({
            ...r,
            score: r.tags.filter(t => j.tags.includes(t)).length,
          }))
          .filter(r => r.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 3)
        setRelated(scored)
      }).catch(() => {})
    }

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

        // "More like this" (best-effort, non-blocking): signed-in users get
        // history-aware suggestions; guests get plain tag overlap.
        if (token) {
          getJourneySuggestions(id, token)
            .then(s => setRelated(s.similar))
            .catch(() => relatedByTags(j, token))
        } else {
          relatedByTags(j)
        }
      } catch (err: unknown) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  // Step i is locked until every earlier step is complete (matches the backend
  // 409 gate, which checks all prior steps — not just the previous one).
  const isStepLocked = (index: number) => steps.slice(0, index).some(s => !s.completed)

  // Forward-only: steps are completed through the step flow and never unmarked.
  const completeStep = async (stepId: string) => {
    const index = steps.findIndex(s => s.id === stepId)
    if (index === -1 || !id) return
    if (steps[index].completed) return
    if (isStepLocked(index)) {
      addToast('Finish the earlier steps first', 'error')
      return
    }

    // Optimistic update
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: true } : s))
    addToast('Step complete ✓')

    if (user) {
      const token = await getToken()
      if (token) {
        try {
          await markStepComplete(id, stepId, token)
        } catch (err: unknown) {
          // Revert on failure
          setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: false } : s))
          const status = (err as { status?: number })?.status
          addToast(
            status === 409 ? 'Finish the earlier steps first'
            : status === 412 ? 'Pass the quiz to finish this step'
            : "Couldn't save — try again",
            'error',
          )
        }
      }
    }
  }

  const toggleExpanded = (stepId: string) =>
    setExpandedStepId(prev => (prev === stepId ? null : stepId))

  // Start Journey / Continue — open the first incomplete step and scroll to it.
  const startJourney = () => {
    const target = steps.find(s => !s.completed) ?? steps[0]
    if (!target) return
    setExpandedStepId(target.id)
    document.getElementById(`step-${target.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
                <button onClick={startJourney} className="btn-primary text-center">
                  {completed === 0 ? 'Start Journey' : 'Continue'}
                </button>
                <button
                  onClick={async () => {
                    const url = window.location.href
                    const title = journey.title
                    if (navigator.share) {
                      try { await navigator.share({ title, url }) } catch { /* cancelled */ }
                    } else {
                      await navigator.clipboard.writeText(url)
                      addToast('Link copied to clipboard')
                    }
                  }}
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
                onToggle={completeStep}
                expanded={expandedStepId === step.id}
                onExpandToggle={toggleExpanded}
                locked={isStepLocked(i)}
              />
            ))}

            {/* Completion card — appears when every step is read */}
            {completed === steps.length && steps.length > 0 && (
              <div className="mt-8 animate-in">
                <div className="rounded-2xl border border-violet-200 dark:border-violet-500/25 bg-gradient-to-br from-violet-50 via-white to-cyan-50/40 dark:from-violet-950/50 dark:via-slate-900/60 dark:to-cyan-950/20 p-7 text-center">
                  <div className="text-5xl mb-3">{journey.icon}</div>
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300 text-xs font-semibold mb-3">
                    <Award size={11} />
                    All steps complete
                  </div>
                  <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1">
                    You've covered everything in this journey.
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">
                    Ready to add it to your Passport?
                  </p>
                  <button
                    onClick={() => setShowCompletion(true)}
                    className="btn-primary flex items-center justify-center gap-2 mx-auto"
                  >
                    <Award size={14} />
                    Complete Journey
                  </button>
                </div>
              </div>
            )}

            {related.length > 0 && (
              <div className="mt-16 pt-8 border-t border-slate-200 dark:border-slate-800/50">
                <p className="text-xs text-slate-400 uppercase tracking-widest mb-4">More like this</p>
                <div className="space-y-3">
                  {related.map(r => (
                    <button
                      key={r.id}
                      onClick={() => navigate(`/journey/${r.id}`)}
                      className="w-full flex items-center gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-violet-300 dark:hover:border-violet-700 bg-white/50 dark:bg-slate-900/30 text-left transition-colors group"
                    >
                      <span className="text-2xl shrink-0">{r.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{r.title}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{r.steps.length} steps · {r.difficulty}</p>
                      </div>
                      <ArrowLeft size={14} className="text-slate-400 rotate-180 group-hover:translate-x-0.5 transition-transform shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showCompletion && journey && (
        <CompletionOverlay journey={journey} onDismiss={() => setShowCompletion(false)} />
      )}
    </>
  )
}
