'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Clock, BookOpen, Share2 } from 'lucide-react'
import Navigation from '@/components/Navigation'
import StepNode from '@/components/StepNode'
import { getJourney } from '@/lib/api'
import type { Journey, JourneyStep } from '@/lib/types'

export default function JourneyPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [journey, setJourney] = useState<Journey | null>(null)
  const [steps, setSteps] = useState<JourneyStep[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getJourney(id)
      .then((j) => {
        setJourney(j)
        setSteps(j.steps)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  const toggleStep = (stepId: string) => {
    setSteps((prev) => prev.map((s) => (s.id === stepId ? { ...s, completed: !s.completed } : s)))
  }

  const completed = steps.filter((s) => s.completed).length
  const progress = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-violet-600/6 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative pt-24 pb-20 px-4 max-w-3xl mx-auto">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 mb-8 transition-colors group"
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
          <div className="glass rounded-2xl p-10 text-center border border-rose-500/20">
            <p className="text-rose-400 text-sm">{error}</p>
          </div>
        )}

        {journey && !loading && (
          <div className="animate-in">
            {/* Header */}
            <div className="mb-10">
              <div className="flex items-start gap-4 mb-5">
                <span className="text-5xl">{journey.icon}</span>
                <div>
                  <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Learning Journey</p>
                  <h1 className="text-2xl md:text-3xl font-bold leading-tight">{journey.title}</h1>
                </div>
              </div>

              <p className="text-slate-400 leading-relaxed mb-5">{journey.description}</p>

              <div className="flex flex-wrap gap-2 mb-5">
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-700 bg-slate-800/50 text-slate-400">
                  <BookOpen size={11} /> {steps.length} steps
                </span>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-700 bg-slate-800/50 text-slate-400">
                  <Clock size={11} /> ~{journey.estimated_hours}h
                </span>
                <span className="px-3 py-1.5 rounded-full text-xs border border-violet-500/30 bg-violet-500/10 text-violet-300 capitalize">
                  {journey.difficulty}
                </span>
              </div>

              {/* Progress */}
              <div className="mb-6">
                <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                  <span>{completed} / {steps.length} completed</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-700"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <div className="flex gap-3">
                <button className="btn-primary">
                  {completed === 0 ? 'Start Journey' : 'Continue'}
                </button>
                <button className="btn-ghost flex items-center gap-1.5">
                  <Share2 size={13} />
                  Share
                </button>
              </div>
            </div>

            <div className="flex items-center gap-3 mb-8">
              <div className="flex-1 h-px bg-slate-800" />
              <span className="text-xs text-slate-600 uppercase tracking-widest">Learning Path</span>
              <div className="flex-1 h-px bg-slate-800" />
            </div>

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
        )}
      </div>
    </>
  )
}
