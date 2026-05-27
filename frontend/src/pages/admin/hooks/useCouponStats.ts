import { useState, useEffect } from 'react'
import { useAuth } from '../../../lib/AuthContext'
import type { CouponStats } from '../types'
import type { TabId } from '../constants'

export function useCouponStats(tab: TabId) {
  const { getToken, user } = useAuth()
  const [couponStats, setCouponStats] = useState<CouponStats | null>(null)

  useEffect(() => {
    if (tab !== 'coupons' || couponStats !== null || !user) return
    async function loadCouponStats() {
      const token = await getToken()
      if (!token) return
      const res = await fetch('/api/v1/coupons/admin/stats', { headers: { Authorization: `Bearer ${token}` } })
      if (res.ok) setCouponStats(await res.json())
    }
    loadCouponStats().catch(() => {})
  }, [tab, couponStats, getToken, user])

  return { couponStats }
}
