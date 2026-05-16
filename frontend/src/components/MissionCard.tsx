import { Clock, BookOpen, Zap, Wrench, Compass } from 'lucide-react'
import clsx from 'clsx'
import type { Mission, StepType } from '../lib/types'

const TYPE_CONFIG: Record<StepType, { icon: React.ElementType; color: string; label: string }> = {
  concept:   { icon: BookOpen, color: 'text-violet-400', label: 'Learn' },
  practice:  { icon: Wrench,   color: 'text-cyan-400',   label: 'Practice' },
  challenge: { icon: Zap,      color: 'text-amber-400',  label: 'Challenge' },
  explore:   { icon: Compass,  color: 'text-emerald-400',label: 'Explore' },
}

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner:     'text-emerald-400 border-emerald-400/25 bg-emerald-400/8',
  intermediate: 'text-amber-400 border-amber-400/25 bg-amber-400/8',
  advanced:     'text-rose-400 border-rose-400/25 bg-rose-400/8',
}

interface MissionCardProps {
  mission: Mission
  onStart: () => void
}

export default function MissionCard({ mission, onStart }: MissionCardProps) {
  return (
    <div className="animate-in delay-200 glass-card rounded-2xl overflow-hidden" style={{ opacity: 0 }}>
      {/* Header */}
      <div className="p-6 pb-4">
        <div className="flex items-start gap-4 mb-3">
          <span className="text-4xl leading-none">{mission.icon}</span>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className={clsx('px-2.5 py-0.5 rounded-full text-xs font-medium border', DIFFICULTY_COLOR[mission.difficulty])}>
                {mission.difficulty}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs border border-slate-700 bg-slate-800/50 text-slate-500">
                #{mission.category}
              </span>
              <span className="flex items-center gap-1 text-xs text-slate-600">
                <Clock size={11} />{mission.estimated_minutes} min
              </span>
            </div>
            <h3 className="text-lg font-bold text-slate-100 leading-snug">{mission.title}</h3>
          </div>
        </div>
        <p className="text-sm text-slate-400 leading-relaxed">{mission.tagline}</p>
      </div>

      {/* Steps */}
      <div className="px-6 pb-5">
        <p className="text-xs text-slate-600 uppercase tracking-widest mb-3">Mission Path</p>
        <div className="space-y-2">
          {mission.steps.map((step, i) => {
            const cfg = TYPE_CONFIG[step.type]
            const Icon = cfg.icon
            return (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/40 border border-slate-800/40">
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-slate-800 text-slate-500 text-xs font-bold shrink-0">
                  {i + 1}
                </div>
                <Icon size={13} className={clsx(cfg.color, 'shrink-0')} />
                <span className="text-sm text-slate-300 flex-1 leading-snug">{step.title}</span>
                <span className="text-xs text-slate-700 shrink-0">{step.minutes}m</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* CTA */}
      <div className="px-6 pb-6">
        <button
          onClick={onStart}
          className="w-full py-3 rounded-xl font-semibold text-sm transition-all duration-200
            bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400
            text-white flex items-center justify-center gap-2 group"
        >
          <Zap size={15} fill="currentColor" />
          Start This Mission
          <span className="opacity-50 group-hover:opacity-80 transition-opacity text-xs">→</span>
        </button>
      </div>
    </div>
  )
}
