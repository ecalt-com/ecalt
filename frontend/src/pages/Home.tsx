import { useNavigate } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import Navigation from '../components/Navigation'
import CuriosityInput from '../components/CuriosityInput'
import JourneyCard from '../components/JourneyCard'
import type { Journey } from '../lib/types'

const FEATURED: Pick<Journey, 'id' | 'title' | 'description' | 'icon' | 'difficulty' | 'tags' | 'estimated_hours' | 'steps'>[] = [
  { id: 'journey-dna',     title: 'The Code of Life: DNA Decoded',         description: 'From double helix to protein factories — unlock the molecular language that makes you, you.',       icon: '🧬', difficulty: 'beginner',     estimated_hours: 3,   tags: ['biology', 'genetics'],   steps: Array(10).fill(null) },
  { id: 'journey-ml',      title: 'How Machines Actually Learn',            description: 'Strip away the hype — understand the math, patterns, and intuition behind AI with zero jargon.',   icon: '🤖', difficulty: 'intermediate', estimated_hours: 4,   tags: ['AI', 'math'],            steps: Array(12).fill(null) },
  { id: 'journey-rockets', title: 'From Gunpowder to Orbit',               description: "Newton's laws meet engineering — why rockets can escape Earth's gravity.",                          icon: '🚀', difficulty: 'beginner',     estimated_hours: 2.5, tags: ['physics', 'space'],      steps: Array(8).fill(null) },
  { id: 'journey-music',   title: 'Music Theory Without the Boring Parts', description: 'Why do minor chords feel sad? Discover the physics of musical beauty.',                             icon: '🎵', difficulty: 'beginner',     estimated_hours: 3,   tags: ['music', 'creativity'],   steps: Array(9).fill(null) },
  { id: 'journey-climate', title: 'Why Does Climate Change?',              description: 'Atmospheric physics, feedback loops, and what the data says — no politics, just science.',          icon: '🌍', difficulty: 'intermediate', estimated_hours: 3.5, tags: ['climate', 'science'],    steps: Array(11).fill(null) },
  { id: 'journey-finance', title: 'Money: How It Actually Works',          description: 'Interest, inflation, investing — the financial literacy school never taught you.',                   icon: '💰', difficulty: 'beginner',     estimated_hours: 2,   tags: ['finance', 'life skills'],steps: Array(7).fill(null) },
]

const HOW = [
  { num: '01', title: 'Ask Anything',         desc: 'Type your question in plain language — no syllabi, no categories.',                              grad: 'from-violet-500/20 to-violet-500/5', border: 'border-violet-500/20', color: 'text-violet-400' },
  { num: '02', title: 'AI Maps Your Journey', desc: "ECALT's AI breaks your question into a step-by-step capability path adapted to your level.",     grad: 'from-cyan-500/20 to-cyan-500/5',    border: 'border-cyan-500/20',   color: 'text-cyan-400' },
  { num: '03', title: 'Explore & Discover',   desc: 'Work through guided concepts, practices, and challenges — at your own pace, on any device.',     grad: 'from-amber-500/20 to-amber-500/5',  border: 'border-amber-500/20',  color: 'text-amber-400' },
]

export default function Home() {
  const navigate = useNavigate()
  const go = (q: string) => navigate(`/explore?q=${encodeURIComponent(q)}`)

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Animated orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/5 w-[500px] h-[500px] bg-violet-600/8 rounded-full blur-[120px] animate-glow-pulse" />
        <div className="absolute bottom-1/4 right-1/5 w-[400px] h-[400px] bg-cyan-500/8 rounded-full blur-[120px] animate-glow-pulse" style={{ animationDelay: '1.5s' }} />
        <div className="absolute top-2/3 left-1/2 w-[300px] h-[300px] bg-amber-500/5 rounded-full blur-[100px] animate-glow-pulse" style={{ animationDelay: '3s' }} />
      </div>

      <Navigation />

      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-screen px-4 py-28 text-center">
        <div className="animate-in mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-violet-500/30 bg-violet-500/8 text-violet-300 text-sm font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
          AI-Powered Learning for Every Mind
        </div>

        <h1 className="animate-in delay-100 text-5xl md:text-7xl lg:text-8xl font-bold leading-[1.05] tracking-tight mb-6 max-w-4xl" style={{ opacity: 0 }}>
          Turn curiosity<br />
          <span className="gradient-text">into capability</span>
        </h1>

        <p className="animate-in delay-200 text-lg md:text-xl text-slate-400 max-w-xl mb-12 leading-relaxed" style={{ opacity: 0 }}>
          Ask anything. ECALT&apos;s AI maps your question into a personalized learning journey —{' '}
          <em className="text-slate-300 not-italic">one discovery at a time.</em>
        </p>

        <div className="animate-in delay-300 w-full max-w-2xl" style={{ opacity: 0 }}>
          <CuriosityInput onExplore={go} />
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-slate-700 animate-float">
          <ChevronDown size={22} />
        </div>
      </section>

      {/* Trending */}
      <section className="relative px-4 py-24 max-w-7xl mx-auto">
        <div className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold mb-3">Trending Discoveries</h2>
          <p className="text-slate-500">Journeys that curious minds are exploring right now</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURED.map(j => <JourneyCard key={j.id} journey={j} />)}
        </div>
      </section>

      {/* How it works */}
      <section className="relative px-4 py-24 max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-3">How ECALT Works</h2>
          <p className="text-slate-500">Three steps from question to capability</p>
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

      {/* CTA */}
      <section className="relative px-4 py-24 text-center">
        <div className="max-w-2xl mx-auto glass rounded-3xl p-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to start your first journey?</h2>
          <p className="text-slate-500 mb-8">No account needed. Just ask your first question.</p>
          <CuriosityInput onExplore={go} />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/50 px-4 py-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-slate-600">
          <div className="flex items-center gap-2 font-semibold">
            <span className="gradient-text">ECALT</span>
            <span>© 2025</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-slate-400 transition-colors">Privacy</a>
            <a href="#" className="hover:text-slate-400 transition-colors">Terms</a>
            <a href="#" className="hover:text-slate-400 transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
