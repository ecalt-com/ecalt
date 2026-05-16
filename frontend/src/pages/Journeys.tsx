import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import Navigation from '../components/Navigation'
import JourneyCard from '../components/JourneyCard'
import { getJourneys } from '../lib/api'
import type { Journey } from '../lib/types'

const FILTERS = ['All', 'Beginner', 'Intermediate', 'Advanced']

export default function Journeys() {
  const [journeys, setJourneys] = useState<Journey[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')

  useEffect(() => {
    getJourneys()
      .then(res => setJourneys(res.journeys))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = journeys.filter(j => {
    const matchFilter = filter === 'All' || j.difficulty === filter.toLowerCase()
    const matchSearch = !search ||
      j.title.toLowerCase().includes(search.toLowerCase()) ||
      j.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
    return matchFilter && matchSearch
  })

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative pt-28 pb-20 px-4 max-w-7xl mx-auto">
        <div className="mb-10">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-100 mb-2">All Journeys</h1>
          <p className="text-slate-500">Explore our curated learning paths across every topic</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 mb-10">
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-600" />
            <input
              type="text"
              placeholder="Search journeys…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full glass rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-600 outline-none"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
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
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="shimmer-bg rounded-2xl h-56" />)}
          </div>
        ) : filtered.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map(j => <JourneyCard key={j.id} journey={j} />)}
          </div>
        ) : (
          <div className="text-center py-24">
            <p className="text-4xl mb-4">🔍</p>
            <p className="text-lg font-medium text-slate-700 dark:text-slate-400">No journeys found</p>
            <p className="text-sm text-slate-500 mt-1">Try a different search or filter</p>
          </div>
        )}
      </div>
    </>
  )
}
