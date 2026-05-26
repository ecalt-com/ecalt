import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Check, Zap, Users, GraduationCap, Building2, ArrowLeft, Ticket } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import { useSubscription } from '../lib/SubscriptionContext'
import { useGeo, isIndia } from '../lib/GeoContext'
import { usePaymentConfig } from '../lib/PaymentConfig'
import { loadRazorpayScript, RazorpayResponse } from '../lib/razorpay'
import PageMeta from '../components/PageMeta'

interface Plan {
  plan_id: string
  name: string
  base_price_cents: number
  base_price_inr_paise?: number
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
}

const PLAN_DETAILS: Record<string, { icon: React.ElementType; features: string[]; badge?: string; cta?: string }> = {
  free_trial: {
    icon: Zap,
    features: ["6 lifetime messages", "Knowledge Universe preview", "Today's spark"],
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

function formatPrice(plan: Plan, country: string): string {
  if (plan.base_price_cents === 0) return 'Free'
  if (isIndia(country) && plan.base_price_inr_paise) {
    return `₹${(plan.base_price_inr_paise / 100).toFixed(0)}`
  }
  return `$${(plan.base_price_cents / 100).toFixed(0)}`
}

export default function Pricing() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, getToken } = useAuth()
  const { plan: currentPlan, plans, loading: loadingPlans } = useSubscription()
  const { country } = useGeo()
  const { razorpayKeyId } = usePaymentConfig()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)

  const handleRazorpayCheckout = async (
    data: {
      checkout_type: 'subscription' | 'order'
      subscription_id?: string
      order_id?: string
      amount: number
      currency: string
    },
    planId: string,
    token: string,
  ) => {
    const loaded = await loadRazorpayScript()
    if (!loaded) { alert('Could not load Razorpay. Check your connection.'); return }

    return new Promise<void>((resolve) => {
      const options: any = {
        key: razorpayKeyId,
        amount: data.amount,
        currency: data.currency,
        name: 'ecalt',
        description: `${planId} plan`,
        prefill: { email: user?.email ?? '' },
        modal: { ondismiss: () => { setLoadingPlan(null); resolve() } },
      }

      if (data.checkout_type === 'subscription') {
        options.subscription_id = data.subscription_id
        options.handler = async () => { navigate('/learn?upgraded=true'); resolve() }
      } else {
        options.order_id = data.order_id
        options.handler = async (response: RazorpayResponse) => {
          const verifyRes = await fetch('/api/v1/subscriptions/razorpay/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              plan_id: planId,
            }),
          })
          if (verifyRes.ok) navigate('/learn?upgraded=true')
          else alert('Payment verification failed. Contact support with your payment ID.')
          resolve()
        }
      }

      new (window as any).Razorpay(options).open()
    })
  }

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
        body: JSON.stringify({ plan_id: planId, country }),
      })
      const data = await res.json()

      if (data.gateway === 'razorpay') {
        await handleRazorpayCheckout(data, planId, token!)
      } else {
        // stripe (default) — redirect to hosted checkout
        if (data.checkout_url) {
          window.location.href = data.checkout_url
        } else {
          alert(data.detail ?? 'Billing not configured yet.')
        }
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
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 mb-10 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>

          <div className="text-center mb-12">
            <h1 className="text-3xl font-bold gradient-text mb-3">Simple, honest pricing</h1>
            <p className="text-slate-500 dark:text-slate-400">Choose the plan that fits your learning journey.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {loadingPlans
              ? Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="glass-card rounded-2xl p-6 flex flex-col animate-pulse">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-9 h-9 rounded-xl bg-slate-200 dark:bg-slate-700" />
                      <div className="h-3.5 w-24 rounded bg-slate-200 dark:bg-slate-700" />
                    </div>
                    <div className="h-7 w-16 rounded bg-slate-200 dark:bg-slate-700 mb-5" />
                    <div className="space-y-2 flex-1 mb-6">
                      {Array.from({ length: 4 }).map((_, j) => (
                        <div key={j} className="h-2.5 rounded bg-slate-200 dark:bg-slate-700" style={{ width: `${70 + (j % 3) * 10}%` }} />
                      ))}
                    </div>
                    <div className="h-9 rounded-xl bg-slate-200 dark:bg-slate-700" />
                  </div>
                ))
              : plans.map(plan => {
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
                    <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-300 bg-violet-100 dark:bg-violet-500/20 px-2 py-0.5 rounded-full mb-3 self-start">
                      {details.badge}
                    </span>
                  )}
                  {isCurrent && (
                    <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-cyan-700 dark:text-cyan-300 bg-cyan-100 dark:bg-cyan-500/20 px-2 py-0.5 rounded-full mb-3 self-start">
                      Current plan
                    </span>
                  )}

                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-9 h-9 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                      <Icon size={16} className="text-violet-600 dark:text-violet-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">{plan.name}</h3>
                      {plan.max_seats > 1 && (
                        <p className="text-[10px] text-slate-500">{plan.max_seats} users</p>
                      )}
                    </div>
                  </div>

                  <div className="mb-5">
                    <span className="text-2xl font-bold text-slate-800 dark:text-slate-100">
                      {formatPrice(plan, country)}
                    </span>
                    {plan.base_price_cents > 0 && (
                      <span className="text-xs text-slate-400 dark:text-slate-500">/month</span>
                    )}
                  </div>

                  <ul className="space-y-2 mb-6 flex-1">
                    {(details?.features ?? []).map(f => (
                      <li key={f} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-400">
                        <Check size={11} className="text-violet-500 dark:text-violet-400 mt-0.5 shrink-0" />
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
                        ? 'bg-slate-100 dark:bg-slate-700/50 text-slate-400 dark:text-slate-500 cursor-default'
                        : isHighlighted
                          ? 'bg-violet-600 hover:bg-violet-500 text-white'
                          : 'border border-slate-200 dark:border-slate-600 hover:border-violet-400 dark:hover:border-violet-500/50 text-slate-700 dark:text-slate-300 hover:text-violet-600 dark:hover:text-violet-300',
                    )}
                  >
                    {isLoading ? 'Processing…' : isCurrent ? 'Current plan' : plan.plan_id === 'free_trial' ? 'Free forever' : (details?.cta ?? 'Get started')}
                  </button>
                </div>
              )
            })}
          </div>

          <p className="text-center text-xs text-slate-400 dark:text-slate-600 mt-10">
            {isIndia(country)
              ? 'All prices in INR · Cancel anytime · Powered by Razorpay'
              : 'All prices in USD · Cancel anytime · Powered by Stripe'}
          </p>

          <CouponApply />
        </div>
      </div>
    </>
  )
}

function CouponApply() {
  const { user, getToken } = useAuth()
  const { refresh } = useSubscription()
  const [code, setCode] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  if (!user) return null

  const apply = async () => {
    if (!code.trim()) return
    setStatus('loading')
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/coupons/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ code: code.trim().toUpperCase() }),
      })
      const data = await res.json()
      if (!res.ok) {
        setMessage(typeof data.detail === 'string' ? data.detail : 'Invalid coupon.')
        setStatus('error')
        return
      }
      refresh()
      setMessage(`✓ ${data.description ?? 'Coupon applied!'}`)
      setStatus('success')
      setCode('')
    } catch {
      setMessage('Something went wrong. Try again.')
      setStatus('error')
    }
  }

  return (
    <div className="mt-10 flex flex-col items-center gap-3">
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <Ticket size={12} />
        Have a promo code?
      </div>
      <div className="flex gap-2">
        <input
          value={code}
          onChange={e => { setCode(e.target.value.toUpperCase()); setStatus('idle') }}
          onKeyDown={e => e.key === 'Enter' && apply()}
          placeholder="ENTER CODE"
          className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs outline-none focus:border-violet-400 dark:focus:border-violet-500/50 w-40 font-mono tracking-wider"
        />
        <button
          onClick={apply}
          disabled={status === 'loading' || !code.trim()}
          className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold disabled:opacity-50 transition-colors"
        >
          {status === 'loading' ? '…' : 'Apply'}
        </button>
      </div>
      {message && (
        <p className={`text-xs ${status === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}`}>
          {message}
        </p>
      )}
    </div>
  )
}
