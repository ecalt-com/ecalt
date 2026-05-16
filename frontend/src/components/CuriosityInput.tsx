import { useState, useEffect, useRef } from 'react'
import { Sparkles, ArrowRight, Loader2 } from 'lucide-react'

const PLACEHOLDERS = [
  'Why do stars shine?',
  'How does machine learning work?',
  'Teach me to play piano',
  'What is quantum physics?',
  'How do vaccines work?',
  'Why is the sky blue?',
  'How does the internet work?',
  'What causes earthquakes?',
]

const QUICK_PICKS = [
  { emoji: '🧬', label: 'How does DNA work?' },
  { emoji: '🤖', label: 'What is AI?' },
  { emoji: '🚀', label: 'How do rockets work?' },
  { emoji: '🎵', label: 'Music theory basics' },
  { emoji: '🌍', label: 'Why does climate change?' },
  { emoji: '💡', label: 'How does electricity work?' },
]

interface CuriosityInputProps {
  onExplore: (question: string) => void
  loading?: boolean
  initialValue?: string
}

export default function CuriosityInput({ onExplore, loading = false, initialValue = '' }: CuriosityInputProps) {
  const [query, setQuery] = useState(initialValue)
  const [phIdx, setPhIdx] = useState(0)
  const [fading, setFading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const t = setInterval(() => {
      setFading(true)
      setTimeout(() => { setPhIdx(i => (i + 1) % PLACEHOLDERS.length); setFading(false) }, 300)
    }, 3500)
    return () => clearInterval(t)
  }, [])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (!q || loading) return
    onExplore(q)
  }

  return (
    <div className="w-full space-y-4">
      <form onSubmit={submit}>
        <div className="relative group">
          <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-violet-600/40 via-cyan-500/40 to-violet-600/40 opacity-0 group-focus-within:opacity-100 blur-sm transition-opacity duration-300" />
          <div className="relative glass rounded-2xl">
            <div className="flex items-center gap-3 px-5 py-4 md:py-5">
              <Sparkles size={22} className="text-violet-400 shrink-0 group-focus-within:text-violet-300 transition-colors" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={PLACEHOLDERS[phIdx]}
                disabled={loading}
                autoFocus
                className={`flex-1 bg-transparent text-base md:text-lg text-slate-100 outline-none
                  placeholder:transition-opacity placeholder:duration-300
                  ${fading ? 'placeholder:opacity-0' : 'placeholder:opacity-100'}
                  placeholder:text-slate-600`}
              />
              <button type="submit" disabled={loading || !query.trim()} className="shrink-0 btn-primary flex items-center gap-2 py-2.5">
                {loading
                  ? <><Loader2 size={15} className="animate-spin" /><span>Mapping…</span></>
                  : <><span>Explore</span><ArrowRight size={15} /></>
                }
              </button>
            </div>
          </div>
        </div>
      </form>

      <div className="flex flex-wrap gap-2 justify-center">
        {QUICK_PICKS.map(({ emoji, label }) => (
          <button
            key={label}
            onClick={() => { setQuery(label); inputRef.current?.focus() }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm border border-slate-700/50
              bg-slate-800/30 text-slate-400 hover:text-slate-200 hover:border-violet-500/40
              hover:bg-violet-500/10 transition-all duration-200"
          >
            <span>{emoji}</span><span>{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
