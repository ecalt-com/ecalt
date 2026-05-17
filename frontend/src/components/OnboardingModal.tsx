import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import { completeOnboarding } from '../lib/api'

const TOPICS = [
  { emoji: '🧬', label: 'Biology' },
  { emoji: '⚛️', label: 'Physics' },
  { emoji: '🤖', label: 'AI & Tech' },
  { emoji: '🧮', label: 'Math' },
  { emoji: '🚀', label: 'Space' },
  { emoji: '💰', label: 'Finance' },
  { emoji: '🎵', label: 'Music' },
  { emoji: '🌍', label: 'Climate' },
  { emoji: '🏛️', label: 'History' },
  { emoji: '🧠', label: 'Psychology' },
  { emoji: '⚙️', label: 'Engineering' },
  { emoji: '🎨', label: 'Arts' },
]

export default function OnboardingModal() {
  const navigate = useNavigate()
  const { getToken, dismissOnboarding } = useAuth()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)

  const toggle = (label: string) =>
    setSelected(prev => {
      const next = new Set(prev)
      next.has(label) ? next.delete(label) : next.add(label)
      return next
    })

  const handleStart = async () => {
    setSaving(true)
    try {
      const token = await getToken()
      if (token) {
        const topics = Array.from(selected).map(t => t.toLowerCase())
        await Promise.allSettled([
          completeOnboarding(token),
          selected.size > 0
            ? fetch('/api/v1/users/me/interests', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({ topics }),
              })
            : Promise.resolve(),
        ])
      }
    } catch { /* non-critical */ } finally {
      dismissOnboarding()
      navigate('/learn')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="animate-celebration glass-card rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-4xl mb-3">✦</div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">What sparks your curiosity?</h2>
          <p className="text-sm text-slate-500">Pick the topics you'd like to explore — we'll tailor your journeys.</p>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-6">
          {TOPICS.map(({ emoji, label }) => (
            <button
              key={label}
              onClick={() => toggle(label)}
              className={clsx(
                'flex flex-col items-center gap-1 py-3 px-2 rounded-xl border text-xs font-medium transition-all duration-150',
                selected.has(label)
                  ? 'border-violet-400 bg-violet-50 text-violet-700 dark:border-violet-500/60 dark:bg-violet-500/15 dark:text-violet-300'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-violet-300 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400 dark:hover:border-violet-500/40'
              )}
            >
              <span className="text-xl leading-none">{emoji}</span>
              {label}
            </button>
          ))}
        </div>

        <button
          onClick={handleStart}
          disabled={saving}
          className="w-full btn-primary flex items-center justify-center gap-2"
        >
          {saving
            ? <><Loader2 size={14} className="animate-spin" />Saving…</>
            : <>Start exploring <ArrowRight size={14} /></>}
        </button>

        <button
          onClick={handleStart}
          className="w-full mt-2 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-1 transition-colors"
        >
          Skip for now
        </button>
      </div>
    </div>
  )
}
