import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Award, BookOpen, Flame, ArrowRight } from 'lucide-react'
import Navigation from '../components/Navigation'
import type { CapabilityEntry } from '../lib/types'

function loadCapabilities(): CapabilityEntry[] {
  try {
    return JSON.parse(localStorage.getItem('ecalt_capabilities') || '[]')
  } catch {
    return []
  }
}

export default function Passport() {
  const navigate = useNavigate()
  const [capabilities, setCapabilities] = useState<CapabilityEntry[]>([])
  const [streak] = useState(0)

  useEffect(() => {
    setCapabilities(loadCapabilities())
  }, [])

  const categories = [...new Set(capabilities.map(c => c.category))]

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[400px] h-[400px] bg-violet-600/6 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative min-h-screen pt-28 pb-20 px-4 max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-10">
          <div>
            <p className="text-xs text-slate-600 uppercase tracking-widest mb-2">ECALT</p>
            <h1 className="text-3xl font-bold mb-1">Capability Passport</h1>
            <p className="text-slate-500 text-sm">Your verified learning record</p>
          </div>
          <div className="glass rounded-2xl px-5 py-4 text-center">
            <div className="flex items-center gap-1.5 text-amber-400 mb-1">
              <Flame size={14} />
              <span className="text-xs font-medium">Streak</span>
            </div>
            <p className="text-2xl font-bold text-white">{streak}</p>
            <p className="text-xs text-slate-600">days</p>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-10">
          {[
            { label: 'Missions Complete', value: capabilities.length, icon: Award, color: 'text-violet-400' },
            { label: 'Topics Explored',   value: categories.length,   icon: BookOpen, color: 'text-cyan-400' },
            { label: 'Hours Invested',    value: capabilities.length * 1.5, icon: Flame, color: 'text-amber-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="glass-card rounded-2xl p-5 text-center">
              <Icon size={18} className={`${color} mx-auto mb-2`} />
              <p className="text-2xl font-bold">{Number.isInteger(value) ? value : value.toFixed(1)}</p>
              <p className="text-xs text-slate-600 mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* Capabilities */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-xs text-slate-600 uppercase tracking-widest">Capabilities Earned</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>

          {capabilities.length === 0 ? (
            <div className="glass-card rounded-2xl p-12 text-center">
              <div className="text-5xl mb-4">🗺️</div>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">No capabilities yet</h3>
              <p className="text-sm text-slate-500 mb-6 max-w-xs mx-auto">
                Complete your first mission to earn a capability badge and start building your passport.
              </p>
              <button
                onClick={() => navigate('/')}
                className="btn-primary flex items-center gap-2 mx-auto"
              >
                Start a mission <ArrowRight size={14} />
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {capabilities.map((cap, i) => (
                <div key={i} className="glass-card rounded-2xl p-5 flex items-center gap-4">
                  <span className="text-3xl">{cap.icon}</span>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-slate-200">{cap.missionTitle}</p>
                    <p className="text-xs text-slate-600 mt-0.5">
                      #{cap.category} · {new Date(cap.completedAt).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="px-3 py-1 rounded-full text-xs border border-violet-500/30 bg-violet-500/10 text-violet-300 font-medium">
                    Earned
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Topic cloud */}
        {categories.length > 0 && (
          <div>
            <p className="text-xs text-slate-600 uppercase tracking-widest mb-3">Topics Explored</p>
            <div className="flex flex-wrap gap-2">
              {categories.map(c => (
                <span key={c} className="px-3 py-1.5 rounded-full text-sm border border-slate-700 bg-slate-800/50 text-slate-400">
                  #{c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
