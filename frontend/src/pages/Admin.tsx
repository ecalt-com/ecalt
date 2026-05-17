import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, ArrowLeft, Save, Loader2, ShieldCheck, ShieldOff, Check, Zap, Users, GraduationCap, Building2, Search } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import PageMeta from '../components/PageMeta'

interface PlanRow {
  plan_id: string
  name: string
  base_price_cents: number
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
  stripe_price_id: string | null
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

const PLAN_ICONS: Record<string, React.ElementType> = {
  free_trial: Zap,
  individual: Zap,
  student: GraduationCap,
  family: Users,
  university: Building2,
  enterprise: Building2,
}

const PLAN_FEATURES: Record<string, string[]> = {
  free_trial: ['6 lifetime messages', 'Knowledge Universe preview', "Today's spark"],
  individual: ['Unlimited conversations', 'Knowledge Universe', 'Daily personalized spark', 'Image analysis', 'Mind Signature'],
  student: ['Same as Individual', 'Verified .edu discount', 'Study-focused sparks'],
  family: ['Up to 5 learners', 'Shared budget', 'Individual Knowledge Universes', 'Parent dashboard'],
  university: ['100+ seats', 'Admin dashboard', 'Usage analytics', 'LMS integration (roadmap)'],
  enterprise: ['Custom seat count', 'Custom model routing', 'SLA & priority support', 'Custom integrations'],
}

export default function Admin() {
  const navigate = useNavigate()
  const { getToken, user } = useAuth()
  const [plans, setPlans] = useState<PlanRow[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [users, setUsers] = useState<UserRow[]>([])
  const [saving, setSaving] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, Partial<PlanRow>>>({})
  const [togglingUid, setTogglingUid] = useState<string | null>(null)
  const [tab, setTab] = useState<'overview' | 'plans' | 'users'>('overview')
  const [userSearch, setUserSearch] = useState('')

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

      const [pRes, sRes, uRes] = await Promise.all([
        fetch('/api/v1/admin/plans', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/stats', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/admin/users', { headers: { Authorization: `Bearer ${token}` } }),
      ])

      if (pRes.status === 403) { navigate('/'); return }
      if (!cancelled && pRes.ok) setPlans(await pRes.json().then(d => d.plans ?? []))
      if (!cancelled && sRes.ok) setStats(await sRes.json())
      if (!cancelled && uRes.ok) setUsers(await uRes.json().then(d => d.users ?? []))
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
    } finally {
      setSaving(null)
    }
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
    } finally {
      setTogglingUid(null)
    }
  }

  const setEdit = (planId: string, field: string, value: string | number | boolean) => {
    setEdits(prev => ({ ...prev, [planId]: { ...prev[planId], [field]: value } }))
  }

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'plans', label: 'Pricing Plans' },
    { id: 'users', label: 'Users' },
  ] as const

  return (
    <>
      <PageMeta title="Admin" />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-10">
        <div className="max-w-5xl mx-auto">
          <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 mb-8 transition-colors">
            <ArrowLeft size={12} /> Back
          </button>

          <div className="flex items-center gap-3 mb-6">
            <Settings size={18} className="text-violet-400" />
            <h1 className="text-xl font-bold text-slate-100">Admin Panel</h1>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-8 p-1 glass-card rounded-xl w-fit">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={clsx(
                  'px-4 py-1.5 rounded-lg text-xs font-semibold transition-all',
                  tab === t.id
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-400 hover:text-slate-300'
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
                    { label: 'Total users', value: stats.total_users },
                    { label: 'DAU', value: stats.dau },
                    { label: 'Messages today', value: stats.messages_today },
                    { label: 'Monthly API cost', value: `$${(stats.monthly_api_cost_cents / 100).toFixed(2)}` },
                  ].map(({ label, value }) => (
                    <div key={label} className="glass-card rounded-xl p-4">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className="text-xl font-bold text-slate-100">{value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-slate-500 text-sm mb-8">
                  <Loader2 size={14} className="animate-spin" /> Loading stats…
                </div>
              )}

              {/* Quick plan summary */}
              <h2 className="text-sm font-semibold text-slate-300 mb-3">Active Plans</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {plans.filter(p => p.is_active).map(p => (
                  <div key={p.plan_id} className="glass-card rounded-xl p-3 flex items-center justify-between">
                    <span className="text-xs text-slate-300 font-medium">{p.name}</span>
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
              {/* Live pricing preview */}
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Pricing Preview</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
                {plans.map(plan => {
                  const Icon = PLAN_ICONS[plan.plan_id] ?? Zap
                  const features = PLAN_FEATURES[plan.plan_id] ?? []
                  return (
                    <div key={plan.plan_id} className="glass-card rounded-2xl p-4 flex flex-col opacity-90">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-xl bg-violet-500/15 flex items-center justify-center">
                          <Icon size={14} className="text-violet-400" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-200">{plan.name}</p>
                          {plan.max_seats > 1 && <p className="text-[10px] text-slate-500">Up to {plan.max_seats} users</p>}
                        </div>
                      </div>
                      <div className="mb-3">
                        {plan.base_price_cents === 0
                          ? <span className="text-lg font-bold text-slate-100">Free</span>
                          : <><span className="text-lg font-bold text-slate-100">${(plan.base_price_cents / 100).toFixed(0)}</span><span className="text-[10px] text-slate-500">/mo</span></>
                        }
                      </div>
                      <ul className="space-y-1.5 flex-1">
                        {features.map(f => (
                          <li key={f} className="flex items-start gap-1.5 text-[11px] text-slate-400">
                            <Check size={10} className="text-violet-400 mt-0.5 shrink-0" />{f}
                          </li>
                        ))}
                      </ul>
                      {!plan.is_active && (
                        <span className="mt-2 text-[10px] text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded self-start">inactive</span>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Editable plan config */}
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Edit Plan Configuration</h2>
              <div className="space-y-3">
                {plans.map(plan => {
                  const edit = edits[plan.plan_id] ?? {}
                  const isDirty = Object.keys(edit).length > 0

                  return (
                    <div key={plan.plan_id} className="glass-card rounded-xl p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-200">{plan.name}</span>
                          <span className="text-[10px] text-slate-500 font-mono">{plan.plan_id}</span>
                          {!plan.is_active && (
                            <span className="text-[10px] text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded">inactive</span>
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

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <label className="text-xs text-slate-500">
                          Price (cents)
                          <input
                            type="number"
                            defaultValue={plan.base_price_cents}
                            onChange={e => setEdit(plan.plan_id, 'base_price_cents', parseInt(e.target.value))}
                            className="mt-1 w-full bg-slate-800 text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-700 focus:border-violet-500/50"
                          />
                        </label>
                        <label className="text-xs text-slate-500">
                          Token budget (cents)
                          <input
                            type="number"
                            defaultValue={plan.token_budget_cents}
                            onChange={e => setEdit(plan.plan_id, 'token_budget_cents', parseInt(e.target.value))}
                            className="mt-1 w-full bg-slate-800 text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-700 focus:border-violet-500/50"
                          />
                        </label>
                        <label className="text-xs text-slate-500">
                          Stripe price ID
                          <input
                            type="text"
                            defaultValue={plan.stripe_price_id ?? ''}
                            placeholder="price_..."
                            onChange={e => setEdit(plan.plan_id, 'stripe_price_id', e.target.value)}
                            className="mt-1 w-full bg-slate-800 text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-700 focus:border-violet-500/50"
                          />
                        </label>
                        <label className="text-xs text-slate-500">
                          Max seats
                          <input
                            type="number"
                            defaultValue={plan.max_seats}
                            onChange={e => setEdit(plan.plan_id, 'max_seats', parseInt(e.target.value))}
                            className="mt-1 w-full bg-slate-800 text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-700 focus:border-violet-500/50"
                          />
                        </label>
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
                <h2 className="text-sm font-semibold text-slate-300 shrink-0">
                  Users ({filteredUsers.length}{userSearch ? ` of ${users.length}` : ''})
                </h2>
                <div className="flex items-center gap-2 glass-card rounded-lg px-3 py-1.5 max-w-xs w-full">
                  <Search size={12} className="text-slate-500 shrink-0" />
                  <input
                    type="text"
                    value={userSearch}
                    onChange={e => setUserSearch(e.target.value)}
                    placeholder="Search by name, email or UID…"
                    className="bg-transparent text-xs text-slate-200 placeholder-slate-500 outline-none w-full"
                  />
                </div>
              </div>
              <div className="space-y-2">
                {filteredUsers.length === 0 && (
                  <p className="text-xs text-slate-500 py-4 text-center">No users match "{userSearch}"</p>
                )}
                {filteredUsers.map(u => (
                  <div key={u.uid} className="glass-card rounded-xl px-4 py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-200 truncate">
                        {u.display_name ?? 'Unknown'}
                        {u.is_admin && (
                          <span className="ml-2 text-[10px] text-violet-300 bg-violet-500/20 px-1.5 py-0.5 rounded-full">admin</span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-500 truncate">{u.email ?? u.uid}</p>
                    </div>
                    <span className="text-[10px] text-slate-500 shrink-0 font-mono">{u.plan_id}</span>
                    <button
                      onClick={() => handleToggleAdmin(u.uid)}
                      disabled={togglingUid === u.uid}
                      title={u.is_admin ? 'Revoke admin' : 'Grant admin'}
                      className={clsx(
                        'shrink-0 flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg transition-all',
                        u.is_admin
                          ? 'text-rose-400 bg-rose-500/10 hover:bg-rose-500/20'
                          : 'text-violet-400 bg-violet-500/10 hover:bg-violet-500/20'
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
        </div>
      </div>
    </>
  )
}
