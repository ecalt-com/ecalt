import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../lib/AuthContext'
import type {
  PlanRow, Stats, UserRow, AIConfig, ModelOption, UsageByModel, DailyUsage,
  RevenueData, CostAnalysis, RetentionData, FeatureUsageData, FunnelData,
  ContentData, CouponRow, PromptRow, NotificationTemplateRow,
} from '../types'

export function useAdminData() {
  const navigate = useNavigate()
  const { getToken, user } = useAuth()

  const [plans, setPlans]               = useState<PlanRow[]>([])
  const [stats, setStats]               = useState<Stats | null>(null)
  const [users, setUsers]               = useState<UserRow[]>([])
  const [aiConfigs, setAiConfigs]       = useState<AIConfig[]>([])
  const [availableModels, setAvailableModels] = useState<Record<string, ModelOption[]>>({})
  const [usageByModel, setUsageByModel] = useState<UsageByModel[]>([])
  const [dailyUsage, setDailyUsage]     = useState<DailyUsage[]>([])
  const [revenue, setRevenue]           = useState<RevenueData | null>(null)
  const [costAnalysis, setCostAnalysis] = useState<CostAnalysis | null>(null)
  const [retentionData, setRetentionData] = useState<RetentionData | null>(null)
  const [featureUsage, setFeatureUsage] = useState<FeatureUsageData | null>(null)
  const [funnelData, setFunnelData]     = useState<FunnelData | null>(null)
  const [contentData, setContentData]   = useState<ContentData | null>(null)
  const [coupons, setCoupons]                         = useState<CouponRow[]>([])
  const [prompts, setPrompts]                         = useState<PromptRow[]>([])
  const [notificationTemplates, setNotificationTemplates] = useState<NotificationTemplateRow[]>([])
  const [templateVariables, setTemplateVariables]     = useState<Record<string, string[]>>({})

  useEffect(() => {
    if (!user) return
    let cancelled = false
    async function load() {
      const token = await getToken()
      if (!token) return

      const h = { Authorization: `Bearer ${token}` }
      const [pRes, sRes, uRes, aiRes, usageRes, cRes, revRes, costRes, retRes, fuRes, fnRes, csRes, prRes, ntRes, tvRes] = await Promise.all([
        fetch('/api/v1/admin/plans',                            { headers: h }),
        fetch('/api/v1/admin/stats',                            { headers: h }),
        fetch('/api/v1/admin/users',                            { headers: h }),
        fetch('/api/v1/admin/ai-config',                        { headers: h }),
        fetch('/api/v1/admin/usage',                            { headers: h }),
        fetch('/api/v1/coupons/admin',                          { headers: h }),
        fetch('/api/v1/admin/revenue',                          { headers: h }),
        fetch('/api/v1/admin/cost-analysis',                    { headers: h }),
        fetch('/api/v1/admin/retention',                        { headers: h }),
        fetch('/api/v1/admin/feature-usage',                    { headers: h }),
        fetch('/api/v1/admin/funnel',                           { headers: h }),
        fetch('/api/v1/admin/content-stats',                    { headers: h }),
        fetch('/api/v1/admin/prompts',                          { headers: h }),
        fetch('/api/v1/admin/notification-templates',           { headers: h }),
        fetch('/api/v1/admin/notification-templates/variables', { headers: h }),
      ])

      if (pRes.status === 403) { navigate('/'); return }
      if (!cancelled && pRes.ok) setPlans(await pRes.json().then((d: any) => d.plans ?? []))
      if (!cancelled && sRes.ok) setStats(await sRes.json())
      if (!cancelled && uRes.ok) setUsers(await uRes.json().then((d: any) => d.users ?? []))
      if (!cancelled && aiRes.ok) {
        const d = await aiRes.json()
        setAiConfigs(d.configs ?? [])
        setAvailableModels(d.available_models ?? {})
      }
      if (!cancelled && usageRes.ok) {
        const d = await usageRes.json()
        setUsageByModel(d.by_model ?? [])
        setDailyUsage(d.daily ?? [])
      }
      if (!cancelled && cRes.ok) setCoupons(await cRes.json().then((d: any) => d.coupons ?? []))
      if (!cancelled && revRes.ok) setRevenue(await revRes.json())
      if (!cancelled && costRes.ok) setCostAnalysis(await costRes.json())
      if (!cancelled && retRes.ok) setRetentionData(await retRes.json())
      if (!cancelled && fuRes.ok) setFeatureUsage(await fuRes.json())
      if (!cancelled && fnRes.ok) setFunnelData(await fnRes.json())
      if (!cancelled && csRes.ok) setContentData(await csRes.json())
      if (!cancelled && prRes.ok) setPrompts(await prRes.json())
      if (!cancelled && ntRes.ok) setNotificationTemplates(await ntRes.json())
      if (!cancelled && tvRes.ok) setTemplateVariables(await tvRes.json())
    }
    load().catch(() => navigate('/'))
    return () => { cancelled = true }
  }, [getToken, navigate, user])

  return {
    plans, stats, users, aiConfigs, availableModels,
    usageByModel, dailyUsage, revenue, costAnalysis,
    retentionData, featureUsage, funnelData, contentData, coupons,
    prompts, notificationTemplates, templateVariables,
    setPlans, setUsers, setAiConfigs, setCoupons,
    setPrompts, setNotificationTemplates,
  }
}
