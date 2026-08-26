import { useEffect, useState } from 'react'
import { Store, Loader2, Check, X, RotateCcw } from 'lucide-react'
import type { MarketplaceQueueItem } from '../types'

interface MarketplaceQueueTabProps {
  getToken: () => Promise<string | null>
}

export function MarketplaceQueueTab({ getToken }: MarketplaceQueueTabProps) {
  const [queue, setQueue] = useState<MarketplaceQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState<string | null>(null)

  const load = async () => {
    const token = await getToken()
    if (!token) return
    const res = await fetch('/api/v1/admin/marketplace-queue', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setQueue(data.queue ?? [])
    }
    setLoading(false)
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken])

  const act = async (journeyId: string, action: 'approve' | 'reject' | 'reset') => {
    setActing(journeyId)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`/api/v1/admin/marketplace-queue/${journeyId}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      // Approve/reject/reset all remove the journey from the *pending* queue view.
      if (res.ok) setQueue(prev => prev.filter(j => j.id !== journeyId))
    } finally {
      setActing(null)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 size={18} className="animate-spin text-violet-500" />
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="text-center py-12 text-xs text-slate-400">
        No journeys are currently flagged as popular. The popularity job runs every 6 hours.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <Store size={14} className="text-violet-500" />
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
          Marketplace Review Queue ({queue.length})
        </h2>
      </div>

      <div className="glass-card rounded-xl divide-y divide-slate-100 dark:divide-slate-700/40 overflow-hidden">
        {queue.map(j => (
          <div key={j.id} className="px-5 py-3 flex items-center gap-3">
            {j.icon && <span className="text-xl shrink-0">{j.icon}</span>}
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{j.title}</p>
              <p className="text-xs text-slate-400 truncate">{j.description}</p>
            </div>
            <span className="text-xs text-slate-400 shrink-0 hidden sm:block">{j.difficulty ?? '—'}</span>
            <span className="text-xs tabular-nums text-slate-500 shrink-0">❤ {j.like_count}</span>
            <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 shrink-0 w-14 text-right">
              score {j.popularity_score}
            </span>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => act(j.id, 'approve')}
                disabled={acting === j.id}
                title="Publish to marketplace"
                className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/10 transition-colors disabled:opacity-40"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => act(j.id, 'reject')}
                disabled={acting === j.id}
                title="Reject"
                className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10 transition-colors disabled:opacity-40"
              >
                <X size={14} />
              </button>
              <button
                onClick={() => act(j.id, 'reset')}
                disabled={acting === j.id}
                title="Send back to private"
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors disabled:opacity-40"
              >
                {acting === j.id ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
