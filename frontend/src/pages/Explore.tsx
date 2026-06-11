import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, BookOpen, Zap } from 'lucide-react'
import Navigation from '../components/Navigation'
import CuriosityInput from '../components/CuriosityInput'
import StepNode from '../components/StepNode'
import { exploreQuestion, markStepComplete } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { usePageTitle } from '../lib/usePageTitle'
import type { Journey, JourneyStep } from '../lib/types'

export default function Explore() {
  usePageTitle('Explore')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user, loading: authLoading, getToken } = useAuth()
  const [journey, setJourney] = useState<Journey | null>(null)
  const [steps, setSteps] = useState<JourneyStep[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null)

  const q = searchParams.get('q') || ''

  // Redirect guests to home — explore requires authentication
  useEffect(() => {
    if (!authLoading && !user) navigate('/')
  }, [user, authLoading, navigate])

  useEffect(() => {
    if (q && user) fetchJourney(q)
  }, [q, user])

  const fetchJourney = async (question: string) => {
    setLoading(true)
    setError(null)
    setJourney(null)
    try {
      const token = await getToken()
      if (!token) { navigate('/'); return }
      const { journey: result } = await exploreQuestion({ question, age_group: 'all' }, token)
      setJourney(result)
      setSteps(result.steps)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate journey. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const goExplore = (question: string) => navigate(`/explore?q=${encodeURIComponent(question)}`)

  // Step i is locked until every earlier step is complete (matches the backend
  // 409 gate, which checks all prior steps — not just the previous one).
  const isStepLocked = (index: number) => steps.slice(0, index).some(s => !s.completed)

  // Forward-only: steps are completed through the step flow and never unmarked.
  const completeStep = async (stepId: string) => {
    const index = steps.findIndex(s => s.id === stepId)
    if (index === -1 || !journey) return
    if (steps[index].completed || isStepLocked(index)) return
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: true } : s))
    const token = await getToken()
    if (token) {
      try {
        await markStepComplete(journey.id, stepId, token)
      } catch {
        setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: false } : s))
      }
    }
  }

  const toggleExpanded = (stepId: string) =>
    setExpandedStepId(prev => (prev === stepId ? null : stepId))

  // Begin Journey — open the first incomplete step and scroll to it.
  const beginJourney = () => {
    const target = steps.find(s => !s.completed) ?? steps[0]
    if (!target) return
    setExpandedStepId(target.id)
    document.getElementById(`step-${target.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const completed = steps.filter(s => s.completed).length
  const progress = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
        <div className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-cyan-500/5 rounded-full blur-[100px] animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <Navigation />

      <div className="relative min-h-screen pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 mb-8 transition-colors group"
          >
            <ArrowLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
            Back home
          </button>

          {!loading && !journey && (
            <div className="mb-12">
              <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-3">What do you want to learn?</h1>
              <p className="text-slate-500 mb-8">Ask anything — ECALT will build your learning path.</p>
              <CuriosityInput onExplore={goExplore} initialValue={q} />
            </div>
          )}

          {loading && (
            <div className="space-y-5">
              <div className="shimmer-bg h-8 w-3/4 rounded-xl" />
              <div className="shimmer-bg h-5 w-full rounded-xl" />
              <div className="shimmer-bg h-5 w-2/3 rounded-xl" />
              <div className="flex gap-3 mt-4">
                {[24, 20, 28].map(w => <div key={w} className={`shimmer-bg h-7 w-${w} rounded-full`} />)}
              </div>
              <div className="mt-8 space-y-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex gap-4">
                    <div className="shimmer-bg w-10 h-10 rounded-full shrink-0" />
                    <div className="flex-1 space-y-2 pt-2">
                      <div className="shimmer-bg h-4 w-2/3 rounded-lg" />
                      <div className="shimmer-bg h-3 w-full rounded-lg" />
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-center text-sm text-slate-500 mt-4">✦ Building your learning journey…</p>
            </div>
          )}

          {error && (
            <div className="glass rounded-2xl p-8 text-center border border-rose-200 dark:border-rose-500/20">
              <p className="text-rose-600 dark:text-rose-400 mb-4">{error}</p>
              <button onClick={() => fetchJourney(q)} className="btn-primary">Try again</button>
            </div>
          )}

          {journey && !loading && (
            <div className="animate-in">
              <div className="mb-10">
                <div className="flex items-start gap-3 mb-4">
                  <span className="text-4xl sm:text-5xl shrink-0">{journey.icon}</span>
                  <div>
                    <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Learning Journey</p>
                    <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight">{journey.title}</h1>
                  </div>
                </div>
                <p className="text-slate-500 leading-relaxed mb-5">{journey.description}</p>

                <div className="flex flex-wrap gap-2 mb-5">
                  <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
                    <BookOpen size={11} />{journey.steps.length} steps
                  </span>
                  <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
                    <Clock size={11} />~{journey.estimated_hours}h
                  </span>
                  <span className="px-3 py-1.5 rounded-full text-xs border border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300 capitalize">
                    {journey.difficulty}
                  </span>
                  {journey.tags.map(tag => (
                    <span key={tag} className="px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-600">#{tag}</span>
                  ))}
                </div>

                {completed > 0 && (
                  <div className="mb-5">
                    <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                      <span>{completed} of {steps.length} steps complete</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
                    </div>
                  </div>
                )}

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <button onClick={beginJourney} className="btn-primary flex items-center justify-center gap-2">
                    <Zap size={14} fill="currentColor" />Begin Journey
                  </button>
                  <button onClick={() => goExplore('')} className="btn-ghost text-center">Ask something else</button>
                </div>
              </div>

              <div className="flex items-center gap-3 mb-8">
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                <span className="text-xs text-slate-400 uppercase tracking-widest">Your Path</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
              </div>

              {steps.map((step, i) => (
                <StepNode
                  key={step.id}
                  step={step}
                  index={i}
                  isLast={i === steps.length - 1}
                  journeyId={journey!.id}
                  getToken={getToken}
                  onToggle={completeStep}
                  expanded={expandedStepId === step.id}
                  onExpandToggle={toggleExpanded}
                  locked={isStepLocked(i)}
                />
              ))}

              <div className="mt-16 pt-8 border-t border-slate-200 dark:border-slate-800/50">
                <p className="text-center text-slate-500 text-sm mb-6">Curious about something else?</p>
                <CuriosityInput onExplore={goExplore} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
