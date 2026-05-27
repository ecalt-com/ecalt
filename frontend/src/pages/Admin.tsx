import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, ArrowLeft, Save, Loader2, ShieldCheck, ShieldOff, Check, Zap, Search, Cpu, Ticket, Plus, ToggleLeft, ToggleRight, AlertTriangle, ChevronDown, ChevronUp, BarChart2, Copy, Trash2, X, Pencil } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import PageMeta from '../components/PageMeta'
import type {
  PlanRow, NewPlanForm, Stats, UserRow, UserDetail, RevenueData, AIConfig, ModelOption,
  UsageByModel, DailyUsage, CostAnalysis, ContentData, StepDropoff,
  FunnelData, FeatureUsageData, RetentionData, CouponRow, RedemptionRow, CouponStats,
} from './admin/types'
import { PLAN_ICONS, PLAN_FEATURES, INTERACTION_LABELS, TABS, inputCls, selectCls } from './admin/constants'
import type { TabId } from './admin/constants'
import { fmtCents, fmtPct, calcPct, fmtTokens, fmtMonth } from './admin/utils'
import { FeatureTrendChart } from './admin/components/FeatureTrendChart'



export default function Admin() {
  const navigate = useNavigate()
  const { getToken, user } = useAuth()

  const [plans, setPlans] = useState<PlanRow[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [users, setUsers] = useState<UserRow[]>([])
  const [aiConfigs, setAiConfigs] = useState<AIConfig[]>([])
  const [availableModels, setAvailableModels] = useState<Record<string, ModelOption[]>>({})
  const [usageByModel, setUsageByModel] = useState<UsageByModel[]>([])
  const [dailyUsage, setDailyUsage] = useState<DailyUsage[]>([])
  const [revenue, setRevenue] = useState<RevenueData | null>(null)
  const [costAnalysis, setCostAnalysis] = useState<CostAnalysis | null>(null)
  const [retentionData, setRetentionData] = useState<RetentionData | null>(null)
  const [featureUsage, setFeatureUsage] = useState<FeatureUsageData | null>(null)
  const [funnelData, setFunnelData] = useState<FunnelData | null>(null)
  const [contentData, setContentData] = useState<ContentData | null>(null)
  const [expandedJourneyId, setExpandedJourneyId] = useState<string | null>(null)
  const [journeyDropoff, setJourneyDropoff] = useState<Record<string, StepDropoff[]>>({})
  const [loadingDropoff, setLoadingDropoff] = useState<string | null>(null)

  const [saving, setSaving] = useState<string | null>(null)
  const [savingAI, setSavingAI] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, Partial<PlanRow>>>({})
  const [aiEdits, setAiEdits] = useState<Record<string, AIConfig>>({})
  const [togglingUid, setTogglingUid] = useState<string | null>(null)
  const [tab, setTab] = useState<TabId>('overview')
  const [userSearch, setUserSearch] = useState('')

  // Coupon state
  const [coupons, setCoupons] = useState<CouponRow[]>([])
  const [couponForm, setCouponForm] = useState({ code: '', description: '', credit_cents: '', bonus_messages: '', duration_days: '', max_redemptions: '', expires_at: '' })
  const [creatingCoupon, setCreatingCoupon] = useState(false)
  const [couponError, setCouponError] = useState<string | null>(null)
  const [editingCode, setEditingCode] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<CouponRow>>({})
  const [savingEdit, setSavingEdit] = useState(false)
  const [confirmDeleteCode, setConfirmDeleteCode] = useState<string | null>(null)
  const [deletingCode, setDeletingCode] = useState<string | null>(null)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('')
  const [copiedCode, setCopiedCode] = useState<string | null>(null)
  const [redemptions, setRedemptions] = useState<Record<string, RedemptionRow[]>>({})
  const [loadingRedemptions, setLoadingRedemptions] = useState<string | null>(null)
  const [expandedRedemptionsCode, setExpandedRedemptionsCode] = useState<string | null>(null)
  const [couponSearch, setCouponSearch] = useState('')
  const [couponStatusFilter, setCouponStatusFilter] = useState<'all' | 'active' | 'inactive' | 'expired' | 'depleted'>('all')
  const [couponSort, setCouponSort] = useState<'newest' | 'most_used' | 'expiring'>('newest')
  const [couponStats, setCouponStats] = useState<CouponStats | null>(null)
  const [showBulkForm, setShowBulkForm] = useState(false)
  const [bulkForm, setBulkForm] = useState({ prefix: '', count: '10', description: '', credit_cents: '', bonus_messages: '0', duration_days: '', expires_at: '' })
  const [bulkResult, setBulkResult] = useState<string[] | null>(null)
  const [bulkGenerating, setBulkGenerating] = useState(false)
  const [provisioning, setProvisioning] = useState<Record<string, string | null>>({})
  const [expandedUid, setExpandedUid] = useState<string | null>(null)
  const [userDetails, setUserDetails] = useState<Record<string, UserDetail>>({})
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null)
  const [newPlanForm, setNewPlanForm] = useState<NewPlanForm>({
    plan_id: '', name: '', base_price_cents: '', base_price_inr_paise: '',
    token_budget_cents: '', max_seats: '1',
  })
  const [creatingPlan, setCreatingPlan] = useState(false)

  const createFormRef = useRef<HTMLDivElement>(null)

  const filteredUsers = useMemo(() => {
    const q = userSearch.toLowerCase().trim()
    if (!q) return users
    return users.filter(u =>
      u.display_name?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.uid.toLowerCase().includes(q)
    )
  }, [users, userSearch])

  const filteredCoupons = useMemo(() => {
    let result = [...coupons]
    if (couponSearch) {
      result = result.filter(c =>
        c.code.includes(couponSearch.toUpperCase()) ||
        c.description.toLowerCase().includes(couponSearch.toLowerCase())
      )
    }
    const now = new Date()
    if (couponStatusFilter === 'active')
      result = result.filter(c => c.is_active && (!c.expires_at || new Date(c.expires_at) > now))
    else if (couponStatusFilter === 'inactive')
      result = result.filter(c => !c.is_active)
    else if (couponStatusFilter === 'expired')
      result = result.filter(c => c.expires_at != null && new Date(c.expires_at) <= now)
    else if (couponStatusFilter === 'depleted')
      result = result.filter(c => c.max_redemptions != null && c.redemption_count >= c.max_redemptions)
    if (couponSort === 'most_used')
      result.sort((a, b) => b.redemption_count - a.redemption_count)
    else if (couponSort === 'expiring')
      result = result.filter(c => c.expires_at != null).sort((a, b) =>
        new Date(a.expires_at!).getTime() - new Date(b.expires_at!).getTime()
      )
    return result
  }, [coupons, couponSearch, couponStatusFilter, couponSort])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    async function load() {
      const token = await getToken()
      if (!token) return

      const [pRes, sRes, uRes, aiRes, usageRes, cRes, revRes, costRes, retRes, fuRes, fnRes, csRes] = await Promise.all([
        fetch('/api/v1/admin/plans',          { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/stats',          { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/users',          { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/ai-config',      { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/usage',          { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/coupons/admin',        { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/revenue',        { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/cost-analysis',  { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/retention',      { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/feature-usage',  { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/funnel',          { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/content-stats',   { headers: { Authorization: `Bearer ${token}` } }),
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
    }
    load().catch(() => navigate('/'))
    return () => { cancelled = true }
  }, [getToken, navigate, user])

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

  const handleSavePlan = async (planId: string) => {
    const patch = edits[planId]
    if (!patch) return
    setSaving(planId)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/plans/${planId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(patch),
      })
      if (res.ok) {
        const data = await res.json()
        setPlans(prev => prev.map(p => p.plan_id === planId ? { ...p, ...data.plan } : p))
        setEdits(prev => { const next = { ...prev }; delete next[planId]; return next })
      }
    } finally { setSaving(null) }
  }

  const handleSaveAI = async (interactionType: string) => {
    const cfg = aiEdits[interactionType]
    if (!cfg) return
    setSavingAI(interactionType)
    try {
      const token = await getToken()
      await fetch('/api/v1/admin/ai-config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(cfg),
      })
      setAiConfigs(prev => prev.map(c => c.interaction_type === interactionType ? { ...c, ...cfg } : c))
      setAiEdits(prev => { const next = { ...prev }; delete next[interactionType]; return next })
    } finally { setSavingAI(null) }
  }

  const handleToggleAdmin = async (uid: string) => {
    setTogglingUid(uid)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/users/${uid}/toggle-admin`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setUsers(prev => prev.map(u => u.uid === uid ? { ...u, is_admin: data.user.is_admin } : u))
      }
    } finally { setTogglingUid(null) }
  }

  const handleExpandUser = async (uid: string) => {
    if (expandedUid === uid) { setExpandedUid(null); return }
    setExpandedUid(uid)
    if (userDetails[uid]) return
    setLoadingDetail(uid)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/users/${uid}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data: UserDetail = await res.json()
        setUserDetails(prev => ({ ...prev, [uid]: data }))
      }
    } finally {
      setLoadingDetail(null)
    }
  }

  const setEdit = (planId: string, field: string, value: string | number | boolean | null) => {
    setEdits(prev => ({ ...prev, [planId]: { ...prev[planId], [field]: value } }))
  }

  const setAiEdit = (interactionType: string, field: 'provider' | 'model', value: string) => {
    setAiEdits(prev => {
      const base = prev[interactionType] ?? aiConfigs.find(c => c.interaction_type === interactionType) ?? { interaction_type: interactionType, provider: 'anthropic', model: '' }
      const updated = { ...base, [field]: value }
      // Reset model when provider changes
      if (field === 'provider') {
        const models = availableModels[value] ?? []
        updated.model = models[0]?.id ?? ''
      }
      return { ...prev, [interactionType]: updated }
    })
  }

  const handleCreateCoupon = async () => {
    setCouponError(null)
    if (!couponForm.code.trim() || !couponForm.description.trim()) {
      setCouponError('Code and description are required.')
      return
    }
    setCreatingCoupon(true)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/coupons/admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          code: couponForm.code.toUpperCase(),
          description: couponForm.description,
          credit_cents: parseFloat(couponForm.credit_cents || '0'),
          bonus_messages: parseInt(couponForm.bonus_messages || '0', 10),
          duration_days: couponForm.duration_days ? parseInt(couponForm.duration_days, 10) : null,
          max_redemptions: couponForm.max_redemptions ? parseInt(couponForm.max_redemptions, 10) : null,
          expires_at: couponForm.expires_at || null,
        }),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        setCouponError(d.detail ?? 'Failed to create coupon.')
        return
      }
      const created = await res.json()
      setCoupons(prev => [created, ...prev])
      setCouponForm({ code: '', description: '', credit_cents: '', bonus_messages: '', duration_days: '', max_redemptions: '', expires_at: '' })
    } finally {
      setCreatingCoupon(false)
    }
  }

  const handleToggleCoupon = async (code: string, active: boolean) => {
    const token = await getToken()
    const res = await fetch(`/api/v1/coupons/admin/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ is_active: active }),
    })
    if (res.ok) {
      setCoupons(prev => prev.map(c => c.code === code ? { ...c, is_active: active } : c))
    }
  }

  const handleSaveCoupon = async (code: string) => {
    setSavingEdit(true)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/coupons/admin/${code}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(editForm),
      })
      if (res.ok) {
        const updated = await res.json()
        setCoupons(prev => prev.map(c => c.code === code ? { ...c, ...updated } : c))
        setEditingCode(null)
        setEditForm({})
      }
    } finally { setSavingEdit(false) }
  }

  const handleDeleteCoupon = async (code: string) => {
    setDeletingCode(code)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/coupons/admin/${code}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setCoupons(prev => prev.filter(c => c.code !== code))
        setConfirmDeleteCode(null)
        setEditingCode(null)
        setDeleteConfirmInput('')
      }
    } finally { setDeletingCode(null) }
  }

  const handleLoadRedemptions = async (code: string) => {
    if (expandedRedemptionsCode === code) { setExpandedRedemptionsCode(null); return }
    setExpandedRedemptionsCode(code)
    if (redemptions[code]) return
    setLoadingRedemptions(code)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/coupons/admin/${code}/redemptions`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setRedemptions(prev => ({ ...prev, [code]: data.redemptions ?? [] }))
      }
    } finally { setLoadingRedemptions(null) }
  }

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 1500)
  }

  const handleCloneCoupon = (c: CouponRow) => {
    setCouponForm({
      code: '',
      description: c.description,
      credit_cents: String(c.credit_cents),
      bonus_messages: String(c.bonus_messages),
      duration_days: c.duration_days ? String(c.duration_days) : '',
      max_redemptions: c.max_redemptions ? String(c.max_redemptions) : '',
      expires_at: '',
    })
    createFormRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleBulkGenerate = async () => {
    setBulkGenerating(true)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/coupons/admin/bulk-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          prefix: bulkForm.prefix.toUpperCase(),
          count: parseInt(bulkForm.count),
          description: bulkForm.description,
          credit_cents: parseFloat(bulkForm.credit_cents || '0'),
          bonus_messages: parseInt(bulkForm.bonus_messages || '0'),
          duration_days: bulkForm.duration_days ? parseInt(bulkForm.duration_days) : null,
          expires_at: bulkForm.expires_at || null,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setBulkResult(data.codes ?? [])
        const cRes = await fetch('/api/v1/coupons/admin', { headers: { Authorization: `Bearer ${token}` } })
        if (cRes.ok) setCoupons(await cRes.json().then((d: any) => d.coupons ?? []))
      }
    } finally { setBulkGenerating(false) }
  }

  const handleExpandJourney = async (journeyId: string) => {
    if (expandedJourneyId === journeyId) { setExpandedJourneyId(null); return }
    setExpandedJourneyId(journeyId)
    if (journeyDropoff[journeyId]) return
    setLoadingDropoff(journeyId)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/content-stats?journey_id=${journeyId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setJourneyDropoff(prev => ({ ...prev, [journeyId]: data.step_dropoff ?? [] }))
      }
    } finally {
      setLoadingDropoff(null)
    }
  }

  const handleProvision = async (planId: string, gateway: 'stripe' | 'razorpay' | 'both') => {
    setProvisioning(prev => ({ ...prev, [planId]: gateway }))
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/plans/${planId}/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ gateway }),
      })
      const data = await res.json()
      if (res.ok) {
        setPlans(prev => prev.map(p => {
          if (p.plan_id !== planId) return p
          const stripe = data.provisioned?.stripe ?? {}
          const razorpay = data.provisioned?.razorpay ?? {}
          return {
            ...p,
            stripe_price_id: stripe.stripe_price_id ?? p.stripe_price_id,
            razorpay_plan_id: razorpay.razorpay_plan_id ?? p.razorpay_plan_id,
          }
        }))
      } else {
        alert(data.detail ?? 'Provisioning failed.')
      }
    } finally {
      setProvisioning(prev => ({ ...prev, [planId]: null }))
    }
  }

  const handleCreatePlan = async () => {
    if (!newPlanForm.plan_id || !newPlanForm.name) return
    setCreatingPlan(true)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/admin/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          plan_id: newPlanForm.plan_id.toLowerCase().replace(/\s+/g, '_'),
          name: newPlanForm.name,
          base_price_cents: parseInt(newPlanForm.base_price_cents) || 0,
          base_price_inr_paise: parseInt(newPlanForm.base_price_inr_paise) || null,
          token_budget_cents: parseInt(newPlanForm.token_budget_cents) || 0,
          max_seats: parseInt(newPlanForm.max_seats) || 1,
        }),
      })
      const data = await res.json()
      if (res.ok) {
        setPlans(prev => [...prev, data.plan])
        setNewPlanForm({ plan_id: '', name: '', base_price_cents: '', base_price_inr_paise: '', token_budget_cents: '', max_seats: '1' })
      } else {
        alert(data.detail ?? 'Failed to create plan.')
      }
    } finally {
      setCreatingPlan(false)
    }
  }

  const totalMonthlyCost = usageByModel.reduce((s, r) => s + r.total_cost_cents, 0)

  return (
    <>
      <PageMeta title="Admin" />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-10">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 mb-8 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>

          <div className="flex items-center gap-3 mb-6">
            <Settings size={18} className="text-violet-500 dark:text-violet-400" />
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">Admin Panel</h1>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-8 p-1 glass-card rounded-xl w-fit flex-wrap">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={clsx(
                  'px-4 py-1.5 rounded-lg text-xs font-semibold transition-all',
                  tab === t.id
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Overview tab */}
          {tab === 'overview' && (
            <>
              {stats ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                  {[
                    { label: 'Total users',     value: stats.total_users },
                    { label: 'DAU',             value: stats.dau },
                    { label: 'Messages today',  value: stats.messages_today },
                    { label: 'Monthly API cost', value: `$${(stats.monthly_api_cost_cents / 100).toFixed(2)}` },
                  ].map(({ label, value }) => (
                    <div key={label} className="glass-card rounded-xl p-4">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-8">
                  <Loader2 size={14} className="animate-spin" /> Loading stats…
                </div>
              )}

              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Active Plans</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {plans.filter(p => p.is_active).map(p => (
                  <div key={p.plan_id} className="glass-card rounded-xl p-3 flex items-center justify-between">
                    <span className="text-xs text-slate-700 dark:text-slate-300 font-medium">{p.name}</span>
                    <span className="text-xs text-slate-500">
                      {p.base_price_cents === 0 ? 'Free' : `$${(p.base_price_cents / 100).toFixed(0)}/mo`}
                    </span>
                  </div>
                ))}
              </div>

              {/* Feature Usage section */}
              <div className="mt-8">
                <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">
                  Feature Usage — {new Date().toLocaleString('default', { month: 'long', year: 'numeric' })}
                </h2>

                {!featureUsage ? (
                  <div className="flex items-center gap-2 text-slate-500 text-sm mb-6">
                    <Loader2 size={14} className="animate-spin" /> Loading feature data…
                  </div>
                ) : (
                  <>
                    {/* Feature summary table */}
                    <div className="glass-card rounded-xl overflow-hidden mb-6">
                      {featureUsage.this_month.length === 0 ? (
                        <p className="text-xs text-slate-400 px-4 py-6 text-center">No feature usage data for this month yet.</p>
                      ) : (
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-slate-200 dark:border-slate-700">
                              <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Feature</th>
                              <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Users</th>
                              <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Requests</th>
                              <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Cost</th>
                              <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden md:table-cell">Cost/req</th>
                              <th className="px-4 py-2.5 text-slate-500 font-semibold hidden lg:table-cell w-40">Share</th>
                            </tr>
                          </thead>
                          <tbody>
                            {featureUsage.this_month.map(r => {
                              const totalCost = featureUsage.this_month.reduce((s, x) => s + Number(x.total_cost_cents), 0)
                              const share = totalCost > 0 ? (Number(r.total_cost_cents) / totalCost) * 100 : 0
                              return (
                                <tr key={r.interaction_type} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                                  <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                                    {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                                  </td>
                                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-500 hidden sm:table-cell">{r.unique_users}</td>
                                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-500">{Number(r.total_requests).toLocaleString()}</td>
                                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">{fmtCents(Number(r.total_cost_cents))}</td>
                                  <td className="px-4 py-2.5 text-right tabular-nums text-slate-400 hidden md:table-cell">
                                    {r.avg_cost_per_request_cents != null
                                      ? `$${Number(r.avg_cost_per_request_cents).toFixed(4)}`
                                      : '—'}
                                  </td>
                                  <td className="px-4 py-2.5 hidden lg:table-cell">
                                    <div className="flex items-center gap-2">
                                      <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                        <div className="h-full rounded-full bg-violet-500" style={{ width: `${share}%` }} />
                                      </div>
                                      <span className="text-[10px] tabular-nums text-slate-400 w-7 text-right shrink-0">{Math.round(share)}%</span>
                                    </div>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      )}
                    </div>

                    {/* 6-month trend grouped bar chart */}
                    <div className="glass-card rounded-xl p-5 mb-6">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">6-Month Cost Trend per Feature</h2>
                      {featureUsage.trend.length === 0 ? (
                        <p className="text-xs text-slate-400">No trend data yet.</p>
                      ) : (
                        <FeatureTrendChart trend={featureUsage.trend} />
                      )}
                    </div>

                    {/* Model distribution */}
                    <div className="glass-card rounded-xl p-5 mb-4">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Model Distribution</h2>
                      {featureUsage.models.length === 0 ? (
                        <p className="text-xs text-slate-400">No model data for this month yet.</p>
                      ) : (
                        <div className="space-y-2.5">
                          {featureUsage.models.map(m => {
                            const maxCount = Math.max(...featureUsage.models.map(x => x.message_count), 1)
                            return (
                              <div key={m.model_used} className="flex items-center gap-3">
                                <span className="text-xs font-mono text-slate-600 dark:text-slate-400 w-36 shrink-0 truncate">{m.model_used}</span>
                                <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-violet-500/70"
                                    style={{ width: `${(m.message_count / maxCount) * 100}%` }}
                                  />
                                </div>
                                <span className="text-xs tabular-nums text-slate-500 w-20 text-right shrink-0">
                                  {m.message_count.toLocaleString()} calls
                                </span>
                                <span className="text-xs tabular-nums text-slate-400 w-14 text-right shrink-0 hidden sm:block">
                                  {fmtCents(m.total_cost_cents)}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </>
          )}

          {/* Pricing plans tab */}
          {tab === 'plans' && (
            <>
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Pricing Preview</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
                {plans.map(plan => {
                  const Icon = PLAN_ICONS[plan.plan_id] ?? Zap
                  const features = PLAN_FEATURES[plan.plan_id] ?? []
                  return (
                    <div key={plan.plan_id} className="glass-card rounded-2xl p-4 flex flex-col">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                          <Icon size={14} className="text-violet-600 dark:text-violet-400" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-800 dark:text-slate-200">{plan.name}</p>
                          {plan.max_seats > 1 && <p className="text-[10px] text-slate-500">Up to {plan.max_seats} users</p>}
                        </div>
                      </div>
                      <div className="mb-3">
                        {plan.base_price_cents === 0
                          ? <span className="text-lg font-bold text-slate-800 dark:text-slate-100">Free</span>
                          : <><span className="text-lg font-bold text-slate-800 dark:text-slate-100">${(plan.base_price_cents / 100).toFixed(0)}</span><span className="text-[10px] text-slate-400">/mo</span></>
                        }
                      </div>
                      <ul className="space-y-1.5 flex-1">
                        {features.map(f => (
                          <li key={f} className="flex items-start gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                            <Check size={10} className="text-violet-500 dark:text-violet-400 mt-0.5 shrink-0" />{f}
                          </li>
                        ))}
                      </ul>
                      {!plan.is_active && (
                        <span className="mt-2 text-[10px] text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded self-start">inactive</span>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Create New Plan */}
              <div className="glass-card rounded-2xl p-5 mb-6">
                <div className="flex items-center gap-2 mb-4">
                  <Plus size={14} className="text-violet-500 dark:text-violet-400" />
                  <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Create New Plan</h2>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
                  <div>
                    <label className="text-xs text-slate-500">Plan ID slug</label>
                    <input value={newPlanForm.plan_id} onChange={e => setNewPlanForm(f => ({ ...f, plan_id: e.target.value }))} placeholder="individual" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Display Name</label>
                    <input value={newPlanForm.name} onChange={e => setNewPlanForm(f => ({ ...f, name: e.target.value }))} placeholder="Individual" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">USD $/mo (cents)</label>
                    <input type="number" min="0" value={newPlanForm.base_price_cents} onChange={e => setNewPlanForm(f => ({ ...f, base_price_cents: e.target.value }))} placeholder="999" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">INR ₹/mo (paise)</label>
                    <input type="number" min="0" value={newPlanForm.base_price_inr_paise} onChange={e => setNewPlanForm(f => ({ ...f, base_price_inr_paise: e.target.value }))} placeholder="79900" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Token budget (cents)</label>
                    <input type="number" min="0" value={newPlanForm.token_budget_cents} onChange={e => setNewPlanForm(f => ({ ...f, token_budget_cents: e.target.value }))} placeholder="5000" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">Max seats</label>
                    <input type="number" min="1" value={newPlanForm.max_seats} onChange={e => setNewPlanForm(f => ({ ...f, max_seats: e.target.value }))} className={inputCls} />
                  </div>
                </div>
                <button
                  onClick={handleCreatePlan}
                  disabled={creatingPlan || !newPlanForm.plan_id || !newPlanForm.name}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  {creatingPlan ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                  Create Plan
                </button>
              </div>

              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Edit Plan Configuration</h2>
              <div className="space-y-3">
                {plans.map(plan => {
                  const edit = edits[plan.plan_id] ?? {}
                  const isDirty = Object.keys(edit).length > 0
                  const currentTokenBudget = (edit.token_budget_cents as number | undefined) ?? plan.token_budget_cents
                  return (
                    <div key={plan.plan_id} className="glass-card rounded-xl p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">{plan.name}</span>
                          <span className="text-[10px] text-slate-400 font-mono">{plan.plan_id}</span>
                          {!plan.is_active && (
                            <span className="text-[10px] text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded">inactive</span>
                          )}
                        </div>
                        {isDirty && (
                          <button
                            onClick={() => handleSavePlan(plan.plan_id)}
                            disabled={saving === plan.plan_id}
                            className="flex items-center gap-1.5 text-xs bg-violet-600 hover:bg-violet-500 text-white px-3 py-1.5 rounded-lg transition-colors"
                          >
                            {saving === plan.plan_id ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                            Save
                          </button>
                        )}
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        <label className="text-xs text-slate-500">
                          USD Price (¢)
                          <input type="number" defaultValue={plan.base_price_cents} onChange={e => setEdit(plan.plan_id, 'base_price_cents', parseInt(e.target.value))} className={inputCls} />
                        </label>
                        {plan.base_price_cents > 0 && (
                          <label className="text-xs text-slate-500">
                            INR Price (paise)
                            <input type="number" defaultValue={plan.base_price_inr_paise ?? ''} placeholder="e.g. 79900" onChange={e => setEdit(plan.plan_id, 'base_price_inr_paise', parseInt(e.target.value) || null)} className={inputCls} />
                          </label>
                        )}
                        <label className="text-xs text-slate-500">
                          Token budget (cents)
                          <input type="number" defaultValue={plan.token_budget_cents} onChange={e => setEdit(plan.plan_id, 'token_budget_cents', parseInt(e.target.value))} className={inputCls} />
                          {currentTokenBudget > 0 && (
                            <span className="text-[10px] text-slate-400 mt-0.5 block">≈ ${(currentTokenBudget / 10000).toFixed(2)} of AI spend / month</span>
                          )}
                        </label>
                        <label className="text-xs text-slate-500">
                          Max seats
                          <input type="number" defaultValue={plan.max_seats} onChange={e => setEdit(plan.plan_id, 'max_seats', parseInt(e.target.value))} className={inputCls} />
                        </label>
                        <label className="text-xs text-slate-500 flex items-center gap-2 self-end pb-1.5">
                          <input type="checkbox" defaultChecked={plan.is_active} onChange={e => setEdit(plan.plan_id, 'is_active', e.target.checked)} />
                          Active
                        </label>
                      </div>

                      {/* Gateway Configuration */}
                      {plan.base_price_cents > 0 && (
                        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700/50">
                          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">Gateway Configuration</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
                            {/* Stripe */}
                            <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                              <div className="flex items-center gap-1.5 min-w-0">
                                {plan.stripe_price_id
                                  ? <Check size={11} className="text-emerald-500 shrink-0" />
                                  : <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                                }
                                <span className="text-[10px] font-mono text-slate-600 dark:text-slate-400 truncate">
                                  {plan.stripe_price_id ? `Stripe ${plan.stripe_price_id}` : 'Stripe: Not provisioned'}
                                </span>
                              </div>
                              <button
                                onClick={() => handleProvision(plan.plan_id, 'stripe')}
                                disabled={!!provisioning[plan.plan_id]}
                                className="text-[10px] shrink-0 flex items-center gap-1 px-2 py-1 rounded-md bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 hover:bg-violet-200 dark:hover:bg-violet-500/25 transition-colors disabled:opacity-50"
                              >
                                {provisioning[plan.plan_id] === 'stripe' && <Loader2 size={9} className="animate-spin" />}
                                {plan.stripe_price_id ? 'Re-provision' : 'Provision'}
                              </button>
                            </div>
                            {/* Razorpay */}
                            <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                              <div className="flex items-center gap-1.5 min-w-0">
                                {plan.razorpay_plan_id
                                  ? <Check size={11} className="text-emerald-500 shrink-0" />
                                  : <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                                }
                                <span className="text-[10px] font-mono text-slate-600 dark:text-slate-400 truncate">
                                  {plan.razorpay_plan_id ? `Razorpay ${plan.razorpay_plan_id}` : 'Razorpay: Not provisioned'}
                                </span>
                              </div>
                              <button
                                onClick={() => handleProvision(plan.plan_id, 'razorpay')}
                                disabled={!!provisioning[plan.plan_id]}
                                className="text-[10px] shrink-0 flex items-center gap-1 px-2 py-1 rounded-md bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 hover:bg-violet-200 dark:hover:bg-violet-500/25 transition-colors disabled:opacity-50"
                              >
                                {provisioning[plan.plan_id] === 'razorpay' && <Loader2 size={9} className="animate-spin" />}
                                {plan.razorpay_plan_id ? 'Re-provision' : 'Provision'}
                              </button>
                            </div>
                          </div>
                          <button
                            onClick={() => handleProvision(plan.plan_id, 'both')}
                            disabled={!!provisioning[plan.plan_id]}
                            className="w-full text-[10px] flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-violet-400 dark:hover:border-violet-500/50 transition-colors disabled:opacity-50"
                          >
                            {provisioning[plan.plan_id] === 'both' && <Loader2 size={9} className="animate-spin" />}
                            Provision Both Gateways
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {/* AI Providers tab */}
          {tab === 'ai' && (
            <>
              {/* ── Cost Analysis ─────────────────────────────────────────────── */}
              {costAnalysis && (
                <>
                  {/* 1. Cost vs Revenue by Plan */}
                  <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cost vs Revenue by Plan</h2>
                  <div className="glass-card rounded-xl overflow-hidden mb-6">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700">
                          <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Plan</th>
                          <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Users</th>
                          <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Avg/user</th>
                          <th className="text-right px-4 py-2.5 text-slate-500 font-semibold hidden sm:table-cell">Max/user</th>
                          <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Cost/Rev%</th>
                          <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Health</th>
                        </tr>
                      </thead>
                      <tbody>
                        {costAnalysis.plan_margins.map(r => {
                          const pct = Number(r.cost_revenue_pct)
                          const health = pct >= 60
                            ? { label: 'At risk', cls: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10' }
                            : pct >= 30
                              ? { label: 'Watch', cls: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10' }
                              : { label: 'Healthy', cls: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10' }
                          return (
                            <tr key={r.plan_id} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                              <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300 font-medium">{r.plan_name}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400">{r.active_users}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400 hidden sm:table-cell">{fmtCents(r.avg_spent_cents)}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400 hidden sm:table-cell">{fmtCents(r.max_spent_cents)}</td>
                              <td className="px-4 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-400">
                                {r.price_cents > 0 ? `${pct}%` : '—'}
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                {r.price_cents > 0 ? (
                                  <span className={clsx('text-[10px] font-semibold px-1.5 py-0.5 rounded', health.cls)}>{health.label}</span>
                                ) : <span className="text-[10px] text-slate-400">—</span>}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* 2. Users Near Budget Limit */}
                  {costAnalysis.at_risk_users.length > 0 && (
                    <>
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={13} className="text-amber-500 shrink-0" />
                        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                          Users Near Budget Limit
                          <span className="ml-2 text-amber-500">({costAnalysis.at_risk_users.length} above 75%)</span>
                        </h2>
                      </div>
                      <div className="glass-card rounded-xl overflow-hidden mb-6">
                        <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                          {costAnalysis.at_risk_users.map(u => {
                            const isExpanded = expandedUid === u.uid
                            const detail = userDetails[u.uid]
                            const isLoadingThis = loadingDetail === u.uid
                            const pct = Math.min(100, u.pct_used)
                            const barColor = pct >= 90 ? 'bg-rose-500' : 'bg-amber-400'
                            const txtColor = pct >= 90 ? 'text-rose-500' : 'text-amber-500'
                            return (
                              <div key={u.uid}>
                                <div
                                  className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                                  onClick={() => handleExpandUser(u.uid)}
                                >
                                  <div className="min-w-0 flex-1">
                                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{u.display_name ?? u.email ?? u.uid}</p>
                                    <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                                  </div>
                                  <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono shrink-0 hidden sm:block">{u.plan_id}</span>
                                  <div className="shrink-0 flex flex-col items-end gap-0.5 w-32">
                                    <div className="flex items-center gap-1.5 w-full">
                                      <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                                        <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
                                      </div>
                                      <span className={clsx('text-[10px] tabular-nums font-semibold w-10 text-right', txtColor)}>{u.pct_used}%</span>
                                    </div>
                                    <span className="text-[10px] text-slate-400 tabular-nums">{fmtCents(u.spent_cents)} / {fmtCents(u.budget_cents)}</span>
                                  </div>
                                  <div className="text-slate-400 shrink-0">
                                    {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                                  </div>
                                </div>

                                {isExpanded && (
                                  <div className="border-t border-slate-100 dark:border-slate-700/50 px-4 pb-5 pt-4">
                                    {isLoadingThis && (
                                      <div className="flex items-center gap-2 text-slate-400 text-xs py-4 justify-center">
                                        <Loader2 size={13} className="animate-spin" /> Loading usage detail…
                                      </div>
                                    )}
                                    {!isLoadingThis && !detail && (
                                      <p className="text-xs text-slate-400 text-center py-4">Failed to load detail.</p>
                                    )}
                                    {!isLoadingThis && detail && (
                                      <div className="space-y-5">
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                          {[
                                            { label: 'Plan', value: detail.profile.plan_name },
                                            { label: 'Status', value: detail.profile.sub_status },
                                            { label: 'Streak', value: `${detail.profile.streak_days} days` },
                                            { label: 'Last active', value: detail.profile.last_active_date ? new Date(detail.profile.last_active_date).toLocaleDateString() : '—' },
                                          ].map(({ label, value }) => (
                                            <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5">
                                              <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                                              <p className="font-medium text-slate-700 dark:text-slate-200 mt-0.5 truncate">{value}</p>
                                            </div>
                                          ))}
                                        </div>
                                        <div>
                                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                                            <BarChart2 size={11} /> This Month
                                          </p>
                                          {(() => {
                                            const spent = detail.current_month.spent_cents
                                            const budget = detail.current_month.budget_cents ?? 0
                                            const p = calcPct(spent, budget)
                                            const barCls = p >= 90 ? 'bg-rose-500' : p >= 70 ? 'bg-amber-400' : 'bg-emerald-500'
                                            const txtCls = p >= 90 ? 'text-rose-500' : p >= 70 ? 'text-amber-500' : 'text-emerald-600 dark:text-emerald-400'
                                            return (
                                              <div className="mb-3">
                                                <div className="flex items-center justify-between text-xs mb-1">
                                                  <span className="text-slate-600 dark:text-slate-300">{fmtCents(spent)}<span className="text-slate-400"> / {fmtCents(budget)}</span></span>
                                                  <span className={clsx('font-semibold tabular-nums', txtCls)}>{fmtPct(spent, budget)}</span>
                                                </div>
                                                <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                                  <div className={clsx('h-full rounded-full', barCls)} style={{ width: `${Math.max(spent > 0 ? 0.5 : 0, p)}%` }} />
                                                </div>
                                              </div>
                                            )
                                          })()}
                                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                            {[
                                              { label: 'Requests', value: String(detail.current_month.message_count) },
                                              { label: 'Input tokens', value: fmtTokens(detail.current_month.input_tokens) },
                                              { label: 'Output tokens', value: fmtTokens(detail.current_month.output_tokens) },
                                              { label: 'Cached tokens', value: fmtTokens(detail.current_month.cached_input_tokens) },
                                            ].map(({ label, value }) => (
                                              <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5 text-xs">
                                                <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                                                <p className="font-bold text-slate-800 dark:text-slate-100 tabular-nums mt-0.5">{value}</p>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                        {detail.breakdown.length > 0 && (
                                          <div>
                                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Usage by Feature</p>
                                            <div className="space-y-1.5">
                                              {detail.breakdown.map(r => (
                                                <div key={r.interaction_type} className="flex items-center gap-2 text-xs">
                                                  <span className="text-slate-600 dark:text-slate-400 w-28 shrink-0 truncate">{INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}</span>
                                                  <span className="tabular-nums text-slate-500">{r.request_count} req</span>
                                                  <span className="tabular-nums text-slate-500 ml-auto">{fmtCents(r.estimated_cost_cents)}</span>
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </>
                  )}

                  {/* 3. Cost by Feature */}
                  {costAnalysis.by_interaction.length > 0 && (
                    <>
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cost by Feature (this month)</h2>
                      <div className="glass-card rounded-xl p-4 mb-6">
                        {(() => {
                          const maxCost = Math.max(...costAnalysis.by_interaction.map(r => r.total_cost_cents), 1)
                          return (
                            <div className="space-y-2.5">
                              {costAnalysis.by_interaction.map(r => (
                                <div key={r.interaction_type} className="flex items-center gap-3">
                                  <span className="text-xs text-slate-600 dark:text-slate-400 w-28 shrink-0 truncate">
                                    {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                                  </span>
                                  <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                    <div className="h-full rounded-full bg-violet-500" style={{ width: `${(r.total_cost_cents / maxCost) * 100}%` }} />
                                  </div>
                                  <span className="text-xs tabular-nums font-medium text-slate-700 dark:text-slate-300 w-14 text-right shrink-0">
                                    {fmtCents(r.total_cost_cents)}
                                  </span>
                                  <span className="text-[10px] tabular-nums text-slate-400 w-16 text-right shrink-0 hidden sm:block">
                                    {(r.total_requests ?? 0).toLocaleString()} req
                                  </span>
                                </div>
                              ))}
                            </div>
                          )
                        })()}
                      </div>
                    </>
                  )}

                  {/* 4. Cache Hit Rate trend (6 months) */}
                  {costAnalysis.cache_trend.length > 0 && (
                    <>
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Cache Hit Rate (6 months)</h2>
                      <div className="glass-card rounded-xl p-4 mb-8">
                        <div className="flex items-end gap-2 h-16">
                          {costAnalysis.cache_trend.map(r => {
                            const pct = Number(r.cache_hit_pct)
                            return (
                              <div
                                key={r.period_start}
                                className="flex-1 flex flex-col justify-end min-w-0"
                                title={`${fmtMonth(r.period_start)}: ${pct}% cache hit`}
                              >
                                <div
                                  className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t"
                                  style={{ height: `${Math.max(pct, 4)}%` }}
                                />
                              </div>
                            )
                          })}
                        </div>
                        <div className="flex gap-2 mt-2">
                          {costAnalysis.cache_trend.map(r => (
                            <div key={r.period_start} className="flex-1 text-center min-w-0">
                              <p className="text-[9px] text-slate-400 truncate">{fmtMonth(r.period_start)}</p>
                              <p className="text-[9px] font-semibold text-violet-500 tabular-nums">{r.cache_hit_pct}%</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  <div className="border-t border-slate-200 dark:border-slate-700/50 mb-8" />
                </>
              )}

              {/* Usage breakdown */}
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Usage This Month</h2>
              {usageByModel.length > 0 ? (
                <div className="glass-card rounded-xl overflow-hidden mb-8">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700">
                        <th className="text-left px-4 py-2.5 text-slate-500 font-semibold">Model</th>
                        <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Messages</th>
                        <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Est. Cost</th>
                        <th className="text-right px-4 py-2.5 text-slate-500 font-semibold">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageByModel.map(r => (
                        <tr key={r.model_used} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              <Cpu size={11} className="text-slate-400 shrink-0" />
                              <span className="font-mono text-slate-700 dark:text-slate-300">{r.model_used}</span>
                              {r.model_used.startsWith('gpt') || r.model_used.startsWith('o1')
                                ? <span className="text-[9px] bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5 rounded-full">OpenAI</span>
                                : <span className="text-[9px] bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 px-1.5 py-0.5 rounded-full">Anthropic</span>
                              }
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{r.message_count.toLocaleString()}</td>
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">${(r.total_cost_cents / 100).toFixed(4)}</td>
                          <td className="px-4 py-2.5 text-right text-slate-500">
                            {totalMonthlyCost > 0 ? `${Math.round((r.total_cost_cents / totalMonthlyCost) * 100)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="bg-slate-50 dark:bg-slate-800/50">
                        <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300 font-semibold">Total</td>
                        <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-300 font-semibold">
                          {usageByModel.reduce((s, r) => s + r.message_count, 0).toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-300 font-semibold">
                          ${(totalMonthlyCost / 100).toFixed(4)}
                        </td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-400 mb-8">No usage data yet this month.</p>
              )}

              {/* Daily chart — simple bar */}
              {dailyUsage.length > 0 && (
                <div className="glass-card rounded-xl p-4 mb-8">
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-3">Daily Messages (last 14 days)</p>
                  <div className="flex items-end gap-1 h-16">
                    {dailyUsage.map(d => {
                      const max = Math.max(...dailyUsage.map(x => x.messages), 1)
                      const pct = Math.round((d.messages / max) * 100)
                      return (
                        <div key={d.day} className="flex-1 flex flex-col items-center gap-1" title={`${d.day}: ${d.messages}`}>
                          <div className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t" style={{ height: `${Math.max(pct, 4)}%` }} />
                        </div>
                      )
                    })}
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-[9px] text-slate-400">{dailyUsage[0]?.day}</span>
                    <span className="text-[9px] text-slate-400">{dailyUsage[dailyUsage.length - 1]?.day}</span>
                  </div>
                </div>
              )}

              {/* Provider / model config per interaction type */}
              <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Model Routing</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Set which provider and model handles each interaction type. Changes take effect immediately for new conversations.
              </p>
              <div className="space-y-3">
                {aiConfigs.map(cfg => {
                  const pending = aiEdits[cfg.interaction_type] ?? cfg
                  const isDirty = !!aiEdits[cfg.interaction_type]
                  const models = availableModels[pending.provider] ?? []

                  return (
                    <div key={cfg.interaction_type} className="glass-card rounded-xl p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                            {INTERACTION_LABELS[cfg.interaction_type] ?? cfg.interaction_type}
                          </p>
                          <p className="text-[10px] text-slate-400 font-mono">{cfg.interaction_type}</p>
                        </div>
                        {isDirty && (
                          <button
                            onClick={() => handleSaveAI(cfg.interaction_type)}
                            disabled={savingAI === cfg.interaction_type}
                            className="flex items-center gap-1.5 text-xs bg-violet-600 hover:bg-violet-500 text-white px-3 py-1.5 rounded-lg transition-colors"
                          >
                            {savingAI === cfg.interaction_type ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                            Save
                          </button>
                        )}
                      </div>

                      <div className="flex gap-3 flex-wrap">
                        <label className="text-xs text-slate-500">
                          Provider
                          <select
                            value={pending.provider}
                            onChange={e => setAiEdit(cfg.interaction_type, 'provider', e.target.value)}
                            className={`block mt-1 ${selectCls}`}
                          >
                            {Object.keys(availableModels).map(p => (
                              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                            ))}
                          </select>
                        </label>
                        <label className="text-xs text-slate-500 flex-1 min-w-[180px]">
                          Model
                          <select
                            value={pending.model}
                            onChange={e => setAiEdit(cfg.interaction_type, 'model', e.target.value)}
                            className={`block mt-1 w-full ${selectCls}`}
                          >
                            {models.map(m => (
                              <option key={m.id} value={m.id}>{m.label}</option>
                            ))}
                          </select>
                        </label>
                        <div className="text-xs text-slate-400 self-end pb-1.5">
                          {pending.provider === 'anthropic' ? '🟣 Anthropic' : '🟢 OpenAI'}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {/* Users tab */}
          {tab === 'users' && (
            <>
              <div className="flex items-center justify-between gap-3 mb-4">
                <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 shrink-0">
                  Users ({filteredUsers.length}{userSearch ? ` of ${users.length}` : ''})
                </h2>
                <div className="flex items-center gap-2 glass-card rounded-lg px-3 py-1.5 max-w-xs w-full">
                  <Search size={12} className="text-slate-400 shrink-0" />
                  <input
                    type="text"
                    value={userSearch}
                    onChange={e => setUserSearch(e.target.value)}
                    placeholder="Search by name, email or UID…"
                    className="bg-transparent text-xs text-slate-700 dark:text-slate-200 placeholder-slate-400 outline-none w-full"
                  />
                </div>
              </div>

              <div className="space-y-2">
                {filteredUsers.length === 0 && (
                  <p className="text-xs text-slate-400 py-4 text-center">No users match "{userSearch}"</p>
                )}
                {filteredUsers.map(u => {
                  const isExpanded = expandedUid === u.uid
                  const detail = userDetails[u.uid]
                  const isLoadingThis = loadingDetail === u.uid
                  const pct = calcPct(u.spent_cents, u.budget_cents ?? 0)
                  const barColor = pct >= 90 ? 'bg-rose-500' : pct >= 70 ? 'bg-amber-400' : 'bg-emerald-500'

                  return (
                    <div key={u.uid} className="glass-card rounded-xl overflow-hidden">
                      {/* Row */}
                      <div
                        className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                        onClick={() => handleExpandUser(u.uid)}
                      >
                        {/* Identity */}
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                            {u.display_name ?? 'Unknown'}
                            {u.is_admin && (
                              <span className="ml-2 text-[10px] text-violet-600 dark:text-violet-300 bg-violet-100 dark:bg-violet-500/20 px-1.5 py-0.5 rounded-full">admin</span>
                            )}
                          </p>
                          <p className="text-[11px] text-slate-500 truncate">{u.email ?? u.uid}</p>
                        </div>

                        {/* Plan badge */}
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono shrink-0 hidden sm:block">{u.plan_id}</span>

                        {/* Mini usage bar */}
                        <div className="shrink-0 hidden sm:flex flex-col items-end gap-0.5 w-28">
                          <div className="flex items-center gap-1.5 w-full">
                            <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                              <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${Math.max(pct > 0 ? 2 : 0, pct)}%` }} />
                            </div>
                            <span className={clsx(
                              'text-[10px] tabular-nums font-medium w-10 text-right',
                              pct >= 90 ? 'text-rose-500' : pct >= 70 ? 'text-amber-500' : 'text-slate-500'
                            )}>{fmtPct(u.spent_cents, u.budget_cents ?? 0)}</span>
                          </div>
                          <span className="text-[10px] text-slate-400 tabular-nums">
                            {fmtCents(u.spent_cents)} / {fmtCents(u.budget_cents ?? 0)}
                          </span>
                        </div>

                        {/* Message count */}
                        <span className="text-[10px] text-slate-400 tabular-nums shrink-0 hidden md:block w-16 text-right">
                          {u.message_count} req
                        </span>

                        {/* Actions */}
                        <div className="flex items-center gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => handleToggleAdmin(u.uid)}
                            disabled={togglingUid === u.uid}
                            title={u.is_admin ? 'Revoke admin' : 'Grant admin'}
                            className={clsx(
                              'flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-all',
                              u.is_admin
                                ? 'text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20'
                                : 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 hover:bg-violet-100 dark:hover:bg-violet-500/20'
                            )}
                          >
                            {togglingUid === u.uid ? <Loader2 size={11} className="animate-spin" /> : u.is_admin ? <ShieldOff size={11} /> : <ShieldCheck size={11} />}
                            <span className="hidden sm:inline">{u.is_admin ? 'Revoke' : 'Grant'}</span>
                          </button>
                        </div>

                        <div className="text-slate-400 shrink-0">
                          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        </div>
                      </div>

                      {/* Expanded detail panel */}
                      {isExpanded && (
                        <div className="border-t border-slate-100 dark:border-slate-700/50 px-4 pb-5 pt-4">
                          {isLoadingThis && (
                            <div className="flex items-center gap-2 text-slate-400 text-xs py-4 justify-center">
                              <Loader2 size={13} className="animate-spin" /> Loading usage detail…
                            </div>
                          )}

                          {!isLoadingThis && !detail && (
                            <p className="text-xs text-slate-400 text-center py-4">Failed to load detail.</p>
                          )}

                          {!isLoadingThis && detail && (
                            <div className="space-y-5">

                              {/* Profile meta */}
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                {[
                                  { label: 'Plan', value: detail.profile.plan_name },
                                  { label: 'Status', value: detail.profile.sub_status },
                                  { label: 'Streak', value: `${detail.profile.streak_days} days` },
                                  { label: 'Age group', value: detail.profile.age_group_flag ?? '—' },
                                  { label: 'Last active', value: detail.profile.last_active_date ? new Date(detail.profile.last_active_date).toLocaleDateString() : '—' },
                                  { label: 'Joined', value: new Date(detail.profile.created_at).toLocaleDateString() },
                                  { label: 'Gateway', value: detail.profile.payment_gateway ?? '—' },
                                  { label: 'Account', value: detail.profile.account_status },
                                ].map(({ label, value }) => (
                                  <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5">
                                    <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                                    <p className="font-medium text-slate-700 dark:text-slate-200 mt-0.5 truncate">{value}</p>
                                  </div>
                                ))}
                              </div>

                              {/* Current month usage */}
                              <div>
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                                  <BarChart2 size={11} /> This Month
                                </p>

                                {/* Budget bar */}
                                {(() => {
                                  const spent = detail.current_month.spent_cents
                                  const budget = detail.current_month.budget_cents ?? 0
                                  const p = calcPct(spent, budget)
                                  const barCls = p >= 90 ? 'bg-rose-500' : p >= 70 ? 'bg-amber-400' : 'bg-emerald-500'
                                  const txtCls = p >= 90 ? 'text-rose-500' : p >= 70 ? 'text-amber-500' : 'text-emerald-600 dark:text-emerald-400'
                                  return (
                                    <div className="mb-3">
                                      <div className="flex items-center justify-between text-xs mb-1">
                                        <span className="text-slate-600 dark:text-slate-300">
                                          {fmtCents(spent)}
                                          <span className="text-slate-400"> / {fmtCents(budget)}</span>
                                        </span>
                                        <span className={clsx('font-semibold tabular-nums', txtCls)}>
                                          {fmtPct(spent, budget)}
                                        </span>
                                      </div>
                                      <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                        <div
                                          className={clsx('h-full rounded-full', barCls)}
                                          style={{ width: `${Math.max(spent > 0 ? 0.5 : 0, p)}%` }}
                                        />
                                      </div>
                                    </div>
                                  )
                                })()}

                                {/* Token stat chips */}
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                  {[
                                    { label: 'Requests', value: String(detail.current_month.message_count) },
                                    { label: 'Input tokens', value: fmtTokens(detail.current_month.input_tokens) },
                                    { label: 'Output tokens', value: fmtTokens(detail.current_month.output_tokens) },
                                    { label: 'Cached tokens', value: fmtTokens(detail.current_month.cached_input_tokens) },
                                  ].map(({ label, value }) => (
                                    <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5 text-xs">
                                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                                      <p className="font-bold text-slate-800 dark:text-slate-100 tabular-nums mt-0.5">{value}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* Breakdown by feature */}
                              {detail.breakdown.length > 0 && (
                                <div>
                                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Usage by Feature</p>
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr className="border-b border-slate-100 dark:border-slate-700/60">
                                          <th className="text-left py-1.5 pr-3 text-slate-400 font-semibold">Feature</th>
                                          <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">Req</th>
                                          <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">In</th>
                                          <th className="text-right py-1.5 px-2 text-slate-400 font-semibold">Out</th>
                                          <th className="text-right py-1.5 pl-2 text-slate-400 font-semibold">Cost</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                                        {detail.breakdown.map(r => (
                                          <tr key={r.interaction_type}>
                                            <td className="py-1.5 pr-3 text-slate-700 dark:text-slate-300 font-medium">
                                              {INTERACTION_LABELS[r.interaction_type] ?? r.interaction_type}
                                            </td>
                                            <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{r.request_count}</td>
                                            <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{fmtTokens(r.input_tokens)}</td>
                                            <td className="py-1.5 px-2 text-right tabular-nums text-slate-500">{fmtTokens(r.output_tokens)}</td>
                                            <td className="py-1.5 pl-2 text-right tabular-nums font-medium text-slate-700 dark:text-slate-300">{fmtCents(r.estimated_cost_cents)}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}

                              {/* Monthly history */}
                              {detail.history.length > 0 && (
                                <div>
                                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">12-Month History</p>
                                  <div className="space-y-1.5">
                                    {(() => {
                                      const maxCost = Math.max(...detail.history.map(r => r.estimated_cost_cents), 1)
                                      return detail.history.map(r => (
                                        <div key={r.period_start} className="flex items-center gap-2">
                                          <span className="text-[10px] text-slate-400 w-14 shrink-0">{fmtMonth(r.period_start)}</span>
                                          <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                            <div
                                              className="h-full rounded-full bg-violet-500"
                                              style={{ width: `${(r.estimated_cost_cents / maxCost) * 100}%` }}
                                            />
                                          </div>
                                          <span className="text-[10px] tabular-nums text-slate-500 w-10 text-right">{fmtCents(r.estimated_cost_cents)}</span>
                                          <span className="text-[10px] tabular-nums text-slate-400 w-10 text-right hidden sm:block">{r.message_count} req</span>
                                        </div>
                                      ))
                                    })()}
                                  </div>
                                </div>
                              )}

                              {/* Lifetime stats */}
                              <div>
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Lifetime</p>
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                                  {[
                                    { label: 'Total cost', value: fmtCents(detail.lifetime.lifetime_cost_cents) },
                                    { label: 'Total requests', value: String(detail.lifetime.lifetime_message_count) },
                                    { label: 'Chat messages', value: String(detail.lifetime.lifetime_chat_messages) },
                                    { label: 'Conversations', value: String(detail.lifetime.total_conversations) },
                                    { label: 'Input tokens', value: fmtTokens(detail.lifetime.lifetime_input_tokens) },
                                    { label: 'First active', value: detail.lifetime.first_active_month ? fmtMonth(detail.lifetime.first_active_month) : '—' },
                                  ].map(({ label, value }) => (
                                    <div key={label} className="bg-slate-50 dark:bg-slate-800/40 rounded-lg p-2.5">
                                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                                      <p className="font-bold text-slate-800 dark:text-slate-100 tabular-nums mt-0.5">{value}</p>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* Coupon redemptions */}
                              {detail.coupons.length > 0 && (
                                <div>
                                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Coupons Redeemed</p>
                                  <div className="space-y-1.5">
                                    {detail.coupons.map(c => (
                                      <div key={c.code} className="flex items-center gap-3 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-lg px-3 py-2">
                                        <code className={clsx(
                                          'font-bold px-1.5 py-0.5 rounded text-[10px]',
                                          c.is_active
                                            ? 'text-violet-700 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/15'
                                            : 'text-slate-500 bg-slate-200 dark:bg-slate-700'
                                        )}>{c.code}</code>
                                        <span className="text-slate-600 dark:text-slate-400 flex-1 truncate">{c.description}</span>
                                        {c.credit_applied_cents > 0 && (
                                          <span className="text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0">+{fmtCents(c.credit_applied_cents)}</span>
                                        )}
                                        {c.bonus_messages_applied > 0 && (
                                          <span className="text-blue-600 dark:text-blue-400 tabular-nums shrink-0">+{c.bonus_messages_applied} msg</span>
                                        )}
                                        {!c.is_active && (
                                          <span className="text-slate-400 text-[10px] shrink-0">expired</span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {/* Revenue tab */}
          {tab === 'revenue' && (
            <>
              {!revenue ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <Loader2 size={14} className="animate-spin" /> Loading revenue data…
                </div>
              ) : (
                <>
                  {/* Summary cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                    {[
                      { label: 'MRR (USD)', value: `$${(revenue.summary.total_mrr_usd_cents / 100).toFixed(2)}` },
                      { label: 'MRR (INR)', value: `₹${(revenue.summary.total_mrr_inr_paise / 100).toFixed(0)}` },
                      { label: 'Paid users', value: String(revenue.summary.total_paid_users) },
                      { label: 'ARPU (USD)', value: `$${(revenue.summary.arpu_usd_cents / 100).toFixed(2)}` },
                    ].map(({ label, value }) => (
                      <div key={label} className="glass-card rounded-xl p-4">
                        <p className="text-xs text-slate-500 mb-1">{label}</p>
                        <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Plan Distribution */}
                  <div className="glass-card rounded-xl p-5 mb-4">
                    <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Plan Distribution</h2>
                    {revenue.plan_distribution.length === 0 ? (
                      <p className="text-xs text-slate-400">No active subscriptions yet.</p>
                    ) : (() => {
                      const maxCount = Math.max(...revenue.plan_distribution.map(p => p.user_count), 1)
                      return (
                        <div className="space-y-3">
                          {revenue.plan_distribution.map(p => (
                            <div key={p.plan_id} className="flex items-center gap-3">
                              <span className="text-xs text-slate-700 dark:text-slate-300 w-24 shrink-0 font-medium truncate">{p.plan_name}</span>
                              <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-violet-500"
                                  style={{ width: `${(p.user_count / maxCount) * 100}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-500 w-14 text-right tabular-nums shrink-0">{p.user_count} users</span>
                              <span className="text-xs text-slate-400 w-20 text-right tabular-nums hidden sm:block shrink-0">
                                {p.mrr_usd_cents > 0
                                  ? `$${(p.mrr_usd_cents / 100).toFixed(0)}/mo`
                                  : p.mrr_inr_paise > 0
                                    ? `₹${(p.mrr_inr_paise / 100).toFixed(0)}/mo`
                                    : '—'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )
                    })()}
                  </div>

                  {/* Status Breakdown + Gateway Split */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="glass-card rounded-xl p-5">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Status Breakdown</h2>
                      {(() => {
                        const total = revenue.status_breakdown.reduce((s, r) => s + r.user_count, 0)
                        const colors: Record<string, string> = {
                          active: 'bg-emerald-500',
                          trialing: 'bg-violet-500',
                          cancelled: 'bg-rose-400',
                          no_subscription: 'bg-slate-300 dark:bg-slate-600',
                        }
                        const labels: Record<string, string> = {
                          active: 'Active',
                          trialing: 'Trial',
                          cancelled: 'Cancelled',
                          no_subscription: 'Free',
                        }
                        return (
                          <div className="space-y-2.5">
                            {revenue.status_breakdown.map(r => (
                              <div key={r.status} className="flex items-center gap-2">
                                <span className="text-xs text-slate-600 dark:text-slate-400 w-20 shrink-0">
                                  {labels[r.status] ?? r.status}
                                </span>
                                <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                  <div
                                    className={clsx('h-full rounded-full', colors[r.status] ?? 'bg-slate-400')}
                                    style={{ width: `${total > 0 ? (r.user_count / total) * 100 : 0}%` }}
                                  />
                                </div>
                                <span className="text-xs tabular-nums text-slate-500 w-8 text-right shrink-0">{r.user_count}</span>
                              </div>
                            ))}
                          </div>
                        )
                      })()}
                    </div>

                    <div className="glass-card rounded-xl p-5">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Gateway Split</h2>
                      {revenue.gateway_split.length === 0 ? (
                        <p className="text-xs text-slate-400">No paid subscriptions yet.</p>
                      ) : (() => {
                        const totalSubs = revenue.gateway_split.reduce((s, r) => s + r.subscriptions, 0)
                        return (
                          <div className="space-y-2.5">
                            {revenue.gateway_split.map(r => (
                              <div key={r.payment_gateway} className="flex items-center gap-2">
                                <span className="text-xs text-slate-600 dark:text-slate-400 w-28 shrink-0">
                                  {r.payment_gateway === 'stripe' ? 'Stripe (USD)' : r.payment_gateway === 'razorpay' ? 'Razorpay (INR)' : r.payment_gateway}
                                </span>
                                <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                  <div
                                    className={clsx('h-full rounded-full', r.payment_gateway === 'stripe' ? 'bg-violet-500' : 'bg-amber-400')}
                                    style={{ width: `${totalSubs > 0 ? (r.subscriptions / totalSubs) * 100 : 0}%` }}
                                  />
                                </div>
                                <div className="text-right shrink-0">
                                  <p className="text-xs tabular-nums text-slate-500">{r.subscriptions} subs</p>
                                  <p className="text-[10px] tabular-nums text-slate-400">
                                    {r.total_usd_cents > 0
                                      ? `$${(r.total_usd_cents / 100).toFixed(0)}/mo`
                                      : r.total_inr_paise > 0
                                        ? `₹${(r.total_inr_paise / 100).toFixed(0)}/mo`
                                        : '—'}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                </>
              )}
            </>
          )}

          {/* Retention tab */}
          {tab === 'retention' && (
            <>
              {!retentionData ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <Loader2 size={14} className="animate-spin" /> Loading retention data…
                </div>
              ) : (
                <>
                  {/* Active user cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                    {[
                      { label: 'DAU',        value: String(retentionData.active_users.dau) },
                      { label: 'WAU',        value: String(retentionData.active_users.wau) },
                      { label: 'MAU',        value: String(retentionData.active_users.mau) },
                      { label: 'Stickiness', value: `${retentionData.active_users.stickiness}%` },
                    ].map(({ label, value }) => (
                      <div key={label} className="glass-card rounded-xl p-4">
                        <p className="text-xs text-slate-500 mb-1">{label}</p>
                        <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Retention bars */}
                  <div className="glass-card rounded-xl p-5 mb-6">
                    <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1">Retention</h2>
                    <p className="text-xs text-slate-400 mb-4">
                      {retentionData.retention.cohort_size} users who signed up in {retentionData.retention.cohort_window}
                    </p>
                    <div className="space-y-3">
                      {([
                        { label: 'D1',  pct: retentionData.retention.d1_pct,  count: retentionData.retention.d1_count,  desc: 'came back next day' },
                        { label: 'D7',  pct: retentionData.retention.d7_pct,  count: retentionData.retention.d7_count,  desc: 'active in week 2' },
                        { label: 'D30', pct: retentionData.retention.d30_pct, count: retentionData.retention.d30_count, desc: 'active in month 2' },
                      ] as { label: string; pct: number; count: number; desc: string }[]).map(({ label, pct, count, desc }) => (
                        <div key={label} className="flex items-center gap-3">
                          <span className="text-xs font-mono text-slate-500 w-7 shrink-0">{label}</span>
                          <div className="flex-1 h-3 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-violet-500"
                              style={{ width: `${Math.max(pct > 0 ? 1 : 0, pct)}%` }}
                            />
                          </div>
                          <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 w-12 text-right shrink-0">{pct}%</span>
                          <span className="text-[11px] text-slate-400 hidden sm:block">({count} {desc})</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Weekly signups bar chart */}
                  {retentionData.weekly_signups.length > 0 && (
                    <div className="glass-card rounded-xl p-5 mb-6">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Weekly New Signups (last 12 weeks)</h2>
                      {(() => {
                        const maxVal = Math.max(...retentionData.weekly_signups.map(w => w.new_users), 1)
                        return (
                          <>
                            <div className="flex items-end gap-1 h-20">
                              {retentionData.weekly_signups.map(w => {
                                const barPct = Math.round((w.new_users / maxVal) * 100)
                                return (
                                  <div
                                    key={w.week_start}
                                    className="flex-1 flex flex-col justify-end min-w-0"
                                    title={`${w.week_start}: ${w.new_users} signups`}
                                  >
                                    <div
                                      className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t"
                                      style={{ height: `${Math.max(barPct, 4)}%` }}
                                    />
                                  </div>
                                )
                              })}
                            </div>
                            <div className="flex justify-between mt-2">
                              <span className="text-[9px] text-slate-400">
                                {retentionData.weekly_signups[0]?.week_start}
                              </span>
                              <span className="text-[9px] text-slate-400">
                                {retentionData.weekly_signups[retentionData.weekly_signups.length - 1]?.week_start}
                              </span>
                            </div>
                          </>
                        )
                      })()}
                    </div>
                  )}

                  {/* Inactive users */}
                  <div className="glass-card rounded-xl overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                        Inactive Users (14+ days no activity)
                        <span className="ml-2 text-xs font-normal text-slate-400">{retentionData.inactive_users.length} shown</span>
                      </h2>
                    </div>
                    {retentionData.inactive_users.length === 0 ? (
                      <p className="text-xs text-slate-400 px-5 py-6 text-center">No inactive users — great retention!</p>
                    ) : (
                      <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                        {retentionData.inactive_users.map(u => {
                          const today = new Date()
                          const signupDate = u.signup_date ? new Date(u.signup_date) : null
                          const lastActive = u.last_active_date ? new Date(u.last_active_date) : null
                          const daysSinceSignup = signupDate
                            ? Math.floor((today.getTime() - signupDate.getTime()) / 86_400_000)
                            : null
                          const daysSinceActive = lastActive
                            ? Math.floor((today.getTime() - lastActive.getTime()) / 86_400_000)
                            : null
                          return (
                            <div key={u.uid} className="px-5 py-3 flex items-center gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                                  {u.display_name ?? u.email ?? u.uid}
                                </p>
                                <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                              </div>
                              <span className="text-[10px] font-mono text-slate-400 shrink-0 hidden sm:block">{u.plan_id}</span>
                              <div className="shrink-0 text-right">
                                <p className="text-[10px] text-slate-500">
                                  {daysSinceSignup !== null ? `joined ${daysSinceSignup}d ago` : '—'}
                                </p>
                                <p className="text-[10px] text-amber-500">
                                  {daysSinceActive !== null ? `inactive ${daysSinceActive}d` : 'never active'}
                                </p>
                              </div>
                              <div className="shrink-0 text-right w-14 hidden md:block">
                                <p className="text-[10px] text-slate-400">{u.ai_requests_ever} req</p>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Funnel tab */}
          {tab === 'funnel' && (
            <>
              {!funnelData ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <Loader2 size={14} className="animate-spin" /> Loading funnel data…
                </div>
              ) : (
                <>
                  {/* Free → Paid Conversion */}
                  <div className="glass-card rounded-xl p-5 mb-6">
                    <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-1">
                      Free → Paid Conversion
                    </h2>
                    <p className="text-xs text-slate-400 mb-4">
                      Last 180 days · {funnelData.conversion.total_signups_180d.toLocaleString()} signups
                    </p>
                    <div className="space-y-3 mb-4">
                      {([
                        { label: 'D30', pct: funnelData.conversion.converted_30d_pct, count: funnelData.conversion.converted_30d, desc: 'converted within 30 days' },
                        { label: 'D60', pct: funnelData.conversion.converted_60d_pct, count: funnelData.conversion.converted_60d, desc: 'converted within 60 days' },
                        { label: 'D90', pct: funnelData.conversion.converted_90d_pct, count: funnelData.conversion.converted_90d, desc: 'converted within 90 days' },
                      ] as { label: string; pct: number; count: number; desc: string }[]).map(({ label, pct, count, desc }) => (
                        <div key={label} className="flex items-center gap-3">
                          <span className="text-xs font-mono text-slate-500 w-7 shrink-0">{label}</span>
                          <div className="flex-1 h-3 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-violet-500"
                              style={{ width: `${Math.max(pct > 0 ? 1 : 0, pct)}%` }}
                            />
                          </div>
                          <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 w-12 text-right shrink-0">{pct}%</span>
                          <span className="text-[11px] text-slate-400 hidden sm:block">({count} {desc})</span>
                        </div>
                      ))}
                    </div>
                    {funnelData.conversion.avg_days_to_convert != null && (
                      <p className="text-xs text-slate-500">
                        Avg time to convert: <span className="font-semibold text-slate-700 dark:text-slate-200">{funnelData.conversion.avg_days_to_convert} days</span>
                        <span className="ml-2 text-[10px] text-slate-400">
                          {funnelData.conversion.avg_days_to_convert < 7 ? '— excellent' : funnelData.conversion.avg_days_to_convert > 30 ? '— consider more nudges' : ''}
                        </span>
                      </p>
                    )}
                  </div>

                  {/* Activations vs Cancellations */}
                  <div className="glass-card rounded-xl p-5 mb-6">
                    <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">
                      Activations vs Cancellations (last 6 months)
                    </h2>
                    {funnelData.monthly_churn.length === 0 ? (
                      <p className="text-xs text-slate-400">No subscription data yet.</p>
                    ) : (
                      <>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs mb-4">
                            <thead>
                              <tr className="border-b border-slate-200 dark:border-slate-700">
                                <th className="text-left px-3 py-2 text-slate-500 font-semibold">Month</th>
                                <th className="text-right px-3 py-2 text-slate-500 font-semibold">New subs</th>
                                <th className="text-right px-3 py-2 text-slate-500 font-semibold">Cancellations</th>
                                <th className="text-right px-3 py-2 text-slate-500 font-semibold">Net</th>
                                <th className="px-3 py-2 w-40 hidden sm:table-cell" />
                              </tr>
                            </thead>
                            <tbody>
                              {funnelData.monthly_churn.map(r => {
                                const net = r.new_subscriptions - r.cancellations
                                const maxVal = Math.max(...funnelData.monthly_churn.map(x => x.new_subscriptions), 1)
                                return (
                                  <tr key={r.month} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                                    <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300 font-medium">{fmtMonth(r.month)}</td>
                                    <td className="px-3 py-2.5 text-right tabular-nums text-emerald-600 dark:text-emerald-400 font-medium">{r.new_subscriptions}</td>
                                    <td className="px-3 py-2.5 text-right tabular-nums text-rose-500 dark:text-rose-400">{r.cancellations}</td>
                                    <td className={clsx('px-3 py-2.5 text-right tabular-nums font-semibold', net >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400')}>
                                      {net >= 0 ? `+${net}` : net}
                                    </td>
                                    <td className="px-3 py-2.5 hidden sm:table-cell">
                                      <div className="flex items-center gap-1 h-3">
                                        <div
                                          className="h-full rounded bg-emerald-500"
                                          style={{ width: `${(r.new_subscriptions / maxVal) * 100}%`, minWidth: r.new_subscriptions > 0 ? '2px' : '0' }}
                                        />
                                        <div
                                          className="h-full rounded bg-rose-400"
                                          style={{ width: `${(r.cancellations / maxVal) * 100}%`, minWidth: r.cancellations > 0 ? '2px' : '0' }}
                                        />
                                      </div>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-emerald-500" /><span className="text-[10px] text-slate-500">New</span></div>
                          <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-rose-400" /><span className="text-[10px] text-slate-500">Cancelled</span></div>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Trial exhausted — never upgraded */}
                  <div className="glass-card rounded-xl overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                        Trial Exhausted — Never Upgraded
                        <span className="ml-2 text-xs font-normal text-slate-400">{funnelData.trial_exhausted_never_upgraded.length} shown</span>
                      </h2>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Used 6+ messages but never paid — highest-intent re-engagement audience.
                      </p>
                    </div>
                    {funnelData.trial_exhausted_never_upgraded.length === 0 ? (
                      <p className="text-xs text-slate-400 px-5 py-6 text-center">No trial-exhausted users found.</p>
                    ) : (
                      <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                        {funnelData.trial_exhausted_never_upgraded.map(u => {
                          const signupDate = u.signup_date ? new Date(u.signup_date) : null
                          const daysSinceSignup = signupDate
                            ? Math.floor((Date.now() - signupDate.getTime()) / 86_400_000)
                            : null
                          return (
                            <div key={u.uid} className="px-5 py-3 flex items-center gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                                  {u.display_name ?? u.email ?? u.uid}
                                </p>
                                <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                              </div>
                              <div className="shrink-0 text-right">
                                <p className="text-[10px] text-slate-500">
                                  {daysSinceSignup !== null ? `joined ${daysSinceSignup}d ago` : '—'}
                                </p>
                                <p className="text-[10px] text-slate-400">{u.signup_date ?? '—'}</p>
                              </div>
                              <div className="shrink-0 text-right w-20 hidden sm:block">
                                <p className="text-xs tabular-nums font-medium text-amber-600 dark:text-amber-400">{u.lifetime_messages} msgs</p>
                                <p className="text-[10px] text-slate-400">used</p>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Content tab */}
          {tab === 'content' && (
            <>
              {!contentData ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <Loader2 size={14} className="animate-spin" /> Loading content data…
                </div>
              ) : (
                <>
                  {/* Completion summary */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                    {[
                      { label: 'Journeys started',    value: String(contentData.completion_summary.journeys_started) },
                      { label: 'Users with progress', value: String(contentData.completion_summary.users_with_progress) },
                      { label: 'Avg completion',      value: `${contentData.completion_summary.avg_completion_pct}%` },
                    ].map(({ label, value }) => (
                      <div key={label} className="glass-card rounded-xl p-4">
                        <p className="text-xs text-slate-500 mb-1">{label}</p>
                        <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Top journeys */}
                  <div className="glass-card rounded-xl overflow-hidden mb-6">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Top Journeys by Learners</h2>
                    </div>
                    {contentData.top_journeys.length === 0 ? (
                      <p className="text-xs text-slate-400 px-5 py-6 text-center">No journey activity yet.</p>
                    ) : (
                      <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                        {contentData.top_journeys.map(j => {
                          const pct = Number(j.completion_pct)
                          const barColor = pct >= 40 ? 'bg-violet-500' : pct >= 20 ? 'bg-amber-400' : 'bg-rose-400'
                          const isExpanded = expandedJourneyId === j.id
                          const dropoff = journeyDropoff[j.id]
                          const isLoadingThis = loadingDropoff === j.id
                          const maxCompletions = dropoff ? Math.max(...dropoff.map(s => s.completions), 1) : 1
                          return (
                            <div key={j.id}>
                              <div
                                className="px-5 py-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                                onClick={() => handleExpandJourney(j.id)}
                              >
                                <div className="flex items-center gap-3 mb-2">
                                  {j.icon && <span className="text-base shrink-0">{j.icon}</span>}
                                  <p className="text-xs font-medium text-slate-800 dark:text-slate-200 flex-1 truncate">{j.title}</p>
                                  <span className="text-[10px] text-slate-400 shrink-0 hidden sm:block">{j.difficulty ?? '—'}</span>
                                  <span className="text-[10px] tabular-nums text-slate-500 shrink-0">{j.unique_learners} learners</span>
                                  <span className={clsx('text-[10px] tabular-nums font-semibold shrink-0 w-10 text-right',
                                    pct >= 40 ? 'text-violet-600 dark:text-violet-400' : pct >= 20 ? 'text-amber-500' : 'text-rose-500'
                                  )}>{pct}%</span>
                                  <div className="text-slate-400 shrink-0">
                                    {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                                  </div>
                                </div>
                                <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                                  <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(pct > 0 ? 1 : 0, pct)}%` }} />
                                </div>
                              </div>
                              {isExpanded && (
                                <div className="px-5 pb-4 pt-2 border-t border-slate-100 dark:border-slate-700/40 bg-slate-50/40 dark:bg-slate-800/20">
                                  <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-2">Step drop-off</p>
                                  {isLoadingThis && (
                                    <div className="flex items-center gap-2 text-slate-400 text-xs py-2">
                                      <Loader2 size={12} className="animate-spin" /> Loading…
                                    </div>
                                  )}
                                  {!isLoadingThis && dropoff && dropoff.length === 0 && (
                                    <p className="text-xs text-slate-400">No step data yet.</p>
                                  )}
                                  {!isLoadingThis && dropoff && dropoff.length > 0 && (
                                    <div className="space-y-1.5">
                                      {dropoff.map(s => (
                                        <div key={s.step_id} className="flex items-center gap-2">
                                          <span className="text-[10px] font-mono text-slate-500 w-24 shrink-0 truncate">{s.step_id}</span>
                                          <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700/60 overflow-hidden">
                                            <div className="h-full rounded-full bg-violet-500/70" style={{ width: `${(s.completions / maxCompletions) * 100}%` }} />
                                          </div>
                                          <span className="text-[10px] tabular-nums text-slate-500 w-10 text-right shrink-0">{s.completions}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Most active conversations */}
                  <div className="glass-card rounded-xl overflow-hidden mb-6">
                    <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-700/50">
                      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Most Active Conversations (last 30 days)</h2>
                    </div>
                    {contentData.top_conversations.length === 0 ? (
                      <p className="text-xs text-slate-400 px-5 py-6 text-center">No conversations in the last 30 days.</p>
                    ) : (
                      <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                        {contentData.top_conversations.map(c => (
                          <div key={c.id} className="px-5 py-3 flex items-center gap-3">
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                                {c.title ?? 'Untitled'}
                              </p>
                              <p className="text-[11px] text-slate-500 truncate">{c.email ?? c.uid}</p>
                            </div>
                            <span className="text-xs tabular-nums font-semibold text-violet-600 dark:text-violet-400 shrink-0">
                              {c.message_count} msgs
                            </span>
                            {c.last_message_at && (
                              <span className="text-[10px] text-slate-400 shrink-0 hidden sm:block">
                                {new Date(c.last_message_at).toLocaleDateString('default', { month: 'short', day: 'numeric' })}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Knowledge graph growth */}
                  <div className="glass-card rounded-xl p-5">
                    <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Knowledge Graph Growth (last 14 days)</h2>
                    {contentData.knowledge_growth.length === 0 ? (
                      <p className="text-xs text-slate-400">No knowledge nodes discovered yet.</p>
                    ) : (
                      <>
                        {(() => {
                          const maxConcepts = Math.max(...contentData.knowledge_growth.map(d => d.new_concepts), 1)
                          return (
                            <>
                              <div className="flex items-end gap-1 h-16 mb-2">
                                {contentData.knowledge_growth.map(d => (
                                  <div
                                    key={d.day}
                                    className="flex-1 flex flex-col justify-end min-w-0"
                                    title={`${d.day}: ${d.new_concepts} concepts, ${d.unique_users} users`}
                                  >
                                    <div
                                      className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t"
                                      style={{ height: `${Math.max((d.new_concepts / maxConcepts) * 100, 4)}%` }}
                                    />
                                  </div>
                                ))}
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[9px] text-slate-400">{contentData.knowledge_growth[0]?.day}</span>
                                <span className="text-[9px] text-slate-400">{contentData.knowledge_growth[contentData.knowledge_growth.length - 1]?.day}</span>
                              </div>
                            </>
                          )
                        })()}
                      </>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Coupons tab */}
          {tab === 'coupons' && (
            <>
              {/* Stats cards */}
              {couponStats && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                  {[
                    { label: 'Active coupons',     value: String(couponStats.active_coupons) },
                    { label: 'Total redemptions',  value: String(couponStats.total_redemptions) },
                    { label: 'Unique redeemers',   value: String(couponStats.unique_redeemers) },
                    { label: 'Credit distributed', value: `$${(couponStats.total_credit_applied_cents / 100).toFixed(2)}` },
                  ].map(({ label, value }) => (
                    <div key={label} className="glass-card rounded-xl p-4">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Create form */}
              <div ref={createFormRef} className="glass-card rounded-2xl p-6 mb-6">
                <div className="flex items-center gap-2 mb-5">
                  <Ticket size={14} className="text-violet-500 dark:text-violet-400" />
                  <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Create Coupon</h2>
                </div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Code *</label>
                    <input value={couponForm.code} onChange={e => setCouponForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} placeholder="LAUNCH50" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Description *</label>
                    <input value={couponForm.description} onChange={e => setCouponForm(f => ({ ...f, description: e.target.value }))} placeholder="Launch promo — 50 cents AI credit" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">AI Credit (cents)</label>
                    <input type="number" min="0" step="1" value={couponForm.credit_cents} onChange={e => setCouponForm(f => ({ ...f, credit_cents: e.target.value }))} placeholder="50 = $0.50 extra budget" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Bonus Chat Messages</label>
                    <input type="number" min="0" value={couponForm.bonus_messages} onChange={e => setCouponForm(f => ({ ...f, bonus_messages: e.target.value }))} placeholder="0 = none" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Credit valid for (days)</label>
                    <input type="number" min="1" value={couponForm.duration_days} onChange={e => setCouponForm(f => ({ ...f, duration_days: e.target.value }))} placeholder="Leave blank = permanent" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Max users</label>
                    <input type="number" min="1" value={couponForm.max_redemptions} onChange={e => setCouponForm(f => ({ ...f, max_redemptions: e.target.value }))} placeholder="Leave blank = unlimited" className={inputCls} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Expires at</label>
                    <input type="datetime-local" value={couponForm.expires_at} onChange={e => setCouponForm(f => ({ ...f, expires_at: e.target.value }))} className={inputCls} />
                  </div>
                </div>
                {couponError && <p className="text-xs text-rose-500 mb-2">{couponError}</p>}
                <button onClick={handleCreateCoupon} disabled={creatingCoupon} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
                  {creatingCoupon ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                  Create Coupon
                </button>

                {/* Bulk generate */}
                <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700/50">
                  <button onClick={() => { setShowBulkForm(v => !v); setBulkResult(null) }} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
                    <Plus size={11} />
                    {showBulkForm ? 'Hide bulk generate' : 'Bulk generate unique codes'}
                  </button>
                  {showBulkForm && (
                    <div className="mt-4 space-y-3">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div>
                          <label className="text-xs text-slate-500">Prefix</label>
                          <input value={bulkForm.prefix} onChange={e => setBulkForm(f => ({ ...f, prefix: e.target.value.toUpperCase() }))} placeholder="CONF26" className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Count</label>
                          <input type="number" min="1" max="1000" value={bulkForm.count} onChange={e => setBulkForm(f => ({ ...f, count: e.target.value }))} className={inputCls} />
                        </div>
                        <div className="col-span-2">
                          <label className="text-xs text-slate-500">Description</label>
                          <input value={bulkForm.description} onChange={e => setBulkForm(f => ({ ...f, description: e.target.value }))} placeholder="Conference promo" className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">AI Credit ¢</label>
                          <input type="number" min="0" value={bulkForm.credit_cents} onChange={e => setBulkForm(f => ({ ...f, credit_cents: e.target.value }))} placeholder="50" className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Bonus Messages</label>
                          <input type="number" min="0" value={bulkForm.bonus_messages} onChange={e => setBulkForm(f => ({ ...f, bonus_messages: e.target.value }))} placeholder="0" className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Duration days</label>
                          <input type="number" min="1" value={bulkForm.duration_days} onChange={e => setBulkForm(f => ({ ...f, duration_days: e.target.value }))} placeholder="30" className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Expires at</label>
                          <input type="datetime-local" value={bulkForm.expires_at} onChange={e => setBulkForm(f => ({ ...f, expires_at: e.target.value }))} className={inputCls} />
                        </div>
                      </div>
                      <button onClick={handleBulkGenerate} disabled={bulkGenerating || !bulkForm.prefix || !bulkForm.description} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
                        {bulkGenerating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                        Generate {bulkForm.count} codes
                      </button>
                      {bulkResult && (
                        <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">Generated {bulkResult.length} codes</p>
                            <button onClick={() => navigator.clipboard.writeText(bulkResult.join('\n'))} className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 hover:underline">
                              <Copy size={10} /> Copy all
                            </button>
                          </div>
                          <p className="text-[10px] text-emerald-600 dark:text-emerald-500 font-mono break-all">
                            {bulkResult.slice(0, 20).join(', ')}{bulkResult.length > 20 ? ` … and ${bulkResult.length - 20} more` : ''}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Search + filter bar */}
              <div className="flex flex-wrap gap-2 mb-4">
                <div className="flex items-center gap-2 glass-card rounded-lg px-3 py-1.5 flex-1 min-w-[200px]">
                  <Search size={12} className="text-slate-400 shrink-0" />
                  <input
                    type="text"
                    value={couponSearch}
                    onChange={e => setCouponSearch(e.target.value)}
                    placeholder="Search codes or descriptions…"
                    className="bg-transparent text-xs text-slate-700 dark:text-slate-200 placeholder-slate-400 outline-none w-full"
                  />
                  {couponSearch && (
                    <button onClick={() => setCouponSearch('')} className="text-slate-400 hover:text-slate-600 shrink-0">
                      <X size={11} />
                    </button>
                  )}
                </div>
                <select value={couponStatusFilter} onChange={e => setCouponStatusFilter(e.target.value as typeof couponStatusFilter)} className={`${selectCls} py-1.5`}>
                  <option value="all">All status</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="expired">Expired</option>
                  <option value="depleted">Depleted</option>
                </select>
                <select value={couponSort} onChange={e => setCouponSort(e.target.value as typeof couponSort)} className={`${selectCls} py-1.5`}>
                  <option value="newest">Newest</option>
                  <option value="most_used">Most used</option>
                  <option value="expiring">Expiring soon</option>
                </select>
              </div>

              {/* Coupon list */}
              <div className="glass-card rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Ticket size={14} className="text-violet-500 dark:text-violet-400" />
                  <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    All Coupons ({filteredCoupons.length}{couponSearch || couponStatusFilter !== 'all' ? ` of ${coupons.length}` : ''})
                  </h2>
                </div>
                {filteredCoupons.length === 0 ? (
                  <p className="text-xs text-slate-400 py-4 text-center">
                    {coupons.length === 0 ? 'No coupons yet. Create one above.' : 'No coupons match the current filter.'}
                  </p>
                ) : (
                  <div className="space-y-2">
                    {filteredCoupons.map(c => {
                      const isEditing = editingCode === c.code
                      const isRedemptionsOpen = expandedRedemptionsCode === c.code
                      const fillPct = c.max_redemptions ? Math.min(100, (c.redemption_count / c.max_redemptions) * 100) : 0

                      return (
                        <div key={c.code} className={clsx(
                          'rounded-xl border overflow-hidden',
                          c.is_active
                            ? 'border-slate-200 dark:border-slate-700/50 bg-white dark:bg-slate-800/30'
                            : 'border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/20 opacity-70'
                        )}>
                          {/* Main row */}
                          <div className="flex items-start gap-3 p-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                <code
                                  onClick={() => copyCode(c.code)}
                                  className="cursor-pointer select-none text-xs font-bold text-violet-700 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 px-1.5 py-0.5 rounded hover:bg-violet-100 dark:hover:bg-violet-500/20 transition-colors"
                                  title="Click to copy"
                                >
                                  {copiedCode === c.code ? '✓ Copied' : c.code}
                                </code>
                                {c.credit_cents > 0 && (
                                  <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">+{c.credit_cents}¢ credit</span>
                                )}
                                {c.bonus_messages > 0 && (
                                  <span className="text-[10px] text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded">+{c.bonus_messages} messages</span>
                                )}
                                {c.duration_days && (
                                  <span className="text-[10px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-1.5 py-0.5 rounded">{c.duration_days}d validity</span>
                                )}
                                {!c.is_active && (
                                  <span className="text-[10px] text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded">inactive</span>
                                )}
                              </div>
                              <p className="text-xs text-slate-600 dark:text-slate-400">{c.description}</p>
                              <div className="mt-1 flex items-center gap-2 flex-wrap">
                                {c.max_redemptions ? (
                                  <div className="flex items-center gap-1.5 flex-1 min-w-[120px]">
                                    <div className="flex-1 h-1 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                                      <div
                                        className={clsx('h-full rounded-full', fillPct >= 90 ? 'bg-rose-500' : fillPct >= 60 ? 'bg-amber-400' : 'bg-emerald-500')}
                                        style={{ width: `${fillPct}%` }}
                                      />
                                    </div>
                                    <button onClick={() => handleLoadRedemptions(c.code)} className="text-[10px] tabular-nums text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 transition-colors shrink-0">
                                      {c.redemption_count}/{c.max_redemptions} users
                                    </button>
                                  </div>
                                ) : (
                                  <button onClick={() => handleLoadRedemptions(c.code)} className="text-[10px] text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
                                    {c.redemption_count} users
                                  </button>
                                )}
                                {c.expires_at && (
                                  <span className="text-[10px] text-slate-400">expires {new Date(c.expires_at).toLocaleDateString()}</span>
                                )}
                              </div>
                            </div>

                            {/* Action buttons */}
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => handleCloneCoupon(c)}
                                title="Clone coupon"
                                className="p-1.5 rounded-lg text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors"
                              >
                                <Copy size={13} />
                              </button>
                              <button
                                onClick={() => {
                                  if (isEditing) {
                                    setEditingCode(null)
                                    setConfirmDeleteCode(null)
                                    setDeleteConfirmInput('')
                                  } else {
                                    setEditingCode(c.code)
                                    setEditForm({
                                      description: c.description,
                                      credit_cents: c.credit_cents,
                                      bonus_messages: c.bonus_messages,
                                      max_redemptions: c.max_redemptions,
                                      expires_at: c.expires_at,
                                      duration_days: c.duration_days,
                                      plan_override: c.plan_override,
                                    })
                                  }
                                }}
                                title={isEditing ? 'Close edit' : 'Edit coupon'}
                                className={clsx(
                                  'p-1.5 rounded-lg transition-colors',
                                  isEditing
                                    ? 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10'
                                    : 'text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-500/10'
                                )}
                              >
                                <Pencil size={13} />
                              </button>
                              <button
                                onClick={() => handleToggleCoupon(c.code, !c.is_active)}
                                title={c.is_active ? 'Deactivate' : 'Activate'}
                                className="p-0.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                              >
                                {c.is_active ? <ToggleRight size={18} className="text-violet-500" /> : <ToggleLeft size={18} />}
                              </button>
                            </div>
                          </div>

                          {/* Inline edit form */}
                          {isEditing && (
                            <div className="border-t border-slate-100 dark:border-slate-700/50 px-3 pb-4 pt-3">
                              <div className="grid grid-cols-2 gap-2 mb-3">
                                <div className="col-span-2">
                                  <label className="text-xs text-slate-500">Description</label>
                                  <input value={editForm.description ?? ''} onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} className={inputCls} />
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500">AI Credit ¢</label>
                                  <input type="number" value={editForm.credit_cents ?? ''} onChange={e => setEditForm(f => ({ ...f, credit_cents: parseFloat(e.target.value) || 0 }))} className={inputCls} />
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500">Bonus Messages</label>
                                  <input type="number" value={editForm.bonus_messages ?? ''} onChange={e => setEditForm(f => ({ ...f, bonus_messages: parseInt(e.target.value) || 0 }))} className={inputCls} />
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500">Max users</label>
                                  <input type="number" value={editForm.max_redemptions ?? ''} onChange={e => setEditForm(f => ({ ...f, max_redemptions: parseInt(e.target.value) || null }))} className={inputCls} />
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500">Credit days</label>
                                  <input type="number" value={editForm.duration_days ?? ''} onChange={e => setEditForm(f => ({ ...f, duration_days: parseInt(e.target.value) || null }))} className={inputCls} />
                                </div>
                                <div className="col-span-2">
                                  <label className="text-xs text-slate-500">Expires at</label>
                                  <input type="datetime-local" value={editForm.expires_at?.slice(0, 16) ?? ''} onChange={e => setEditForm(f => ({ ...f, expires_at: e.target.value || null }))} className={inputCls} />
                                </div>
                              </div>
                              <div className="flex items-center justify-end gap-2">
                                <button onClick={() => { setEditingCode(null); setConfirmDeleteCode(null); setDeleteConfirmInput('') }} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 px-3 py-1.5 transition-colors">
                                  Cancel
                                </button>
                                <button onClick={() => handleSaveCoupon(c.code)} disabled={savingEdit} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
                                  {savingEdit ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                                  Save changes
                                </button>
                              </div>

                              {/* Danger zone */}
                              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-700/50">
                                <p className="text-[10px] font-semibold text-rose-500 uppercase tracking-wide mb-1">Danger zone</p>
                                <p className="text-[10px] text-slate-400 mb-2">Deleting removes this coupon. Existing redemptions and credits are NOT revoked.</p>
                                {confirmDeleteCode === c.code ? (
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <input
                                      type="text"
                                      value={deleteConfirmInput}
                                      onChange={e => setDeleteConfirmInput(e.target.value)}
                                      placeholder={`Type ${c.code} to confirm`}
                                      className={inputCls}
                                      onKeyDown={e => { if (e.key === 'Enter' && deleteConfirmInput === c.code) handleDeleteCoupon(c.code) }}
                                    />
                                    <button
                                      onClick={() => handleDeleteCoupon(c.code)}
                                      disabled={deleteConfirmInput !== c.code || deletingCode === c.code}
                                      className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold transition-colors disabled:opacity-40"
                                    >
                                      {deletingCode === c.code ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                                      Delete
                                    </button>
                                    <button onClick={() => { setConfirmDeleteCode(null); setDeleteConfirmInput('') }} className="text-xs text-slate-400 hover:text-slate-600 shrink-0">Cancel</button>
                                  </div>
                                ) : (
                                  <button onClick={() => setConfirmDeleteCode(c.code)} className="flex items-center gap-1.5 text-xs text-rose-500 hover:text-rose-600 transition-colors">
                                    <Trash2 size={11} />
                                    Delete coupon
                                  </button>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Redemptions drawer */}
                          {isRedemptionsOpen && (
                            <div className="border-t border-slate-100 dark:border-slate-700/50 px-3 pb-4 pt-3">
                              <div className="flex items-center justify-between mb-3">
                                <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                                  Redemptions ({redemptions[c.code]?.length ?? '…'})
                                </p>
                                <button onClick={() => setExpandedRedemptionsCode(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
                                  <X size={13} />
                                </button>
                              </div>
                              {loadingRedemptions === c.code ? (
                                <div className="flex items-center gap-2 text-slate-400 text-xs py-2">
                                  <Loader2 size={12} className="animate-spin" /> Loading…
                                </div>
                              ) : !redemptions[c.code] ? (
                                <p className="text-xs text-slate-400">Failed to load redemptions.</p>
                              ) : redemptions[c.code].length === 0 ? (
                                <p className="text-xs text-slate-400">No redemptions yet.</p>
                              ) : (
                                <div className="space-y-1.5">
                                  {redemptions[c.code].map(r => (
                                    <div key={r.id} className="flex items-center gap-3 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-lg px-3 py-2">
                                      <div className="min-w-0 flex-1">
                                        <p className="font-medium text-slate-700 dark:text-slate-300 truncate">{r.display_name ?? r.email ?? r.uid}</p>
                                        <p className="text-[10px] text-slate-400 truncate">{r.email}</p>
                                      </div>
                                      {r.credit_applied_cents > 0 && (
                                        <span className="text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0">+{fmtCents(r.credit_applied_cents)}</span>
                                      )}
                                      {r.bonus_messages_applied > 0 && (
                                        <span className="text-blue-600 dark:text-blue-400 tabular-nums shrink-0">+{r.bonus_messages_applied} msg</span>
                                      )}
                                      <span className="text-[10px] text-slate-400 shrink-0">
                                        {new Date(r.redeemed_at).toLocaleDateString('default', { month: 'short', day: 'numeric' })}
                                      </span>
                                      {r.credit_expires_at && (
                                        <span className="text-[10px] text-slate-400 shrink-0 hidden sm:block">
                                          exp {new Date(r.credit_expires_at).toLocaleDateString('default', { month: 'short', day: 'numeric', year: '2-digit' })}
                                        </span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
