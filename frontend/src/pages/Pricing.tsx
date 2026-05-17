import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Check, Zap, Users, GraduationCap, Building2, ArrowLeft } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import { useSubscription } from '../lib/SubscriptionContext'
import PageMeta from '../components/PageMeta'

interface Plan {
  plan_id: string
  name: string
  base_price_cents: number
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
}

const PLAN_DETAILS: Record<string, { icon: React.ElementType; features: string[]; badge?: string; cta?: string }> = {
  free_trial: {
    icon: Zap,
    features: ['6 lifetime messages', 'Knowledge Universe preview', 'Today\'s spark'],
  },
  individual: {
    icon: Zap,
    features: ['Unlimited conversations', 'Knowledge Universe', 'Daily personalized spark', 'Image analysis', 'Mind Signature'],
    badge: 'Most popular',
  },
  student: {
    icon: GraduationCap,
    features: ['Same as Individual', 'Verified .edu discount', 'Study-focused sparks'],
    badge: '.edu required',
  },
  family: {
    icon: Users,
    features: ['Up to 5 learners', 'Shared budget', 'Individual Knowledge Universes', 'Parent dashboard'],
  },
  university: {
    icon: Building2,
    features: ['100+ seats', 'Admin dashboard', 'Usage analytics', 'LMS integration (roadmap)'],
    cta: 'Contact us',
  },
  enterprise: {
    icon: Building2,
    features: ['Custom seat count', 'Custom model routing', 'SLA & priority support', 'Custom integrations'],
    cta: 'Contact us',
  },
}

export default function Pricing() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, getToken } = useAuth()
  const { plan: currentPlan } = useSubscription()
  const [plans, setPlans] = useState<Plan[]>([])
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/subscriptions/plans')
      .then(r => r.json())
      .then(d => setPlans(d.plans ?? []))
      .catch(() => {})
  }, [])

  const handleSelect = async (planId: string) => {
    if (!user) { navigate('/'); return }
    if (planId === 'free_trial') return
    const details = PLAN_DETAILS[planId]
    if (details?.cta === 'Contact us') {
      window.location.href = `mailto:hello@ecalt.ai?subject=${encodeURIComponent(`${planId} plan inquiry`)}`
      return
    }

    setLoadingPlan(planId)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/subscriptions/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan_id: planId }),
      })
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        alert(data.detail ?? 'Billing not configured yet.')
      }
    } catch {
      alert('Something went wrong. Try again.')
    } finally {
      setLoadingPlan(null)
    }
  }

  const highlightPlan = searchParams.get('plan') ?? 'individual'

  return (
    <>
      <PageMeta title="Pricing" description="Choose the plan that fits your learning journey." />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-12">
        <div className="max-w-6xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 mb-10 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>

          <div className="text-center mb-12">
            <h1 className="text-3xl font-bold gradient-text mb-3">Simple, honest pricing</h1>
            <p className="text-slate-400">Choose the plan that fits your learning journey.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map(plan => {
              const details = PLAN_DETAILS[plan.plan_id]
              const Icon = details?.icon ?? Zap
              const isHighlighted = plan.plan_id === highlightPlan
              const isCurrent = currentPlan?.plan_id === plan.plan_id
              const isLoading = loadingPlan === plan.plan_id

              return (
                <div
                  key={plan.plan_id}
                  className={clsx(
                    'glass-card rounded-2xl p-6 flex flex-col transition-all duration-200',
                    isHighlighted && 'border-violet-500/50 shadow-lg shadow-violet-500/10',
                    isCurrent && 'border-cyan-500/40',
                  )}
                >
                  {details?.badge && (
                    <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-violet-300 bg-violet-500/20 px-2 py-0.5 rounded-full mb-3 self-start">
                      {details.badge}
                    </span>
                  )}
                  {isCurrent && (
                    <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-cyan-300 bg-cyan-500/20 px-2 py-0.5 rounded-full mb-3 self-start">
                      Current plan
                    </span>
                  )}

                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-9 h-9 rounded-xl bg-violet-500/15 flex items-center justify-center">
                      <Icon size={16} className="text-violet-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-100">{plan.name}</h3>
                      {plan.max_seats > 1 && (
                        <p className="text-[10px] text-slate-500">Up to {plan.max_seats} users</p>
                      )}
                    </div>
                  </div>

                  <div className="mb-5">
                    {plan.base_price_cents === 0 ? (
                      <span className="text-2xl font-bold text-slate-100">Free</span>
                    ) : (
                      <>
                        <span className="text-2xl font-bold text-slate-100">
                          ${(plan.base_price_cents / 100).toFixed(0)}
                        </span>
                        <span className="text-xs text-slate-500">/month</span>
                      </>
                    )}
                  </div>

                  <ul className="space-y-2 mb-6 flex-1">
                    {(details?.features ?? []).map(f => (
                      <li key={f} className="flex items-start gap-2 text-xs text-slate-400">
                        <Check size={11} className="text-violet-400 mt-0.5 shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>

                  <button
                    onClick={() => handleSelect(plan.plan_id)}
                    disabled={isCurrent || isLoading || plan.plan_id === 'free_trial'}
                    className={clsx(
                      'w-full py-2.5 rounded-xl text-xs font-semibold transition-all',
                      isCurrent || plan.plan_id === 'free_trial'
                        ? 'bg-slate-700/50 text-slate-500 cursor-default'
                        : isHighlighted
                          ? 'bg-violet-600 hover:bg-violet-500 text-white'
                          : 'border border-slate-600 hover:border-violet-500/50 text-slate-300 hover:text-violet-300',
                    )}
                  >
                    {isLoading ? 'Redirecting…' : isCurrent ? 'Current plan' : plan.plan_id === 'free_trial' ? 'Free forever' : (details?.cta ?? 'Get started')}
                  </button>
                </div>
              )
            })}
          </div>

          <p className="text-center text-xs text-slate-600 mt-10">
            All prices in USD · Cancel anytime · Powered by Stripe
          </p>
        </div>
      </div>
    </>
  )
}
