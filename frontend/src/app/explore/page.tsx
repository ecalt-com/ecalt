'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { ArrowLeft, Clock, BookOpen, Zap } from 'lucide-react'
import Navigation from '@/components/Navigation'
import CuriosityInput from '@/components/CuriosityInput'
import StepNode from '@/components/StepNode'
import { exploreQuestion } from '@/lib/api'
import type { Journey, JourneyStep } from '@/lib/types'

function ExploreContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [journey, setJourney] = useState<Journey | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [steps, setSteps] = useState<JourneyStep[]>([])

  const q = searchParams.get('q') || ''

  useEffect(() => {
    if (!q) return
    fetchJourney(q)
  }, [q])

  const fetchJourney = async (question: string) => {
    setLoading(true)
    setError(null)
    setJourney(null)
    try {
      const result = await exploreQuestion({ question, age_group: 'all' })
      setJourney(result)
      setSteps(result.steps)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate journey. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleNewExplore = (question: string) => {
    router.push(`/explore?q=${encodeURIComponent(question)}`)
  }

  const toggleStep = (id: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, completed: !s.completed } : s))
    )
  }

  const completedCount = steps.filter((s) => s.completed).length
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0

  return (
    <div className="relative min-h-screen pt-24 pb-16 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Back */}
        <button
          onClick={() => router.push('/')}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 mb-8 transition-colors group"
        >
          <ArrowLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
          Back home
        </button>

        {/* Input at top */}
        {!loading && !journey && (
          <div className="mb-12">
            <h1 className="text-3xl font-bold mb-3">What do you want to learn?</h1>
            <p className="text-slate-500 mb-8">Ask anything — ECALT will build your learning path.</p>
            <CuriosityInput onExplore={handleNewExplore} />
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-6">
            <div className="shimmer-bg h-8 w-3/4 rounded-xl" />
            <div className="shimmer-bg h-5 w-full rounded-xl" />
            <div className="shimmer-bg h-5 w-2/3 rounded-xl" />
            <div className="flex gap-3 mt-4">
              <div className="shimmer-bg h-7 w-24 rounded-full" />
              <div className="shimmer-bg h-7 w-20 rounded-full" />
              <div className="shimmer-bg h-7 w-28 rounded-full" />
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
            <p className="text-center text-sm text-slate-600 mt-4">
              ✦ Building your learning journey…
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="glass rounded-2xl p-8 text-center border border-rose-500/20">
            <p className="text-rose-400 mb-4">{error}</p>
            <button onClick={() => fetchJourney(q)} className="btn-primary">
              Try again
            </button>
          </div>
        )}

        {/* Result */}
        {journey && !loading && (
          <div className="animate-in">
            {/* Journey header */}
            <div className="mb-10">
              <div className="flex items-start gap-4 mb-4">
                <span className="text-5xl">{journey.icon}</span>
                <div className="flex-1">
                  <p className="text-xs text-slate-600 mb-1 uppercase tracking-wider">Learning Journey</p>
                  <h1 className="text-2xl md:text-3xl font-bold text-slate-100 leading-tight">{journey.title}</h1>
                </div>
              </div>

              <p className="text-slate-400 leading-relaxed mb-5">{journey.description}</p>

              {/* Meta badges */}
              <div className="flex flex-wrap gap-2 mb-6">
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-700 bg-slate-800/50 text-slate-400">
                  <BookOpen size={11} />
                  {journey.steps.length} steps
                </span>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-700 bg-slate-800/50 text-slate-400">
                  <Clock size={11} />
                  ~{journey.estimated_hours}h total
                </span>
                <span className="px-3 py-1.5 rounded-full text-xs border border-violet-500/30 bg-violet-500/10 text-violet-300">
                  {journey.difficulty}
                </span>
                {journey.tags.map((tag) => (
                  <span key={tag} className="px-3 py-1.5 rounded-full text-xs border border-slate-800 bg-slate-900 text-slate-600">
                    #{tag}
                  </span>
                ))}
              </div>

              {/* Progress bar */}
              {completedCount > 0 && (
                <div className="mb-6">
                  <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
                    <span>{completedCount} of {steps.length} steps complete</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Start button */}
              <div className="flex items-center gap-3">
                <button className="btn-primary flex items-center gap-2">
                  <Zap size={14} fill="currentColor" />
                  Begin Journey
                </button>
                <button
                  onClick={() => handleNewExplore('')}
                  className="btn-ghost"
                >
                  Ask something else
                </button>
              </div>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3 mb-8">
              <div className="flex-1 h-px bg-slate-800" />
              <span className="text-xs text-slate-600 uppercase tracking-widest">Your Path</span>
              <div className="flex-1 h-px bg-slate-800" />
            </div>

            {/* Steps */}
            <div>
              {steps.map((step, i) => (
                <StepNode
                  key={step.id}
                  step={step}
                  index={i}
                  isLast={i === steps.length - 1}
                  onToggle={toggleStep}
                />
              ))}
            </div>

            {/* New search */}
            <div className="mt-16 pt-8 border-t border-slate-800/50">
              <p className="text-center text-slate-500 text-sm mb-6">Curious about something else?</p>
              <CuriosityInput onExplore={handleNewExplore} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ExplorePage() {
  return (
    <>
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-violet-600/6 rounded-full blur-[120px] animate-glow-pulse" />
        <div className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-cyan-500/6 rounded-full blur-[100px] animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>
      <Navigation />
      <Suspense
        fallback={
          <div className="min-h-screen pt-24 flex items-center justify-center">
            <p className="text-slate-600">Loading…</p>
          </div>
        }
      >
        <ExploreContent />
      </Suspense>
    </>
  )
}
