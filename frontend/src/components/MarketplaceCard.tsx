import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Clock, BookOpen, Heart, Plus, Loader2, Users } from 'lucide-react'
import clsx from 'clsx'
import type { Journey } from '../lib/types'
import { toggleJourneyLike, forkJourney } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'

interface MarketplaceCardProps {
  journey: Journey
}

const difficultyStyle: Record<string, string> = {
  beginner:     'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-400/10 dark:border-emerald-400/25',
  intermediate: 'text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-400/10 dark:border-amber-400/25',
  advanced:     'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-400 dark:bg-rose-400/10 dark:border-rose-400/25',
}

// A journey only lands here once a scheduled popularity job + admin review
// have both approved it (marketplace_status === 'published'), so "liked" is
// always false on load — the API has no per-viewer "did I already like this"
// field, only the aggregate count (see docs/frontend-changes-course-marketplace.md).
export default function MarketplaceCard({ journey }: MarketplaceCardProps) {
  const navigate = useNavigate()
  const { user, getToken, signIn } = useAuth()
  const { addToast } = useToast()
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(journey.like_count)
  const [liking, setLiking] = useState(false)
  const [forking, setForking] = useState(false)

  const handleLike = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!user) { signIn(); return }
    if (liking) return
    setLiking(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await toggleJourneyLike(journey.id, token)
      setLiked(res.liked)
      setLikeCount(res.like_count)
    } catch {
      addToast("Couldn't update like", 'error')
    } finally {
      setLiking(false)
    }
  }

  const handleFork = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!user) { signIn(); return }
    if (forking) return
    setForking(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await forkJourney(journey.id, token)
      addToast('Added to your journeys')
      navigate(`/journey/${res.journey.id}`)
    } catch {
      addToast("Couldn't add this journey", 'error')
    } finally {
      setForking(false)
    }
  }

  return (
    <Link to={`/journey/${journey.id}`} className="block h-full">
      <div className="glass-card rounded-2xl h-full flex flex-col group cursor-pointer overflow-hidden">
        {journey.hero_image_url && (
          <div className="relative aspect-[16/9] shrink-0">
            <img
              src={journey.hero_image_url}
              alt={journey.title}
              loading="lazy"
              className="absolute inset-0 w-full h-full object-cover"
            />
            <span className={clsx('absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-medium border backdrop-blur-sm', difficultyStyle[journey.difficulty])}>
              {journey.difficulty}
            </span>
          </div>
        )}
        <div className="p-6 flex flex-col flex-1">
          {!journey.hero_image_url && (
            <div className="flex items-start justify-between mb-4">
              <span className="text-4xl leading-none">{journey.icon}</span>
              <span className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border', difficultyStyle[journey.difficulty])}>
                {journey.difficulty}
              </span>
            </div>
          )}

          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2 group-hover:text-violet-600 dark:group-hover:text-violet-300 transition-colors leading-snug">
            {journey.title}
          </h3>
          <p className="text-sm text-slate-500 mb-4 line-clamp-2 flex-1">{journey.description}</p>

          <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-600 mb-4">
            <span className="flex items-center gap-1.5"><BookOpen size={12} />{journey.steps.length} steps</span>
            <span className="flex items-center gap-1.5"><Clock size={12} />~{journey.estimated_hours}h</span>
            <span className="flex items-center gap-1.5"><Users size={12} />popular</span>
          </div>

          <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-200 dark:border-slate-800/60">
            <button
              onClick={handleLike}
              disabled={liking}
              className="flex items-center gap-1.5 px-2 py-1 -ml-2 rounded-lg text-xs font-medium text-slate-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10 dark:hover:text-rose-400 transition-colors"
            >
              <Heart size={13} className={liked ? 'fill-rose-500 text-rose-500' : ''} />
              {likeCount}
            </button>
            <button
              onClick={handleFork}
              disabled={forking}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-50 text-violet-700 hover:bg-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:hover:bg-violet-500/20 transition-colors"
            >
              {forking ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              Add to my journeys
            </button>
          </div>
        </div>
      </div>
    </Link>
  )
}
