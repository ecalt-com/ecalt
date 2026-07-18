import { Link } from 'react-router-dom'
import { Clock, BookOpen, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import type { Journey } from '../lib/types'

interface JourneyCardProps {
  journey: Pick<Journey, 'id' | 'title' | 'description' | 'icon' | 'difficulty' | 'tags' | 'estimated_hours' | 'steps'> &
    Partial<Pick<Journey, 'hero_image_url'>>
  progress?: number
}

const difficultyStyle: Record<string, string> = {
  beginner:     'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-400/10 dark:border-emerald-400/25',
  intermediate: 'text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-400/10 dark:border-amber-400/25',
  advanced:     'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-400 dark:bg-rose-400/10 dark:border-rose-400/25',
}

export default function JourneyCard({ journey, progress }: JourneyCardProps) {
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
        </div>

        {progress !== undefined && (
          <div className="mb-4">
            <div className="h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">{progress}% complete</p>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-800/60">
          <div className="flex flex-wrap gap-1">
            {journey.tags.slice(0, 2).map((tag) => (
              <span key={tag} className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800/60 text-slate-500 dark:text-slate-600 text-xs">#{tag}</span>
            ))}
          </div>
          <ChevronRight size={15} className="text-slate-300 dark:text-slate-700 group-hover:text-violet-500 dark:group-hover:text-violet-400 group-hover:translate-x-1 transition-all duration-200" />
        </div>
        </div>
      </div>
    </Link>
  )
}
