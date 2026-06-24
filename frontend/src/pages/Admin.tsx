import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, ArrowLeft } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import { useImpersonation } from '../lib/ImpersonationContext'
import { useSubscription } from '../lib/SubscriptionContext'
import PageMeta from '../components/PageMeta'
import type {
  PlanRow, NewPlanForm, UserDetail, AIConfig,
  StepDropoff, CouponRow,
} from './admin/types'
import { TABS } from './admin/constants'
import type { TabId } from './admin/constants'
import { useAdminData } from './admin/hooks/useAdminData'
import { useCouponStats } from './admin/hooks/useCouponStats'
import { OverviewTab } from './admin/tabs/OverviewTab'
import { PlansTab } from './admin/tabs/PlansTab'
import { AIProvidersTab } from './admin/tabs/AIProvidersTab'
import { UsersTab } from './admin/tabs/UsersTab'
import { CouponsTab } from './admin/tabs/CouponsTab'
import { RevenueTab } from './admin/tabs/RevenueTab'
import { RetentionTab } from './admin/tabs/RetentionTab'
import { FunnelTab } from './admin/tabs/FunnelTab'
import { ContentTab } from './admin/tabs/ContentTab'
import { PromptsTab } from './admin/tabs/PromptsTab'
import { NotificationTemplatesTab } from './admin/tabs/NotificationTemplatesTab'
import { ImpersonationLogTab } from './admin/tabs/ImpersonationLogTab'


export default function Admin() {
  const navigate = useNavigate()
  const { getToken } = useAuth()
  const { startImpersonation } = useImpersonation()
  const { refresh: refreshSubscription } = useSubscription()

  const {
    plans, stats, users, aiConfigs, availableModels,
    usageByModel, dailyUsage, revenue, costAnalysis,
    retentionData, featureUsage, funnelData, contentData, coupons,
    prompts, notificationTemplates, templateVariables,
    setPlans, setUsers, setAiConfigs, setCoupons,
    setPrompts, setNotificationTemplates,
  } = useAdminData()

  const [expandedJourneyId, setExpandedJourneyId] = useState<string | null>(null)
  const [journeyDropoff, setJourneyDropoff] = useState<Record<string, StepDropoff[]>>({})
  const [loadingDropoff, setLoadingDropoff] = useState<string | null>(null)

  const [saving, setSaving] = useState<string | null>(null)
  const [savingAI, setSavingAI] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, Partial<PlanRow>>>({})
  const [aiEdits, setAiEdits] = useState<Record<string, AIConfig>>({})
  const [togglingUid, setTogglingUid] = useState<string | null>(null)
  const [impersonatingUid, setImpersonatingUid] = useState<string | null>(null)
  const [tab, setTab] = useState<TabId>('overview')
  const [userSearch, setUserSearch] = useState('')

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
  const [redemptions, setRedemptions] = useState<Record<string, any[]>>({})
  const [loadingRedemptions, setLoadingRedemptions] = useState<string | null>(null)
  const [expandedRedemptionsCode, setExpandedRedemptionsCode] = useState<string | null>(null)
  const [couponSearch, setCouponSearch] = useState('')
  const [couponStatusFilter, setCouponStatusFilter] = useState<'all' | 'active' | 'inactive' | 'expired' | 'depleted'>('all')
  const [couponSort, setCouponSort] = useState<'newest' | 'most_used' | 'expiring'>('newest')
  const { couponStats } = useCouponStats(tab)
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

  const handleImpersonate = async (uid: string, displayName: string) => {
    setImpersonatingUid(uid)
    try {
      await startImpersonation(uid, displayName)
      refreshSubscription()
      navigate('/learn')
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start impersonation session')
    } finally {
      setImpersonatingUid(null)
    }
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
    } finally { setLoadingDetail(null) }
  }

  const setEdit = (planId: string, field: string, value: string | number | boolean | null) => {
    setEdits(prev => ({ ...prev, [planId]: { ...prev[planId], [field]: value } }))
  }

  const setAiEdit = (interactionType: string, field: 'provider' | 'model', value: string) => {
    setAiEdits(prev => {
      const base = prev[interactionType] ?? aiConfigs.find(c => c.interaction_type === interactionType) ?? { interaction_type: interactionType, provider: 'anthropic', model: '' }
      const updated = { ...base, [field]: value }
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
    } finally { setCreatingCoupon(false) }
  }

  const handleToggleCoupon = async (code: string, active: boolean) => {
    const token = await getToken()
    const res = await fetch(`/api/v1/coupons/admin/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ is_active: active }),
    })
    if (res.ok) setCoupons(prev => prev.map(c => c.code === code ? { ...c, is_active: active } : c))
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
    } finally { setLoadingDropoff(null) }
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
    } finally { setCreatingPlan(false) }
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

          <div className="flex gap-1 mb-8 p-1 glass-card rounded-xl overflow-x-auto flex-nowrap">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={clsx(
                  'px-4 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0',
                  tab === t.id
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <OverviewTab stats={stats} plans={plans} featureUsage={featureUsage} />
          )}

          {tab === 'plans' && (
            <PlansTab
              plans={plans}
              edits={edits}
              saving={saving}
              provisioning={provisioning}
              newPlanForm={newPlanForm}
              creatingPlan={creatingPlan}
              onSetEdit={setEdit}
              onSavePlan={handleSavePlan}
              onProvision={handleProvision}
              onSetNewPlanForm={setNewPlanForm}
              onCreatePlan={handleCreatePlan}
            />
          )}

          {tab === 'ai' && (
            <AIProvidersTab
              costAnalysis={costAnalysis}
              usageByModel={usageByModel}
              dailyUsage={dailyUsage}
              aiConfigs={aiConfigs}
              availableModels={availableModels}
              aiEdits={aiEdits}
              savingAI={savingAI}
              totalMonthlyCost={totalMonthlyCost}
              expandedUid={expandedUid}
              userDetails={userDetails}
              loadingDetail={loadingDetail}
              onExpandUser={handleExpandUser}
              onSaveAI={handleSaveAI}
              onSetAiEdit={setAiEdit}
            />
          )}

          {tab === 'prompts' && (
            <PromptsTab
              prompts={prompts}
              setPrompts={setPrompts}
              getToken={getToken}
            />
          )}

          {tab === 'notification-templates' && (
            <NotificationTemplatesTab
              templates={notificationTemplates}
              setTemplates={setNotificationTemplates}
              templateVariables={templateVariables}
              getToken={getToken}
            />
          )}

          {tab === 'users' && (
            <UsersTab
              users={users}
              filteredUsers={filteredUsers}
              userSearch={userSearch}
              togglingUid={togglingUid}
              impersonatingUid={impersonatingUid}
              expandedUid={expandedUid}
              userDetails={userDetails}
              loadingDetail={loadingDetail}
              onSetUserSearch={setUserSearch}
              onExpandUser={handleExpandUser}
              onToggleAdmin={handleToggleAdmin}
              onImpersonate={handleImpersonate}
            />
          )}

          {tab === 'coupons' && (
            <CouponsTab
              coupons={coupons}
              filteredCoupons={filteredCoupons}
              couponStats={couponStats}
              couponForm={couponForm}
              couponSearch={couponSearch}
              couponStatusFilter={couponStatusFilter}
              couponSort={couponSort}
              editingCode={editingCode}
              editForm={editForm}
              savingEdit={savingEdit}
              confirmDeleteCode={confirmDeleteCode}
              deletingCode={deletingCode}
              deleteConfirmInput={deleteConfirmInput}
              copiedCode={copiedCode}
              redemptions={redemptions}
              loadingRedemptions={loadingRedemptions}
              expandedRedemptionsCode={expandedRedemptionsCode}
              showBulkForm={showBulkForm}
              bulkForm={bulkForm}
              bulkResult={bulkResult}
              bulkGenerating={bulkGenerating}
              creatingCoupon={creatingCoupon}
              couponError={couponError}
              onSetCouponForm={setCouponForm}
              onSetCouponSearch={setCouponSearch}
              onSetCouponStatusFilter={setCouponStatusFilter}
              onSetCouponSort={setCouponSort}
              onCreateCoupon={handleCreateCoupon}
              onToggleCoupon={handleToggleCoupon}
              onSaveCoupon={handleSaveCoupon}
              onDeleteCoupon={handleDeleteCoupon}
              onLoadRedemptions={handleLoadRedemptions}
              onBulkGenerate={handleBulkGenerate}
              onSetEditingCode={setEditingCode}
              onSetEditForm={setEditForm}
              onSetConfirmDeleteCode={setConfirmDeleteCode}
              onSetDeleteConfirmInput={setDeleteConfirmInput}
              onSetShowBulkForm={setShowBulkForm}
              onSetBulkForm={setBulkForm}
              onSetBulkResult={setBulkResult}
              copyCode={copyCode}
              onSetExpandedRedemptionsCode={setExpandedRedemptionsCode}
              onCloneCoupon={handleCloneCoupon}
            />
          )}

          {tab === 'revenue' && <RevenueTab revenue={revenue} />}

          {tab === 'retention' && <RetentionTab retentionData={retentionData} />}

          {tab === 'funnel' && <FunnelTab funnelData={funnelData} />}

          {tab === 'content' && (
            <ContentTab
              contentData={contentData}
              expandedJourneyId={expandedJourneyId}
              journeyDropoff={journeyDropoff}
              loadingDropoff={loadingDropoff}
              onExpandJourney={handleExpandJourney}
            />
          )}

          {tab === 'impersonation-log' && (
            <ImpersonationLogTab getToken={getToken} />
          )}
        </div>
      </div>
    </>
  )
}
