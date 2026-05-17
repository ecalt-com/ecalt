import { useEffect, useState } from 'react'
import { Sparkles, ArrowRight, Loader2 } from 'lucide-react'
import { useAuth } from '../../lib/AuthContext'

interface TodaysSparkProps {
  onSelect: (prompt: string) => void
}

export default function TodaysSpark({ onSelect }: TodaysSparkProps) {
  const { getToken } = useAuth()
  const [spark, setSpark] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function fetchSpark() {
      try {
        const token = await getToken()
        if (!token) return
        const res = await fetch('/api/v1/knowledge/spark', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok || cancelled) return
        const data = await res.json()
        setSpark(data.spark)
      } catch {
        // fail silently — spark is not critical
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchSpark()
    return () => { cancelled = true }
  }, [getToken])

  return (
    <div className="h-full flex flex-col p-4">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={14} className="text-amber-400" />
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Today's spark
        </span>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={16} className="text-slate-500 animate-spin" />
        </div>
      ) : spark ? (
        <div className="flex-1 flex flex-col justify-between">
          <p className="text-sm leading-relaxed text-slate-300 font-light">{spark}</p>
          <button
            onClick={() => onSelect(spark)}
            className="mt-4 flex items-center gap-2 text-xs text-violet-400 hover:text-violet-300 transition-colors group"
          >
            <span>Start exploring</span>
            <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
          </button>
        </div>
      ) : (
        <p className="text-xs text-slate-500 italic">Ask anything to begin your learning journey.</p>
      )}

      <div className="mt-6 pt-4 border-t border-white/5">
        <p className="text-xs text-slate-600">
          Personalized from your interests · refreshes daily
        </p>
      </div>
    </div>
  )
}
