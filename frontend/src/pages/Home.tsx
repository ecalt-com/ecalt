import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Zap, ArrowRight, Loader2, Sparkles,
  BookOpen, Wrench, Compass, Check,
  Shield, Map, Star,
} from 'lucide-react'
import clsx from 'clsx'
import GateModal from '../components/GateModal'
import Navigation from '../components/Navigation'
import { askSpark } from '../lib/api'
import type { Mission, StepType } from '../lib/types'

// ── Session ───────────────────────────────────────────────────────────────────
function getSessionId() {
  let id = localStorage.getItem('ecalt_sid') || ''
  if (!id) { id = crypto.randomUUID(); localStorage.setItem('ecalt_sid', id) }
  return id
}

// ── State shape ───────────────────────────────────────────────────────────────
type Phase =
  | { kind: 'hero' }
  | { kind: 'loading'; question: string }
  | { kind: 'sparked'; question: string; answer: string; mission: Mission; sparksUsed: number; sparksRemaining: number }
  | { kind: 'error'; question: string; message: string }

// ── Inline sub-components ─────────────────────────────────────────────────────

const CHIPS = [
  { emoji: '🤖', label: 'Build a robot' },
  { emoji: '🕳️', label: 'Explain black holes' },
  { emoji: '🎵', label: 'Make AI music' },
  { emoji: '💡', label: 'Smart night lamp' },
]

interface AskBoxProps {
  onSpark: (q: string) => void
  loading: boolean
}

function AskBox({ onSpark, loading }: AskBoxProps) {
  const [query, setQuery] = useState('')

  const submit = (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || loading) return
    onSpark(trimmed)
  }

  return (
    <div className="w-full space-y-4">
      <form onSubmit={e => { e.preventDefault(); submit(query) }}>
        <div className={clsx(
          'flex items-center gap-3 bg-white dark:bg-slate-800/60 rounded-2xl px-5 py-4 transition-all duration-200',
          'border border-slate-200 dark:border-slate-700 shadow-lg shadow-slate-200/60 dark:shadow-slate-900/60',
          'focus-within:border-violet-300 dark:focus-within:border-violet-500/50 focus-within:ring-2 focus-within:ring-violet-500/15 focus-within:shadow-violet-100/60'
        )}>
          <Sparkles size={20} className="text-violet-500 dark:text-violet-400 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="What do you want to understand or build?"
            autoFocus
            disabled={loading}
            className="flex-1 bg-transparent text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 text-base outline-none"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className={clsx(
              'shrink-0 flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200',
              'bg-violet-600 hover:bg-violet-700 text-white',
              'disabled:opacity-40 disabled:cursor-not-allowed'
            )}
          >
            {loading
              ? <><Loader2 size={14} className="animate-spin" /><span>Thinking…</span></>
              : <><span>Ask ECALT</span><ArrowRight size={14} /></>
            }
          </button>
        </div>
      </form>

      {/* Curiosity chips */}
      <div className="flex flex-wrap gap-2 justify-center">
        {CHIPS.map(({ emoji, label }) => (
          <button
            key={label}
            onClick={() => submit(label)}
            className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
              border border-slate-200 bg-white text-slate-600 shadow-sm
              hover:border-violet-300 hover:text-violet-700 hover:bg-violet-50
              dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-400 dark:shadow-none
              dark:hover:border-violet-500/50 dark:hover:text-violet-300 dark:hover:bg-violet-500/10
              transition-all duration-200"
          >
            <span>{emoji}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Spark result (light) ──────────────────────────────────────────────────────

const STEP_TYPE: Record<StepType, { icon: React.ElementType; color: string; bg: string; label: string }> = {
  concept:   { icon: BookOpen, color: 'text-violet-600', bg: 'bg-violet-50',  label: 'Learn' },
  practice:  { icon: Wrench,   color: 'text-cyan-600',   bg: 'bg-cyan-50',    label: 'Practice' },
  challenge: { icon: Zap,      color: 'text-amber-600',  bg: 'bg-amber-50',   label: 'Challenge' },
  explore:   { icon: Compass,  color: 'text-emerald-600',bg: 'bg-emerald-50', label: 'Explore' },
}

const DIFF_COLOR: Record<string, string> = {
  beginner:     'text-emerald-700 bg-emerald-50 border-emerald-200',
  intermediate: 'text-amber-700 bg-amber-50 border-amber-200',
  advanced:     'text-rose-700 bg-rose-50 border-rose-200',
}

interface LightResultProps {
  question: string
  answer: string
  mission: Mission
  sparksUsed: number
  sparksRemaining: number
  onStartMission: () => void
  onReset: () => void
  onUpgrade: () => void
}

function LightSparkResult({ question, answer, mission, sparksUsed, sparksRemaining, onStartMission, onReset, onUpgrade }: LightResultProps) {
  return (
    <div className="animate-in max-w-2xl mx-auto px-4 pb-20">
      {/* Answer */}
      <div className="mb-6">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-1.5">You asked</p>
        <p className="text-slate-500 italic text-sm mb-4">"{question}"</p>
        <div className="bg-violet-50 dark:bg-violet-900/20 border border-violet-100 dark:border-violet-800/40 border-l-4 border-l-violet-500 rounded-2xl p-6">
          <p className="text-slate-800 dark:text-slate-200 leading-relaxed">{answer}</p>
        </div>
      </div>

      {/* Mission card */}
      <div className="light-card rounded-2xl overflow-hidden mb-5">
        {/* Header */}
        <div className="p-6 pb-4 border-b border-slate-100">
          <div className="flex items-start gap-4">
            <span className="text-4xl">{mission.icon}</span>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className={clsx('px-2.5 py-0.5 rounded-full text-xs font-medium border', DIFF_COLOR[mission.difficulty])}>
                  {mission.difficulty}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs border border-slate-200 bg-slate-50 text-slate-500">
                  #{mission.category}
                </span>
                <span className="text-xs text-slate-400">{mission.estimated_minutes} min</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 leading-snug">{mission.title}</h3>
            </div>
          </div>
          <p className="text-sm text-slate-500 mt-2 leading-relaxed">{mission.tagline}</p>
        </div>

        {/* Steps */}
        <div className="p-6 pb-4">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-3">Mission Path</p>
          <div className="space-y-2">
            {mission.steps.map((step, i) => {
              const cfg = STEP_TYPE[step.type]
              const Icon = cfg.icon
              return (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/50">
                  <div className="w-6 h-6 rounded-full bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 flex items-center justify-center text-xs font-bold text-slate-500 shrink-0">
                    {i + 1}
                  </div>
                  <div className={clsx('p-1 rounded-md', cfg.bg)}>
                    <Icon size={12} className={cfg.color} />
                  </div>
                  <span className="text-sm text-slate-700 dark:text-slate-300 flex-1">{step.title}</span>
                  <span className="text-xs text-slate-400">{step.minutes}m</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* CTA */}
        <div className="px-6 pb-6">
          <button
            onClick={onStartMission}
            className="w-full py-3 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            <Zap size={14} fill="currentColor" />
            Start This Mission
          </button>
        </div>
      </div>

      {/* Spark meter */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={clsx('w-2 h-2 rounded-full transition-all', i < sparksUsed ? 'bg-slate-300' : 'bg-violet-500')}
            />
          ))}
          <span className="text-slate-400 text-xs ml-1">
            {sparksRemaining === 0
              ? <button onClick={onUpgrade} className="text-violet-600 font-medium hover:underline">Upgrade for unlimited →</button>
              : <><span className="font-medium text-violet-600">{sparksRemaining}</span> spark{sparksRemaining !== 1 ? 's' : ''} left</>
            }
          </span>
        </div>
        <button onClick={onReset} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
          ↑ Ask another
        </button>
      </div>
    </div>
  )
}

function LightLoadingSkeleton() {
  return (
    <div className="max-w-2xl mx-auto px-4 pb-20 space-y-4">
      <div className="shimmer-light h-4 w-1/4 rounded-lg" />
      <div className="shimmer-light h-4 w-2/3 rounded-lg" />
      <div className="shimmer-light h-28 w-full rounded-2xl" />
      <div className="shimmer-light h-72 w-full rounded-2xl" />
      <p className="text-center text-xs text-slate-400 animate-pulse">✦ Sparking your curiosity…</p>
    </div>
  )
}

// ── Feature cards ─────────────────────────────────────────────────────────────

interface FeatureCardProps {
  icon: React.ReactNode
  title: string
  accent: string
  bullets: string[]
}

function FeatureCard({ icon, title, accent, bullets }: FeatureCardProps) {
  return (
    <div className="light-card rounded-2xl p-6">
      <div className={clsx('w-11 h-11 rounded-xl flex items-center justify-center mb-4', accent)}>
        {icon}
      </div>
      <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-3">{title}</h3>
      <ul className="space-y-2">
        {bullets.map(b => (
          <li key={b} className="flex items-start gap-2 text-sm text-slate-500">
            <Check size={14} className="text-slate-400 mt-0.5 shrink-0" />
            {b}
          </li>
        ))}
      </ul>
    </div>
  )
}

const FEATURES: FeatureCardProps[] = [
  {
    icon: <Zap size={20} className="text-violet-600 dark:text-violet-400" fill="currentColor" />,
    title: 'Free Spark',
    accent: 'bg-violet-50 dark:bg-violet-500/15',
    bullets: ['5 short asks', 'No login at first', 'Mission suggestion'],
  },
  {
    icon: <Map size={20} className="text-emerald-600 dark:text-emerald-400" />,
    title: 'Capability Passport',
    accent: 'bg-emerald-50 dark:bg-emerald-500/15',
    bullets: ['Evidence + growth map', 'Not a certificate', 'Shareable with consent'],
  },
  {
    icon: <Shield size={20} className="text-blue-600 dark:text-blue-400" />,
    title: 'Parent Trust',
    accent: 'bg-blue-50 dark:bg-blue-500/15',
    bullets: ['Controls + summaries', 'No unsafe claims', 'Usage limits'],
  },
]

// ── Trusted by section ────────────────────────────────────────────────────────

function TrustRow() {
  return (
    <div className="border-t border-slate-100 dark:border-slate-800 py-10 px-4">
      <div className="max-w-3xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <p className="text-sm text-slate-400 font-medium">Trusted by curious learners</p>
        <div className="flex items-center gap-8 opacity-40 grayscale">
          {['🧠 Students', '👨‍👩‍👧 Families', '🏫 Educators', '💼 Professionals'].map(label => (
            <span key={label} className="text-sm font-medium text-slate-600 dark:text-slate-400">{label}</span>
          ))}
        </div>
        <div className="flex items-center gap-1 text-amber-400">
          {Array.from({ length: 5 }).map((_, i) => <Star key={i} size={14} fill="currentColor" />)}
          <span className="text-xs text-slate-400 ml-1">4.9 · 2k+ missions</span>
        </div>
      </div>
    </div>
  )
}

// ── Passport teaser ───────────────────────────────────────────────────────────

function PassportTeaser() {
  const navigate = useNavigate()
  return (
    <section className="px-4 py-20 bg-gradient-to-b from-slate-50 dark:from-slate-900 to-white dark:to-[#080b14]">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 mb-4 inline-block">
            Capability Passport
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-3">
            Not a certificate.<br />
            <span className="text-emerald-600 dark:text-emerald-400">Evidence of what you can do.</span>
          </h2>
          <p className="text-slate-500 max-w-lg mx-auto">
            Every mission you complete adds a verified capability to your passport — a living record of real skills, not scores.
          </p>
        </div>

        {/* Mock passport card */}
        <div className="max-w-md mx-auto light-card rounded-3xl overflow-hidden">
          <div className="bg-gradient-to-r from-violet-600 to-violet-700 px-6 py-5 flex items-center justify-between">
            <div>
              <p className="text-violet-200 text-xs font-medium">ECALT</p>
              <p className="text-white font-bold text-lg">Capability Passport</p>
            </div>
            <Map size={28} className="text-violet-300" />
          </div>
          <div className="p-6">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-4">Sample Capabilities</p>
            <div className="space-y-3">
              {[
                { icon: '🧬', title: 'DNA & Molecular Biology', tag: 'biology' },
                { icon: '🤖', title: 'Machine Learning Fundamentals', tag: 'tech' },
                { icon: '🚀', title: 'Orbital Mechanics', tag: 'physics' },
              ].map(c => (
                <div key={c.title} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/50">
                  <span className="text-xl">{c.icon}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{c.title}</p>
                    <p className="text-xs text-slate-400">#{c.tag}</p>
                  </div>
                  <div className="px-2 py-0.5 rounded-full bg-violet-50 border border-violet-100 text-violet-600 text-xs font-medium">
                    Earned
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={() => navigate('/passport')}
              className="mt-5 w-full py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
            >
              View your passport →
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const [phase, setPhase] = useState<Phase>({ kind: 'hero' })
  const [gateOpen, setGateOpen] = useState(false)
  const [gateReason, setGateReason] = useState<'mission' | 'limit'>('mission')
  const sessionId = useMemo(getSessionId, [])
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => { window.scrollTo(0, 0) }, [])

  const hasResult = phase.kind !== 'hero'

  const handleSpark = useCallback(async (question: string) => {
    setPhase({ kind: 'loading', question })
    try {
      const res = await askSpark({ question, session_id: sessionId })
      setPhase({ kind: 'sparked', question, answer: res.answer, mission: res.mission, sparksUsed: res.sparks_used, sparksRemaining: res.sparks_remaining })
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80)
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string }
      if (e.status === 429) {
        setGateReason('limit')
        setGateOpen(true)
        setPhase({ kind: 'hero' })
      } else {
        setPhase({ kind: 'error', question, message: e.message ?? 'Something went wrong.' })
      }
    }
  }, [sessionId])

  const currentMission = phase.kind === 'sparked' ? phase.mission : undefined
  const currentQuestion = phase.kind !== 'hero' ? phase.question : undefined

  return (
    <div className="bg-white dark:bg-[#080b14] min-h-screen text-slate-900 dark:text-slate-100 font-[var(--font-inter)]">
      <Navigation />

      {/* ── HERO ── */}
      <section className="relative pt-16 overflow-hidden">
        {/* Dot grid background */}
        <div className="absolute inset-0 hero-dot-grid opacity-40 pointer-events-none" />
        {/* Gradient overlay to fade dots */}
        <div className="absolute inset-0 bg-gradient-to-b from-white/30 dark:from-[#080b14]/30 via-transparent to-white dark:to-[#080b14] pointer-events-none" />
        {/* Violet glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-violet-100/60 rounded-full blur-[80px] pointer-events-none" />

        <div className="relative max-w-4xl mx-auto px-4 pt-20 pb-12 text-center">
          {/* Badge */}
          {!hasResult && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-violet-200 bg-violet-50 text-violet-700 text-xs font-semibold mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
              Mission-first AI learning platform
            </div>
          )}

          {/* Headline */}
          {hasResult ? (
            <div className="flex items-center justify-center gap-2 mb-6">
              <div className="w-6 h-6 rounded-md bg-violet-600 flex items-center justify-center">
                <Zap size={12} className="text-white" fill="currentColor" />
              </div>
              <span className="font-bold text-slate-900 dark:text-white tracking-tight">ECALT</span>
            </div>
          ) : (
            <>
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-slate-900 dark:text-white leading-[1.05] tracking-tight mb-4">
                Ask anything.<br />
                Turn curiosity into{' '}
                <span className="text-violet-600">capability.</span>
              </h1>
              <p className="text-lg text-slate-500 max-w-xl mx-auto mb-10 leading-relaxed">
                A mission-first AI learning platform for kids, families and lifelong learners.
              </p>
            </>
          )}

          {/* Ask box */}
          <div className={clsx('mx-auto transition-all duration-300', hasResult ? 'max-w-2xl' : 'max-w-2xl')}>
            <AskBox onSpark={handleSpark} loading={phase.kind === 'loading'} />
          </div>
        </div>
      </section>

      {/* ── SPARK RESULT ── */}
      <div ref={resultRef}>
        {phase.kind === 'loading' && <LightLoadingSkeleton />}

        {phase.kind === 'sparked' && (
          <LightSparkResult
            question={phase.question}
            answer={phase.answer}
            mission={phase.mission}
            sparksUsed={phase.sparksUsed}
            sparksRemaining={phase.sparksRemaining}
            onStartMission={() => { setGateReason('mission'); setGateOpen(true) }}
            onReset={() => setPhase({ kind: 'hero' })}
            onUpgrade={() => { setGateReason('limit'); setGateOpen(true) }}
          />
        )}

        {phase.kind === 'error' && (
          <div className="max-w-2xl mx-auto px-4 pb-12">
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center">
              <p className="text-rose-600 text-sm mb-3">{phase.message}</p>
              <button onClick={() => handleSpark(phase.question)} className="px-4 py-2 rounded-lg bg-rose-600 text-white text-sm font-medium hover:bg-rose-700 transition-colors">
                Try again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── BELOW FOLD (hero state only) ── */}
      {phase.kind === 'hero' && (
        <>
          {/* Trust row */}
          <TrustRow />

          {/* Feature cards */}
          <section className="px-4 py-20 max-w-5xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">
                Everything a learner needs. Nothing they don't.
              </h2>
              <p className="text-slate-500">Designed for curiosity, built for trust.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {FEATURES.map(f => <FeatureCard key={f.title} {...f} />)}
            </div>
          </section>

          {/* Capability Passport teaser */}
          <PassportTeaser />

          {/* Bottom CTA */}
          <section className="px-4 py-24 text-center">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-3">
                Start with one question.
              </h2>
              <p className="text-slate-500 mb-10">No account. No syllabus. Just curiosity.</p>
              <AskBox onSpark={handleSpark} loading={false} />
            </div>
          </section>

          {/* Footer */}
          <footer className="border-t border-slate-100 dark:border-slate-800 px-4 py-8">
            <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-slate-400">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-violet-600 flex items-center justify-center">
                  <Zap size={10} className="text-white" fill="currentColor" />
                </div>
                <span className="font-semibold text-slate-600 dark:text-slate-400">ECALT</span>
                <span>© 2025</span>
              </div>
              <div className="flex items-center gap-6">
                {['Privacy', 'Terms', 'Parents', 'Contact'].map(l => (
                  <a key={l} href="#" className="hover:text-slate-600 transition-colors">{l}</a>
                ))}
              </div>
            </div>
          </footer>
        </>
      )}

      {/* Gate modal */}
      <GateModal
        isOpen={gateOpen}
        reason={gateReason}
        mission={currentMission}
        question={currentQuestion}
        onClose={() => setGateOpen(false)}
      />
    </div>
  )
}
