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
import PageMeta from '../components/PageMeta'
import { askSpark, getSessionStatus, getPassport, getUserProfile, type PassportData } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
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

// ── Spark dots ────────────────────────────────────────────────────────────────
function SparkDots({ used, total = 5, size = 'sm' }: { used: number; total?: number; size?: 'sm' | 'md' }) {
  const dotCls = size === 'md' ? 'w-2.5 h-2.5' : 'w-2 h-2'
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className={clsx(dotCls, 'rounded-full transition-all duration-300',
          i < used ? 'bg-slate-300 dark:bg-slate-600' : 'bg-violet-500'
        )} />
      ))}
    </div>
  )
}

// ── Ask box ───────────────────────────────────────────────────────────────────
const CHIPS = [
  { emoji: '🤖', label: 'Build a robot' },
  { emoji: '🕳️', label: 'Explain black holes' },
  { emoji: '🎵', label: 'Make AI music' },
  { emoji: '💡', label: 'Smart night lamp' },
]

interface AskBoxProps {
  onSpark: (q: string) => void
  loading: boolean
  autoFocus?: boolean
  inputRef?: React.RefObject<HTMLInputElement>
}

function AskBox({ onSpark, loading, autoFocus = false, inputRef }: AskBoxProps) {
  const [query, setQuery] = useState('')
  const internalRef = useRef<HTMLInputElement>(null)
  const resolvedRef = inputRef ?? internalRef

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
          'focus-within:border-violet-300 dark:focus-within:border-violet-500/50 focus-within:ring-2 focus-within:ring-violet-500/15'
        )}>
          <Sparkles size={20} className="text-violet-500 dark:text-violet-400 shrink-0" />
          <input
            ref={resolvedRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="What do you want to understand or build?"
            autoFocus={autoFocus}
            disabled={loading}
            className="flex-1 bg-transparent text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 text-base outline-none"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className={clsx(
              'shrink-0 flex items-center gap-1.5 px-3 sm:px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200',
              'bg-violet-600 hover:bg-violet-700 text-white',
              'disabled:opacity-40 disabled:cursor-not-allowed'
            )}
          >
            {loading
              ? <><Loader2 size={14} className="animate-spin" /><span className="hidden sm:inline">Thinking…</span></>
              : <><span className="hidden sm:inline">Ask </span><span>ECALT</span><ArrowRight size={14} /></>
            }
          </button>
        </div>
      </form>

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

// ── Spark result ──────────────────────────────────────────────────────────────
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
  onSavePath: () => void
  onReset: () => void
  onUpgrade: () => void
}

function LightSparkResult({ question, answer, mission, sparksUsed, sparksRemaining, onStartMission, onSavePath, onReset, onUpgrade }: LightResultProps) {
  return (
    <div className="animate-in max-w-2xl mx-auto px-4 pb-20">

      {/* Answer */}
      <div className="mb-5">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-1.5">You asked</p>
        <p className="text-slate-500 italic text-sm mb-4">"{question}"</p>
        <div className="bg-violet-50 dark:bg-violet-900/20 border border-violet-100 dark:border-violet-800/40 border-l-4 border-l-violet-500 rounded-2xl p-5">
          <p className="text-slate-800 dark:text-slate-200 leading-relaxed">{answer}</p>
        </div>
      </div>

      {/* Mission CTA card */}
      <div className="light-card rounded-2xl p-5 mb-5">
        {/* "Next:" prompt */}
        <div className="flex items-start gap-2 mb-4">
          <span className="text-violet-500 mt-0.5 shrink-0">✦</span>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
            Next: Want to turn this curiosity into a{' '}
            <span className="font-bold text-slate-900 dark:text-white">{mission.estimated_minutes}-minute mission</span>?
          </p>
        </div>

        {/* Mission title preview */}
        <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/50 mb-4">
          <span className="text-2xl leading-none">{mission.icon}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-slate-900 dark:text-white leading-snug truncate">{mission.title}</p>
            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
              <span className={clsx('px-1.5 py-0.5 rounded text-xs font-medium border', DIFF_COLOR[mission.difficulty])}>
                {mission.difficulty}
              </span>
              <span className="text-xs text-slate-400">#{mission.category}</span>
              <span className="text-xs text-slate-400">· {mission.steps.length} steps</span>
            </div>
          </div>
        </div>

        {/* Two CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 mb-3">
          <button
            onClick={onStartMission}
            className="flex-1 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-1.5"
          >
            <Zap size={13} fill="currentColor" />
            Start {mission.title}
          </button>
          <button
            onClick={onSavePath}
            className="flex-1 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors flex items-center justify-center gap-1.5"
          >
            Save My Path <ArrowRight size={13} />
          </button>
        </div>

        <p className="text-xs text-slate-400 text-center">
          Save your path and continue your Capability Passport
        </p>
      </div>

      {/* Mission steps — secondary preview */}
      <div className="mb-5">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-widest mb-2">Mission path preview</p>
        <div className="space-y-2">
          {mission.steps.map((step, i) => {
            const cfg = STEP_TYPE[step.type]
            const Icon = cfg.icon
            return (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700/50">
                <div className="w-5 h-5 rounded-full bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 flex items-center justify-center text-xs font-bold text-slate-500 shrink-0">
                  {i + 1}
                </div>
                <div className={clsx('p-1 rounded-md shrink-0', cfg.bg)}>
                  <Icon size={11} className={cfg.color} />
                </div>
                <span className="text-sm text-slate-600 dark:text-slate-400 flex-1 truncate">{step.title}</span>
                <span className="text-xs text-slate-400 shrink-0">{step.minutes}m</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Spark meter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SparkDots used={sparksUsed} />
          <span className="text-xs text-slate-400 ml-0.5">
            {sparksRemaining === 0
              ? <button onClick={onUpgrade} className="text-violet-600 font-medium hover:underline">Upgrade for unlimited →</button>
              : <><span className="font-semibold text-slate-600 dark:text-slate-400">{sparksRemaining}</span> of 5 sparks left</>
            }
          </span>
        </div>
        <button onClick={onReset} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
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
      <div className="shimmer-light h-24 w-full rounded-2xl" />
      <div className="shimmer-light h-48 w-full rounded-2xl" />
      <div className="shimmer-light h-32 w-full rounded-2xl" />
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

// ── Trust row ─────────────────────────────────────────────────────────────────
function TrustRow() {
  return (
    <div className="border-t border-slate-100 dark:border-slate-800 py-10 px-4">
      <div className="max-w-3xl mx-auto flex flex-col items-center md:flex-row md:justify-between gap-4 md:gap-6">
        <p className="text-sm text-slate-400 font-medium">Trusted by curious learners</p>
        <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-8 opacity-40 grayscale">
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
type RecentJourney = PassportData['journeys'][0]

export default function Home() {
  const [phase, setPhase] = useState<Phase>({ kind: 'hero' })
  const [gateOpen, setGateOpen] = useState(false)
  const [gateReason, setGateReason] = useState<'mission' | 'limit'>('mission')
  const [sessionSparks, setSessionSparks] = useState<{ used: number; remaining: number } | null>(null)
  const [recentJourney, setRecentJourney] = useState<RecentJourney | null>(null)
  const [streakDays, setStreakDays] = useState(0)
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [waitlistDone, setWaitlistDone] = useState(false)
  const sessionId = useMemo(getSessionId, [])
  const resultRef = useRef<HTMLDivElement>(null)
  const askInputRef = useRef<HTMLInputElement>(null)
  const { user, getToken } = useAuth()
  const navigate = useNavigate()

  // restore spark count from server on mount (handles page refresh)
  useEffect(() => {
    getSessionStatus(sessionId)
      .then(s => { if (s.sparks_used > 0) setSessionSparks({ used: s.sparks_used, remaining: s.sparks_remaining }) })
      .catch(() => {})
  }, [sessionId])

  // fetch recent journey + streak when user signs in
  useEffect(() => {
    if (!user) { setRecentJourney(null); setStreakDays(0); return }
    getToken().then(token => {
      if (!token) return
      Promise.all([getPassport(token), getUserProfile(token)]).then(([passport, profile]) => {
        const inProgress = passport.journeys.filter(j => !j.fully_completed)
        setRecentJourney(inProgress[0] ?? null)
        setStreakDays(profile.streak_days ?? 0)
      }).catch(() => {})
    })
  }, [user])

  // '/' keyboard shortcut → focus the ask input
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault()
        askInputRef.current?.focus()
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const hasResult = phase.kind !== 'hero'

  const handleSpark = useCallback(async (question: string) => {
    setPhase({ kind: 'loading', question })
    try {
      const token = await getToken()
      const res = await askSpark({ question, session_id: sessionId }, token ?? undefined)
      setSessionSparks({ used: res.sparks_used, remaining: res.sparks_remaining })
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
  }, [sessionId, getToken])

  const currentMission = phase.kind === 'sparked' ? phase.mission : undefined
  const currentQuestion = phase.kind !== 'hero' ? phase.question : undefined

  const sparksUsed = sessionSparks?.used ?? 0
  const sparksRemaining = sessionSparks?.remaining ?? 5

  const homeJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'ECALT',
    url: 'https://ecalt.vercel.app',
    description: 'AI-powered personalized learning journeys for curious minds of all ages.',
    potentialAction: {
      '@type': 'SearchAction',
      target: 'https://ecalt.vercel.app/journeys?q={search_term_string}',
      'query-input': 'required name=search_term_string',
    },
  }

  return (
    <div className="bg-white dark:bg-[#080b14] min-h-screen text-slate-900 dark:text-slate-100">
      <PageMeta
        canonicalPath="/"
        jsonLd={homeJsonLd}
      />
      <Navigation />

      {/* ── CONTINUE CARD ── */}
      {recentJourney && phase.kind === 'hero' && (
        <div className="max-w-2xl mx-auto px-4 pt-24 pb-0 flex flex-col gap-2">
          <button
            onClick={() => navigate(`/journey/${recentJourney.id}`)}
            className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl border border-violet-200 dark:border-violet-800/50 bg-violet-50 dark:bg-violet-900/20 hover:border-violet-400 dark:hover:border-violet-600 transition-colors text-left group"
          >
            <span className="text-3xl shrink-0">{recentJourney.icon}</span>
            <div className="flex-1 min-w-0">
              <p className="text-[11px] font-semibold text-violet-600 dark:text-violet-400 uppercase tracking-wider mb-0.5">Continue where you left off</p>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{recentJourney.title}</p>
              <div className="mt-1.5 h-1 bg-violet-100 dark:bg-violet-900 rounded-full overflow-hidden w-40">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-cyan-500 rounded-full"
                  style={{ width: `${Math.round((recentJourney.completed_steps / recentJourney.total_steps) * 100)}%` }}
                />
              </div>
            </div>
            <ArrowRight size={16} className="text-violet-500 shrink-0 group-hover:translate-x-0.5 transition-transform" />
          </button>
          {streakDays > 1 && (
            <div className="flex items-center gap-1.5 self-end pr-1">
              <Zap size={13} className="text-amber-500" fill="currentColor" />
              <span className="text-xs font-semibold text-amber-600 dark:text-amber-400">{streakDays}-day streak</span>
            </div>
          )}
        </div>
      )}

      {/* ── HERO ── */}
      <section className="relative pt-16 overflow-hidden">
        <div className="absolute inset-0 hero-dot-grid opacity-40 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-b from-white/30 dark:from-[#080b14]/30 via-transparent to-white dark:to-[#080b14] pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-violet-100/60 dark:bg-violet-900/20 rounded-full blur-[80px] pointer-events-none" />

        <div className="relative max-w-4xl mx-auto px-4 pt-20 pb-12 text-center">

          {/* Session header — shown only in hero state */}
          {!hasResult && (
            <>
              {sessionSparks ? (
                /* After at least one spark — show live counter */
                <div className="inline-flex flex-col items-center gap-2 mb-8">
                  <div className="flex items-center gap-2.5 px-4 py-2 rounded-full border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/30">
                    <SparkDots used={sparksUsed} />
                    <span className="text-sm font-medium text-violet-700 dark:text-violet-300">
                      You have <strong>{sparksRemaining}</strong> of 5 free sparks left
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">Short Haiku responses only · Create account to save path</p>
                </div>
              ) : (
                /* First visit — session intro badge */
                <div className="inline-flex flex-col items-center gap-2 mb-8">
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 text-xs font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
                    Free Curiosity Session · 5 sparks included
                  </div>
                  <p className="text-xs text-slate-400">Short Haiku responses only · No sign-up needed</p>
                </div>
              )}
            </>
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
              <h1 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-bold text-slate-900 dark:text-white leading-[1.05] tracking-tight mb-4">
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
          <div className="max-w-2xl mx-auto">
            <AskBox onSpark={handleSpark} loading={phase.kind === 'loading'} autoFocus inputRef={askInputRef} />
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
            onSavePath={() => { setGateReason('mission'); setGateOpen(true) }}
            onReset={() => setPhase({ kind: 'hero' })}
            onUpgrade={() => { setGateReason('limit'); setGateOpen(true) }}
          />
        )}

        {phase.kind === 'error' && (
          <div className="max-w-2xl mx-auto px-4 pb-12">
            <div className="bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800/40 rounded-2xl p-6 text-center">
              <p className="text-rose-600 dark:text-rose-400 text-sm mb-3">{phase.message}</p>
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
          <TrustRow />

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

          <PassportTeaser />

          <section className="px-4 py-24 text-center">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-3">
                Start with one question.
              </h2>
              <p className="text-slate-500 mb-10">No account. No syllabus. Just curiosity.</p>
              <AskBox onSpark={handleSpark} loading={false} />
            </div>
          </section>

          {/* ── EMAIL CAPTURE ── */}
          {!user && (
            <section className="px-4 pb-20">
              <div className="max-w-lg mx-auto text-center">
                <div className="bg-gradient-to-br from-violet-50 to-cyan-50 dark:from-violet-900/20 dark:to-cyan-900/20 border border-violet-100 dark:border-violet-800/40 rounded-3xl p-8">
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Stay in the loop</p>
                  <p className="text-slate-500 text-sm mb-6">New journeys, features, and learning ideas — one email a week, no spam.</p>
                  {waitlistDone ? (
                    <div className="flex items-center justify-center gap-2 text-emerald-600 dark:text-emerald-400 font-medium">
                      <Check size={16} />
                      You're on the list!
                    </div>
                  ) : (
                    <form
                      onSubmit={e => {
                        e.preventDefault()
                        if (waitlistEmail.trim()) setWaitlistDone(true)
                      }}
                      className="flex gap-2"
                    >
                      <input
                        type="email"
                        required
                        value={waitlistEmail}
                        onChange={e => setWaitlistEmail(e.target.value)}
                        placeholder="you@example.com"
                        className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-violet-500/30"
                      />
                      <button
                        type="submit"
                        className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-colors shrink-0"
                      >
                        Subscribe
                      </button>
                    </form>
                  )}
                </div>
              </div>
            </section>
          )}

          <footer className="border-t border-slate-100 dark:border-slate-800 px-4 py-8">
            <div className="max-w-6xl mx-auto flex flex-col items-center md:flex-row md:justify-between gap-4 text-sm text-slate-400">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-violet-600 flex items-center justify-center">
                  <Zap size={10} className="text-white" fill="currentColor" />
                </div>
                <span className="font-semibold text-slate-600 dark:text-slate-400">ECALT</span>
                <span>© {new Date().getFullYear()}</span>
              </div>
              <div className="flex items-center gap-6">
                {['Privacy', 'Terms', 'Parents', 'Contact'].map(l => (
                  <a key={l} href="#" className="hover:text-slate-600 dark:hover:text-slate-300 transition-colors">{l}</a>
                ))}
              </div>
            </div>
          </footer>
        </>
      )}

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
