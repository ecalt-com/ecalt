import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, ArrowLeft, Save, Loader2, ShieldCheck, ShieldOff, Check, Zap, Users, GraduationCap, Building2, Search, Cpu, Ticket, Plus, ToggleLeft, ToggleRight, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import PageMeta from '../components/PageMeta'

interface PlanRow {
  plan_id: string
  name: string
  base_price_cents: number
  base_price_inr_paise: number | null
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
  stripe_price_id: string | null
  razorpay_plan_id: string | null
}

interface NewPlanForm {
  plan_id: string
  name: string
  base_price_cents: string
  base_price_inr_paise: string
  token_budget_cents: string
  max_seats: string
}

interface Stats {
  total_users: number
  dau: number
  messages_today: number
  monthly_api_cost_cents: number
}

interface UserRow {
  uid: string
  email: string | null
  display_name: string | null
  is_admin: boolean
  plan_id: string
  created_at: string
}

interface AIConfig {
  interaction_type: string
  provider: string
  model: string
}

interface ModelOption {
  id: string
  label: string
}

interface UsageByModel {
  model_used: string
  message_count: number
  total_cost_cents: number
}

interface DailyUsage {
  day: string
  messages: number
}

const PLAN_ICONS: Record<string, React.ElementType> = {
  free_trial: Zap, individual: Zap, student: GraduationCap,
  family: Users, university: Building2, enterprise: Building2,
}

const PLAN_FEATURES: Record<string, string[]> = {
  free_trial: ['6 lifetime messages', 'Knowledge Universe preview', "Today's spark"],
  individual: ['Unlimited conversations', 'Knowledge Universe', 'Daily personalized spark', 'Image analysis', 'Mind Signature'],
  student: ['Same as Individual', 'Verified .edu discount', 'Study-focused sparks'],
  family: ['Up to 5 learners', 'Shared budget', 'Individual Knowledge Universes', 'Parent dashboard'],
  university: ['100+ seats', 'Admin dashboard', 'Usage analytics', 'LMS integration (roadmap)'],
  enterprise: ['Custom seat count', 'Custom model routing', 'SLA & priority support', 'Custom integrations'],
}

const INTERACTION_LABELS: Record<string, string> = {
  daily_chat: 'Daily Chat',
  nudge: 'Nudge',
  onboarding: 'Onboarding',
  fingerprint: 'Fingerprint',
  mind_signature: 'Mind Signature',
}

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

  const [saving, setSaving] = useState<string | null>(null)
  const [savingAI, setSavingAI] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, Partial<PlanRow>>>({})
  const [aiEdits, setAiEdits] = useState<Record<string, AIConfig>>({})
  const [togglingUid, setTogglingUid] = useState<string | null>(null)
  const [tab, setTab] = useState<'overview' | 'plans' | 'ai' | 'users' | 'coupons'>('overview')
  const [userSearch, setUserSearch] = useState('')

  // Coupon state
  interface CouponRow {
    code: string; description: string; credit_cents: number; bonus_messages: number;
    plan_override: string | null; duration_days: number | null; max_redemptions: number | null;
    redemption_count: number; expires_at: string | null; is_active: boolean; created_at: string;
  }
  const [coupons, setCoupons] = useState<CouponRow[]>([])
  const [couponForm, setCouponForm] = useState({ code: '', description: '', credit_cents: '', bonus_messages: '', duration_days: '', max_redemptions: '', expires_at: '' })
  const [creatingCoupon, setCreatingCoupon] = useState(false)
  const [couponError, setCouponError] = useState<string | null>(null)
  const [provisioning, setProvisioning] = useState<Record<string, string | null>>({})
  const [newPlanForm, setNewPlanForm] = useState<NewPlanForm>({
    plan_id: '', name: '', base_price_cents: '', base_price_inr_paise: '',
    token_budget_cents: '', max_seats: '1',
  })
  const [creatingPlan, setCreatingPlan] = useState(false)

  const filteredUsers = useMemo(() => {
    const q = userSearch.toLowerCase().trim()
    if (!q) return users
    return users.filter(u =>
      u.display_name?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.uid.toLowerCase().includes(q)
    )
  }, [users, userSearch])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    async function load() {
      const token = await getToken()
      if (!token) return

      const [pRes, sRes, uRes, aiRes, usageRes, cRes] = await Promise.all([
        fetch('/api/v1/admin/plans',     { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/stats',     { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/users',     { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/ai-config', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/usage',     { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/coupons/admin',   { headers: { Authorization: `Bearer ${token}` } }),
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
    }
    load().catch(() => navigate('/'))
    return () => { cancelled = true }
  }, [getToken, navigate, user])

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

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'plans',    label: 'Pricing Plans' },
    { id: 'ai',       label: 'AI Providers' },
    { id: 'users',    label: 'Users' },
    { id: 'coupons',  label: 'Coupons' },
  ] as const

  const inputCls = 'mt-1 w-full bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-200 dark:border-slate-700 focus:border-violet-400 dark:focus:border-violet-500/50'
  const selectCls = 'bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-200 dark:border-slate-700 focus:border-violet-400 dark:focus:border-violet-500/50'

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
                {filteredUsers.map(u => (
                  <div key={u.uid} className="glass-card rounded-xl px-4 py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                        {u.display_name ?? 'Unknown'}
                        {u.is_admin && (
                          <span className="ml-2 text-[10px] text-violet-600 dark:text-violet-300 bg-violet-100 dark:bg-violet-500/20 px-1.5 py-0.5 rounded-full">admin</span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-500 truncate">{u.email ?? u.uid}</p>
                    </div>
                    <span className="text-[10px] text-slate-400 shrink-0 font-mono">{u.plan_id}</span>
                    <button
                      onClick={() => handleToggleAdmin(u.uid)}
                      disabled={togglingUid === u.uid}
                      title={u.is_admin ? 'Revoke admin' : 'Grant admin'}
                      className={clsx(
                        'shrink-0 flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg transition-all',
                        u.is_admin
                          ? 'text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20'
                          : 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 hover:bg-violet-100 dark:hover:bg-violet-500/20'
                      )}
                    >
                      {togglingUid === u.uid
                        ? <Loader2 size={11} className="animate-spin" />
                        : u.is_admin ? <ShieldOff size={11} /> : <ShieldCheck size={11} />
                      }
                      {u.is_admin ? 'Revoke' : 'Grant'}
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Coupons tab */}
          {tab === 'coupons' && (
            <>
              <div className="glass-card rounded-2xl p-6 mb-6">
                <div className="flex items-center gap-2 mb-5">
                  <Ticket size={14} className="text-violet-500 dark:text-violet-400" />
                  <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Create Coupon</h2>
                </div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Code *</label>
                    <input
                      value={couponForm.code}
                      onChange={e => setCouponForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                      placeholder="LAUNCH50"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Description *</label>
                    <input
                      value={couponForm.description}
                      onChange={e => setCouponForm(f => ({ ...f, description: e.target.value }))}
                      placeholder="Launch promo — 50 cents AI credit"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">AI Credit (cents)</label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={couponForm.credit_cents}
                      onChange={e => setCouponForm(f => ({ ...f, credit_cents: e.target.value }))}
                      placeholder="50 = $0.50 extra budget"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Bonus Chat Messages</label>
                    <input
                      type="number"
                      min="0"
                      value={couponForm.bonus_messages}
                      onChange={e => setCouponForm(f => ({ ...f, bonus_messages: e.target.value }))}
                      placeholder="0 = none"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Credit valid for (days)</label>
                    <input
                      type="number"
                      min="1"
                      value={couponForm.duration_days}
                      onChange={e => setCouponForm(f => ({ ...f, duration_days: e.target.value }))}
                      placeholder="Leave blank = permanent"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Max redemptions</label>
                    <input
                      type="number"
                      min="1"
                      value={couponForm.max_redemptions}
                      onChange={e => setCouponForm(f => ({ ...f, max_redemptions: e.target.value }))}
                      placeholder="Leave blank = unlimited"
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400">Expires at</label>
                    <input
                      type="datetime-local"
                      value={couponForm.expires_at}
                      onChange={e => setCouponForm(f => ({ ...f, expires_at: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                </div>
                {couponError && <p className="text-xs text-rose-500 mb-2">{couponError}</p>}
                <button
                  onClick={handleCreateCoupon}
                  disabled={creatingCoupon}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  {creatingCoupon ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                  Create Coupon
                </button>
              </div>

              <div className="glass-card rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Ticket size={14} className="text-violet-500 dark:text-violet-400" />
                  <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    All Coupons ({coupons.length})
                  </h2>
                </div>
                {coupons.length === 0 ? (
                  <p className="text-xs text-slate-400 py-4 text-center">No coupons yet. Create one above.</p>
                ) : (
                  <div className="space-y-2">
                    {coupons.map(c => (
                      <div key={c.code} className={clsx(
                        'flex items-start gap-3 p-3 rounded-xl border',
                        c.is_active
                          ? 'border-slate-200 dark:border-slate-700/50 bg-white dark:bg-slate-800/30'
                          : 'border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/20 opacity-60'
                      )}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <code className="text-xs font-bold text-violet-700 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 px-1.5 py-0.5 rounded">{c.code}</code>
                            {c.credit_cents > 0 && (
                              <span className="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">+{c.credit_cents}¢ credit</span>
                            )}
                            {c.bonus_messages > 0 && (
                              <span className="text-[10px] text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded">+{c.bonus_messages} messages</span>
                            )}
                            {c.duration_days && (
                              <span className="text-[10px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-1.5 py-0.5 rounded">{c.duration_days}d validity</span>
                            )}
                          </div>
                          <p className="text-xs text-slate-600 dark:text-slate-400">{c.description}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5">
                            {c.redemption_count}{c.max_redemptions ? `/${c.max_redemptions}` : ''} uses
                            {c.expires_at ? ` · expires ${new Date(c.expires_at).toLocaleDateString()}` : ''}
                          </p>
                        </div>
                        <button
                          onClick={() => handleToggleCoupon(c.code, !c.is_active)}
                          className="shrink-0 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                          title={c.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {c.is_active ? <ToggleRight size={18} className="text-violet-500" /> : <ToggleLeft size={18} />}
                        </button>
                      </div>
                    ))}
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
