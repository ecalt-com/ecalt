import { useNavigate } from 'react-router-dom'
import { Zap, GraduationCap, Users, Check } from 'lucide-react'
import clsx from 'clsx'
import { useSubscription } from '../lib/SubscriptionContext'
import { useGeo, isIndia } from '../lib/GeoContext'

const PLAN_ICONS: Record<string, React.ElementType> = {
  individual: Zap,
  student: GraduationCap,
  family: Users,
}

const PLAN_FEATURES: Record<string, string[]> = {
  individual: ['Unlimited AI lessons', 'Knowledge Universe', 'Daily personalized spark', 'Mind Signature'],
  student: ['Same as Individual', 'Verified .edu discount', 'Study-focused sparks'],
  family: ['Up to 5 learners', 'Shared budget', 'Individual Knowledge Universes'],
}

export default function StepUpgradePanel() {
  const navigate = useNavigate()
  const { plan: currentPlan, plans } = useSubscription()
  const { country, loading: geoLoading } = useGeo()

  const upgradePlans = plans.filter(p =>
    ['individual', 'student', 'family'].includes(p.plan_id) && p.plan_id !== currentPlan?.plan_id
  )

  function formatPrice(cents: number, inrPaise?: number): string {
    if (geoLoading) return '—'
    if (isIndia(country) && inrPaise) return `₹${(inrPaise / 100).toFixed(0)}/mo`
    return `$${(cents / 100).toFixed(0)}/mo`
  }

  return (
    <div className="py-4 space-y-4">
      <div className="text-center space-y-1">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">Token limit exhausted</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          You've used your plan's AI token budget. Upgrade to keep learning.
        </p>
      </div>

      <div className={clsx('grid gap-3', upgradePlans.length === 1 ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3')}>
        {upgradePlans.slice(0, 3).map(plan => {
          const Icon = PLAN_ICONS[plan.plan_id] ?? Zap
          const features = PLAN_FEATURES[plan.plan_id] ?? []
          const isHighlight = plan.plan_id === 'individual'

          return (
            <div
              key={plan.plan_id}
              className={clsx(
                'glass-card rounded-xl p-4 flex flex-col gap-3 transition-all duration-200',
                isHighlight
                  ? 'border-violet-400/50 dark:border-violet-500/40 shadow-sm shadow-violet-500/10'
                  : 'hover:border-slate-300 dark:hover:border-slate-600',
              )}
            >
              {isHighlight && (
                <span className="self-start text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-300 bg-violet-100 dark:bg-violet-500/20 px-2 py-0.5 rounded-full">
                  Most popular
                </span>
              )}

              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center shrink-0">
                  <Icon size={14} className="text-violet-600 dark:text-violet-400" />
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-800 dark:text-slate-100">{plan.name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {formatPrice(plan.base_price_cents, plan.base_price_inr_paise)}
                  </p>
                </div>
              </div>

              <ul className="space-y-1.5 flex-1">
                {features.map(f => (
                  <li key={f} className="flex items-start gap-1.5 text-xs text-slate-600 dark:text-slate-400">
                    <Check size={10} className="text-violet-500 dark:text-violet-400 mt-0.5 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => navigate(`/pricing?plan=${plan.plan_id}`)}
                className={clsx(
                  'w-full py-2 rounded-lg text-xs font-semibold transition-all',
                  isHighlight
                    ? 'bg-violet-600 hover:bg-violet-500 text-white'
                    : 'border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-violet-400 dark:hover:border-violet-500/50 hover:text-violet-600 dark:hover:text-violet-300',
                )}
              >
                Get started →
              </button>
            </div>
          )
        })}
      </div>

      <div className="text-center">
        <button
          onClick={() => navigate('/pricing')}
          className="text-xs text-slate-500 dark:text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 underline-offset-2 hover:underline transition-colors"
        >
          View all plans & apply promo code →
        </button>
      </div>
    </div>
  )
}
