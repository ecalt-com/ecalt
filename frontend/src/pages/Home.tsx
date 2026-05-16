import { useState, useMemo, useRef, useCallback } from 'react'
import { ChevronDown } from 'lucide-react'
import Navigation from '../components/Navigation'
import CuriosityInput from '../components/CuriosityInput'
import JourneyCard from '../components/JourneyCard'
import SparkAnswer from '../components/SparkAnswer'
import MissionCard from '../components/MissionCard'
import GateModal from '../components/GateModal'
import SparkMeter from '../components/SparkMeter'
import { askSpark } from '../lib/api'
import type { Mission, Journey } from '../lib/types'

// ── Session ID (persisted across reloads, resets with cache clear) ────────────
function getSessionId(): string {
  let id = localStorage.getItem('ecalt_sid') || ''
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('ecalt_sid', id)
  }
  return id
}

// ── Types ─────────────────────────────────────────────────────────────────────
type Phase =
  | { kind: 'hero' }
  | { kind: 'loading'; question: string }
  | { kind: 'sparked'; question: string; answer: string; mission: Mission; sparksUsed: number; sparksRemaining: number }
  | { kind: 'error'; question: string; message: string }

// ── Static data ───────────────────────────────────────────────────────────────
const FEATURED: Pick<Journey, 'id' | 'title' | 'description' | 'icon' | 'difficulty' | 'tags' | 'estimated_hours' | 'steps'>[] = [
  { id: 'journey-dna',     title: 'The Code of Life: DNA Decoded',         description: 'From double helix to protein factories — unlock the molecular language that makes you, you.',       icon: '🧬', difficulty: 'beginner',     estimated_hours: 3,   tags: ['biology', 'genetics'],   steps: Array(10).fill(null) },
  { id: 'journey-ml',      title: 'How Machines Actually Learn',            description: 'Strip away the hype — understand the math, patterns, and intuition behind AI with zero jargon.',   icon: '🤖', difficulty: 'intermediate', estimated_hours: 4,   tags: ['AI', 'math'],            steps: Array(12).fill(null) },
  { id: 'journey-rockets', title: 'From Gunpowder to Orbit',               description: "Newton's laws meet engineering — why rockets can escape Earth's gravity.",                          icon: '🚀', difficulty: 'beginner',     estimated_hours: 2.5, tags: ['physics', 'space'],      steps: Array(8).fill(null) },
  { id: 'journey-music',   title: 'Music Theory Without the Boring Parts', description: 'Why do minor chords feel sad? Discover the physics of musical beauty.',                             icon: '🎵', difficulty: 'beginner',     estimated_hours: 3,   tags: ['music', 'creativity'],   steps: Array(9).fill(null) },
  { id: 'journey-climate', title: 'Why Does Climate Change?',              description: 'Atmospheric physics, feedback loops, and what the data says — no politics, just science.',          icon: '🌍', difficulty: 'intermediate', estimated_hours: 3.5, tags: ['climate', 'science'],    steps: Array(11).fill(null) },
  { id: 'journey-finance', title: 'Money: How It Actually Works',          description: 'Interest, inflation, investing — the financial literacy school never taught you.',                   icon: '💰', difficulty: 'beginner',     estimated_hours: 2,   tags: ['finance', 'life skills'],steps: Array(7).fill(null) },
]

const HOW = [
  { num: '01', title: 'Ask Anything',         desc: 'Type any question. ECALT gives you a vivid answer instantly — no sign-up needed.',                       grad: 'from-violet-500/20 to-violet-500/5', border: 'border-violet-500/20', color: 'text-violet-400' },
  { num: '02', title: 'Get Your Mission',     desc: 'AI proposes a personalized 4-5 step learning path built around your exact question.',                    grad: 'from-cyan-500/20 to-cyan-500/5',    border: 'border-cyan-500/20',   color: 'text-cyan-400' },
  { num: '03', title: 'Earn Capabilities',    desc: 'Complete steps, earn verified capability badges, and build your Capability Passport over time.',          grad: 'from-amber-500/20 to-amber-500/5',  border: 'border-amber-500/20',  color: 'text-amber-400' },
]

// ── Component ─────────────────────────────────────────────────────────────────
export default function Home() {
  const [phase, setPhase] = useState<Phase>({ kind: 'hero' })
  const [gateOpen, setGateOpen] = useState(false)
  const [gateReason, setGateReason] = useState<'mission' | 'limit'>('mission')
  const sessionId = useMemo(getSessionId, [])
  const resultRef = useRef<HTMLDivElement>(null)

  const hasResult = phase.kind === 'sparked' || phase.kind === 'loading'

  const handleSpark = useCallback(async (question: string) => {
    setPhase({ kind: 'loading', question })
    try {
      const res = await askSpark({ question, session_id: sessionId })
      setPhase({
        kind: 'sparked',
        question,
        answer: res.answer,
        mission: res.mission,
        sparksUsed: res.sparks_used,
        sparksRemaining: res.sparks_remaining,
      })
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80)
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string }
      if (e.status === 429) {
        setGateReason('limit')
        setGateOpen(true)
        setPhase({ kind: 'hero' })
      } else {
        setPhase({ kind: 'error', question, message: e.message ?? 'Something went wrong. Try again.' })
      }
    }
  }, [sessionId])

  const openMissionGate = () => {
    setGateReason('mission')
    setGateOpen(true)
  }

  const currentMission = phase.kind === 'sparked' ? phase.mission : undefined
  const currentQuestion = phase.kind === 'sparked' || phase.kind === 'loading' || phase.kind === 'error' ? phase.question : undefined

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/5 w-[500px] h-[500px] bg-violet-600/8 rounded-full blur-[120px] animate-glow-pulse" />
        <div className="absolute bottom-1/4 right-1/5 w-[400px] h-[400px] bg-cyan-500/8 rounded-full blur-[120px] animate-glow-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      <Navigation />

      {/* ── HERO / INPUT ── */}
      <section
        className={`relative flex flex-col items-center px-4 text-center transition-all duration-500
          ${hasResult ? 'pt-24 pb-10 justify-start' : 'min-h-screen pt-28 pb-20 justify-center'}`}
      >
        {/* Badge — only on hero */}
        {!hasResult && (
          <div className="animate-in mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-violet-500/30 bg-violet-500/8 text-violet-300 text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            AI-Powered Learning for Every Mind
          </div>
        )}

        {/* Headline */}
        {hasResult ? (
          <span className="gradient-text font-bold text-2xl tracking-tight mb-6">ECALT</span>
        ) : (
          <>
            <h1 className="animate-in delay-100 text-5xl md:text-7xl lg:text-8xl font-bold leading-[1.05] tracking-tight mb-6 max-w-4xl" style={{ opacity: 0 }}>
              Turn curiosity<br />
              <span className="gradient-text">into capability</span>
            </h1>
            <p className="animate-in delay-200 text-lg md:text-xl text-slate-400 max-w-xl mb-12 leading-relaxed" style={{ opacity: 0 }}>
              Ask anything. ECALT&apos;s AI maps your question into a personalized learning journey —{' '}
              <em className="text-slate-300 not-italic">one discovery at a time.</em>
            </p>
          </>
        )}

        {/* Input */}
        <div className={`w-full transition-all duration-300 ${hasResult ? 'max-w-2xl' : 'max-w-2xl animate-in delay-300'}`} style={hasResult ? undefined : { opacity: 0 }}>
          <CuriosityInput
            onExplore={handleSpark}
            loading={phase.kind === 'loading'}
          />
        </div>

        {/* Spark meter — shown after first spark */}
        {phase.kind === 'sparked' && (
          <SparkMeter
            used={phase.sparksUsed}
            total={5}
            onUpgrade={() => { setGateReason('limit'); setGateOpen(true) }}
          />
        )}

        {/* Scroll cue — hero only */}
        {!hasResult && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-slate-700 animate-float">
            <ChevronDown size={22} />
          </div>
        )}
      </section>

      {/* ── SPARK RESULT ── */}
      <div ref={resultRef}>
        {phase.kind === 'loading' && (
          <section className="max-w-2xl mx-auto px-4 pb-20 space-y-5">
            <div className="shimmer-bg h-5 w-1/3 rounded-lg" />
            <div className="shimmer-bg h-4 w-2/3 rounded-lg" />
            <div className="shimmer-bg h-28 w-full rounded-2xl" />
            <div className="shimmer-bg h-64 w-full rounded-2xl" />
            <p className="text-center text-xs text-slate-700 animate-pulse">✦ Sparking your curiosity…</p>
          </section>
        )}

        {phase.kind === 'sparked' && (
          <section className="max-w-2xl mx-auto px-4 pb-24">
            <SparkAnswer question={phase.question} answer={phase.answer} />
            <MissionCard mission={phase.mission} onStart={openMissionGate} />

            <button
              onClick={() => setPhase({ kind: 'hero' })}
              className="mt-6 text-xs text-slate-600 hover:text-slate-400 transition-colors mx-auto block"
            >
              ↑ Ask another question
            </button>
          </section>
        )}

        {phase.kind === 'error' && (
          <section className="max-w-2xl mx-auto px-4 pb-20">
            <div className="glass rounded-2xl p-6 border border-rose-500/20 text-center">
              <p className="text-rose-400 text-sm mb-3">{phase.message}</p>
              <button onClick={() => handleSpark(phase.question)} className="btn-primary text-sm py-2 px-4">
                Try again
              </button>
            </div>
          </section>
        )}
      </div>

      {/* ── TRENDING (hero only) ── */}
      {phase.kind === 'hero' && (
        <>
          <section className="relative px-4 py-24 max-w-7xl mx-auto">
            <div className="text-center mb-14">
              <h2 className="text-3xl md:text-4xl font-bold mb-3">Trending Discoveries</h2>
              <p className="text-slate-500">Journeys that curious minds are exploring right now</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {FEATURED.map(j => <JourneyCard key={j.id} journey={j} />)}
            </div>
          </section>

          <section className="relative px-4 py-24 max-w-5xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-3">How ECALT Works</h2>
              <p className="text-slate-500">From curiosity to capability in three steps</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {HOW.map(({ num, title, desc, grad, border, color }) => (
                <div key={num} className={`rounded-2xl p-6 bg-gradient-to-b ${grad} border ${border}`}>
                  <div className={`text-5xl font-bold mb-4 ${color} opacity-60`}>{num}</div>
                  <h3 className="text-lg font-semibold text-slate-100 mb-2">{title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="relative px-4 py-24 text-center">
            <div className="max-w-2xl mx-auto glass rounded-3xl p-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to start?</h2>
              <p className="text-slate-500 mb-8">No account needed. Ask your first question.</p>
              <CuriosityInput onExplore={handleSpark} loading={false} />
            </div>
          </section>

          <footer className="border-t border-slate-800/50 px-4 py-8">
            <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-slate-600">
              <div className="flex items-center gap-2 font-semibold"><span className="gradient-text">ECALT</span><span>© 2025</span></div>
              <div className="flex items-center gap-6">
                <a href="#" className="hover:text-slate-400 transition-colors">Privacy</a>
                <a href="#" className="hover:text-slate-400 transition-colors">Terms</a>
                <a href="#" className="hover:text-slate-400 transition-colors">Contact</a>
              </div>
            </div>
          </footer>
        </>
      )}

      {/* ── GATE MODAL ── */}
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
