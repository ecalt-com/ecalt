import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext'

export interface PlanConfig {
  plan_id: string
  name: string
  base_price_cents: number
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
}

export interface SubscriptionState {
  plan: PlanConfig | null
  usedCents: number
  budgetCents: number
  messageCount: number
  lifetimeMessageCount: number | null
  isLimited: boolean
  isAdmin: boolean
  loading: boolean
  refresh: () => void
}

const DEFAULT: SubscriptionState = {
  plan: null,
  usedCents: 0,
  budgetCents: 0,
  messageCount: 0,
  lifetimeMessageCount: null,
  isLimited: false,
  isAdmin: false,
  loading: true,
  refresh: () => {},
}

const SubscriptionContext = createContext<SubscriptionState>(DEFAULT)

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const { user, getToken } = useAuth()
  const [state, setState] = useState<Omit<SubscriptionState, 'refresh'>>(DEFAULT)

  const fetch = useCallback(async () => {
    if (!user) {
      setState({ ...DEFAULT, loading: false })
      return
    }
    try {
      const token = await getToken()
      if (!token) return
      const res = await window.fetch('/api/v1/subscriptions/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return
      const data = await res.json()
      setState({
        plan: data.plan,
        usedCents: data.usage?.estimated_cost_cents ?? 0,
        budgetCents: data.plan?.token_budget_cents ?? 0,
        messageCount: data.usage?.message_count ?? 0,
        lifetimeMessageCount: data.lifetime_message_count ?? null,
        isLimited: data.is_limited ?? false,
        isAdmin: data.is_admin ?? false,
        loading: false,
      })
    } catch {
      setState(prev => ({ ...prev, loading: false }))
    }
  }, [user, getToken])

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
