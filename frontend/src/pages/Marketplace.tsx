import { useState, useEffect, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import Navigation from '../components/Navigation'
import MarketplaceCard from '../components/MarketplaceCard'
import PageMeta from '../components/PageMeta'
import { getMarketplace } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import type { Journey } from '../lib/types'

const FILTERS = ['All', 'Beginner', 'Intermediate', 'Advanced']
const PAGE_SIZE = 20

export default function Marketplace() {
  const [journeys, setJourneys] = useState<Journey[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filter, setFilter] = useState('All')
  const { getToken } = useAuth()

  const difficultyParam = filter === 'All' ? undefined : filter.toLowerCase()

  // Filter changes reset to page 1 — re-fetch from scratch.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getToken()
      .then(token => getMarketplace({ difficulty: difficultyParam, limit: PAGE_SIZE, offset: 0 }, token ?? undefined))
      .then(res => {
        if (cancelled) return
        setJourneys(res.journeys)
        setTotal(res.total)
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter])

  const loadMore = useCallback(async () => {
    setLoadingMore(true)
    try {
      const token = await getToken()
      const res = await getMarketplace(
        { difficulty: difficultyParam, limit: PAGE_SIZE, offset: journeys.length },
        token ?? undefined,
      )
      setJourneys(prev => [...prev, ...res.journeys])
      setTotal(res.total)
    } catch {
      /* leave the list as-is; the button just stays visible to retry */
    } finally {
      setLoadingMore(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journeys.length, difficultyParam])

  return (
    <>
      <PageMeta
        title="Marketplace"
        description="Discover the most-used, best-liked learning journeys created by the ECALT community."
        canonicalPath="/marketplace"
      />
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative pt-28 pb-20 px-4 max-w-7xl mx-auto">
        <div className="mb-10">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-100 mb-2">Marketplace</h1>
          <p className="text-slate-500">
            Journeys the community has used and liked the most, curated in by our admins.
          </p>
        </div>

        <div className="flex gap-2 flex-wrap mb-10">
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                filter === f
                  ? 'bg-violet-600 text-white'
                  : 'glass text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="shimmer-bg rounded-2xl h-64" />)}
          </div>
        ) : journeys.length > 0 ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {journeys.map(j => <MarketplaceCard key={j.id} journey={j} />)}
            </div>
            {journeys.length < total && (
              <div className="flex justify-center mt-10">
                <button onClick={loadMore} disabled={loadingMore} className="btn-ghost flex items-center gap-2">
                  {loadingMore && <Loader2 size={14} className="animate-spin" />}
                  Load more
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-24">
            <p className="text-4xl mb-4">🌱</p>
            <p className="text-lg font-medium text-slate-700 dark:text-slate-400">Nothing here yet</p>
            <p className="text-sm text-slate-500 mt-1">
              Journeys show up here once they've been used and liked by enough learners and approved by an admin.
            </p>
          </div>
        )}
      </div>
    </>
  )
}
