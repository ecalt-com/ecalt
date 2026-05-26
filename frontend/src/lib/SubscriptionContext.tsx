import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext'

export interface PlanConfig {
  plan_id: string
  name: string
  base_price_cents: number
  base_price_inr_paise?: number
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
}

export interface CouponExtras {
  extra_credits_cents: number
  bonus_messages: number
}

export interface SubscriptionState {
  plan: PlanConfig | null
  plans: PlanConfig[]
  usedCents: number
  budgetCents: number
  messageCount: number
  lifetimeMessageCount: number | null
  couponExtras: CouponExtras | null
  isLimited: boolean
  isAdmin: boolean
  loading: boolean
  refresh: () => void
}

const DEFAULT: SubscriptionState = {
  plan: null,
  plans: [],
  usedCents: 0,
  budgetCents: 0,
  messageCount: 0,
  lifetimeMessageCount: null,
  couponExtras: null,
  isLimited: false,
  isAdmin: false,
  loading: true,
  refresh: () => {},
}

const SubscriptionContext = createContext<SubscriptionState>(DEFAULT)

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const { user, getToken } = useAuth()
  const [state, setState] = useState<Omit<SubscriptionState, 'refresh'>>(DEFAULT)

  const applyData = useCallback((data: Record<string, unknown>, plansData: Record<string, unknown>) => {
    const extras = data.coupon_extras as CouponExtras | undefined
    setState({
      plan: data.plan as PlanConfig,
      plans: (plansData.plans as PlanConfig[]) ?? [],
      usedCents: (data.usage as Record<string, number>)?.estimated_cost_cents ?? 0,
      budgetCents: (data.plan as PlanConfig)?.token_budget_cents ?? 0,
      messageCount: (data.usage as Record<string, number>)?.message_count ?? 0,
      lifetimeMessageCount: (data.lifetime_message_count as number | null) ?? null,
      couponExtras: extras ?? null,
      isLimited: (data.is_limited as boolean) ?? false,
      isAdmin: (data.is_admin as boolean) ?? false,
      loading: false,
    })
  }, [])

  const fetch = useCallback(async () => {
    if (!user) {
      setState({ ...DEFAULT, loading: false })
      return
    }
    try {
      const token = await getToken()
      if (!token) return
      const [meRes, plansRes] = await Promise.all([
        window.fetch('/api/v1/subscriptions/me', { headers: { Authorization: `Bearer ${token}` } }),
        window.fetch('/api/v1/subscriptions/plans'),
      ])
      if (!meRes.ok) return
      const [data, plansData] = await Promise.all([meRes.json(), plansRes.ok ? plansRes.json() : { plans: [] }])
      applyData(data, plansData)
    } catch {
      setState(prev => ({ ...prev, loading: false }))
    }
  }, [user, getToken, applyData])

  useEffect(() => {
    fetch()
  }, [fetch])

  return (
    <SubscriptionContext.Provider value={{ ...state, refresh: fetch }}>
      {children}
    </SubscriptionContext.Provider>
  )
}

export const useSubscription = () => useContext(SubscriptionContext)
