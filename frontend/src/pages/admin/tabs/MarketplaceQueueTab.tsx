import { useEffect, useState } from 'react'
import { Store, Loader2, Check, X, RotateCcw, Search } from 'lucide-react'
import clsx from 'clsx'
import type { MarketplaceQueueItem } from '../types'

interface MarketplaceQueueTabProps {
  getToken: () => Promise<string | null>
}

const STATUS_BADGE: Record<string, string> = {
  private:         'text-slate-500 bg-slate-100 dark:bg-slate-700/50',
  pending_review:  'text-amber-700 bg-amber-50 dark:text-amber-400 dark:bg-amber-400/10',
  published:       'text-emerald-700 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-400/10',
  rejected:        'text-rose-700 bg-rose-50 dark:text-rose-400 dark:bg-rose-400/10',
}

export function MarketplaceQueueTab({ getToken }: MarketplaceQueueTabProps) {
  const [view, setView] = useState<'pending_review' | 'all'>('pending_review')
  const [search, setSearch] = useState('')
  const [queue, setQueue] = useState<MarketplaceQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState<string | null>(null)

  const load = async (status: 'pending_review' | 'all', searchTerm: string) => {
    setLoading(true)
    const token = await getToken()
    if (!token) return
    const params = new URLSearchParams({ status })
    if (status === 'all' && searchTerm) params.set('search', searchTerm)
    const res = await fetch(`/api/v1/admin/marketplace-queue?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setQueue(data.queue ?? [])
    }
    setLoading(false)
  }

  useEffect(() => {
    load(view, search)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, view])

  const act = async (journeyId: string, action: 'approve' | 'reject' | 'reset') => {
    setActing(journeyId)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`/api/v1/admin/marketplace-queue/${journeyId}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return
      const updated = await res.json()
      if (view === 'pending_review') {
        // The pending view only ever shows pending_review journeys — any
        // action moves it out of that set.
        setQueue(prev => prev.filter(j => j.id !== journeyId))
      } else {
        setQueue(prev => prev.map(j => j.id === journeyId ? { ...j, marketplace_status: updated.marketplace_status } : j))
      }
    } finally {
      setActing(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-2">
          <Store size={14} className="text-violet-500" />
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            Marketplace{view === 'pending_review' ? ' Review Queue' : ' — All Journeys'} ({queue.length})
          </h2>
        </div>
        <div className="flex gap-1 p-1 glass-card rounded-lg">
          <button
            onClick={() => setView('pending_review')}
            className={clsx('px-3 py-1 rounded-md text-xs font-semibold transition-colors',
              view === 'pending_review' ? 'bg-violet-600 text-white' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400')}
          >
            Pending
          </button>
          <button
            onClick={() => setView('all')}
            className={clsx('px-3 py-1 rounded-md text-xs font-semibold transition-colors',
              view === 'all' ? 'bg-violet-600 text-white' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400')}
          >
            All journeys
          </button>
        </div>
      </div>

      {view === 'all' && (
        <p className="text-xs text-slate-400 -mt-2">
          Feature any journey directly — bypasses the popularity job entirely. Useful while real traffic is low.
        </p>
      )}

      {view === 'all' && (
        <div className="relative max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by title…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') load('all', search) }}
            className="w-full bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs pl-8 pr-3 py-1.5 rounded-lg outline-none border border-slate-200 dark:border-slate-700 focus:border-violet-400 dark:focus:border-violet-500/50"
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={18} className="animate-spin text-violet-500" />
        </div>
      ) : queue.length === 0 ? (
        <div className="text-center py-12 text-xs text-slate-400">
          {view === 'pending_review'
            ? 'No journeys are currently flagged as popular. The popularity job runs every 6 hours.'
            : 'No journeys match.'}
        </div>
      ) : (
        <div className="glass-card rounded-xl divide-y divide-slate-100 dark:divide-slate-700/40 overflow-hidden">
          {queue.map(j => (
            <div key={j.id} className="px-5 py-3 flex items-center gap-3">
              {j.icon && <span className="text-xl shrink-0">{j.icon}</span>}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{j.title}</p>
                <p className="text-xs text-slate-400 truncate">{j.description}</p>
              </div>
              {view === 'all' && (
                <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium shrink-0', STATUS_BADGE[j.marketplace_status])}>
                  {j.marketplace_status.replace('_', ' ')}
                </span>
              )}
              <span className="text-xs text-slate-400 shrink-0 hidden sm:block">{j.difficulty ?? '—'}</span>
              <span className="text-xs tabular-nums text-slate-500 shrink-0">❤ {j.like_count}</span>
              <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 shrink-0 w-16 text-right">
                score {j.popularity_score}
              </span>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => act(j.id, 'approve')}
                  disabled={acting === j.id || j.marketplace_status === 'published'}
                  title="Publish to marketplace"
                  className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/10 transition-colors disabled:opacity-30"
                >
                  <Check size={14} />
                </button>
                <button
                  onClick={() => act(j.id, 'reject')}
                  disabled={acting === j.id || j.marketplace_status === 'rejected'}
                  title="Reject"
                  className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10 transition-colors disabled:opacity-30"
                >
                  <X size={14} />
                </button>
                <button
                  onClick={() => act(j.id, 'reset')}
                  disabled={acting === j.id || j.marketplace_status === 'private'}
                  title="Send back to private"
                  className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors disabled:opacity-30"
                >
                  {acting === j.id ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
