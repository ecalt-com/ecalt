import { useCallback, useEffect, useState } from 'react'
import { School as SchoolIcon, Loader2, Plus, Search, Mail, Save } from 'lucide-react'
import clsx from 'clsx'
import { apiErrorCode, type ApiError } from '../../../lib/api'
import {
  adminCreateSchool, adminInviteOwner, adminListSchools, adminUpdateSchool, schoolErrorMessage,
  type School, type SchoolStatus,
} from '../../../lib/schoolApi'
import { inputCls, selectCls } from '../constants'

interface SchoolsTabProps {
  getToken: () => Promise<string | null>
}

const STATUS_BADGE: Record<SchoolStatus, string> = {
  onboarding: 'text-amber-700 bg-amber-50 dark:text-amber-400 dark:bg-amber-400/10',
  active: 'text-emerald-700 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-400/10',
  suspended: 'text-rose-700 bg-rose-50 dark:text-rose-400 dark:bg-rose-400/10',
  terminated: 'text-slate-500 bg-slate-100 dark:bg-slate-700/50',
}

const EMPTY_FORM = { name: '', country: 'IN', seat_limit: '50', budget: '50', owner_email: '' }

// ECALT admin: school tenants (backend/plans/school-courses SC-111, frontend-changes.md §11).
// Budgets are entered in dollars and stored as cents, like the rest of the cost tracking.
export function SchoolsTab({ getToken }: SchoolsTabProps) {
  const [schools, setSchools] = useState<School[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<SchoolStatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [disabled, setDisabled] = useState(false)
  const [message, setMessage] = useState<{ text: string; tone: 'ok' | 'error' } | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
  const [edits, setEdits] = useState<Record<string, { seat_limit?: string; budget?: string }>>({})
  const [ownerEmails, setOwnerEmails] = useState<Record<string, string>>({})
  const [acting, setActing] = useState<string | null>(null)

  const fail = (err: unknown) => setMessage({
    text: schoolErrorMessage(apiErrorCode(err), (err as Error)?.message || 'Request failed'),
    tone: 'error',
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const token = await getToken()
      if (!token) return
      const data = await adminListSchools({ q: q.trim() || undefined, status: status || undefined, limit: 100 }, token)
      setSchools(data.schools)
      setTotal(data.total)
      setDisabled(false)
    } catch (err) {
      if ((err as ApiError)?.status === 404) setDisabled(true)
      else fail(err)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, status])

  useEffect(() => { load() }, [load])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || creating) return
    setCreating(true)
    setMessage(null)
    try {
      const token = await getToken()
      if (!token) return
      const school = await adminCreateSchool({
        name: form.name.trim(),
        country: form.country.trim().toUpperCase() || 'IN',
        seat_limit: Number(form.seat_limit) || 0,
        monthly_ai_budget_cents: Math.round((Number(form.budget) || 0) * 100),
        ...(form.owner_email.trim() ? { owner_email: form.owner_email.trim() } : {}),
      }, token)
      setMessage({
        text: school.owner_invite
          ? `Created ${school.name} and emailed an owner invite to ${school.owner_invite.email}.`
          : `Created ${school.name}. Invite an owner below.`,
        tone: 'ok',
      })
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      fail(err)
    } finally {
      setCreating(false)
    }
  }

  const update = async (school: School, body: Parameters<typeof adminUpdateSchool>[1]) => {
    setActing(school.id)
    setMessage(null)
    try {
      const token = await getToken()
      if (!token) return
      const updated = await adminUpdateSchool(school.id, body, token)
      setSchools(prev => prev.map(s => s.id === school.id ? { ...s, ...updated } : s))
      setEdits(prev => { const next = { ...prev }; delete next[school.id]; return next })
    } catch (err) {
      fail(err)
    } finally {
      setActing(null)
    }
  }

  const changeStatus = (school: School, next: SchoolStatus) => {
    if (next === school.status) return
    if (next === 'terminated') {
      const typed = window.prompt(
        `Terminating ${school.name} blocks all its staff and students and starts the 30-day deletion grace period. ` +
        'It cannot be undone. Type the school name to confirm.',
      )
      if (typed?.trim() !== school.name) return
    } else if (next === 'suspended' && !window.confirm(`Suspend ${school.name}? Staff and students lose access until it's reactivated.`)) {
      return
    }
    update(school, { status: next })
  }

  const saveLimits = (school: School) => {
    const e = edits[school.id]
    if (!e) return
    update(school, {
      ...(e.seat_limit !== undefined ? { seat_limit: Number(e.seat_limit) || 0 } : {}),
      ...(e.budget !== undefined ? { monthly_ai_budget_cents: Math.round((Number(e.budget) || 0) * 100) } : {}),
    })
  }

  const inviteOwner = async (school: School) => {
    const email = ownerEmails[school.id]?.trim()
    if (!email) return
    setActing(school.id)
    setMessage(null)
    try {
      const token = await getToken()
      if (!token) return
      const invite = await adminInviteOwner(school.id, email, token)
      setOwnerEmails(prev => ({ ...prev, [school.id]: '' }))
      setMessage({ text: `Owner invite emailed to ${invite.email}.`, tone: 'ok' })
    } catch (err) {
      fail(err)
    } finally {
      setActing(null)
    }
  }

  if (disabled) {
    return (
      <div className="glass-card rounded-xl p-6 text-sm text-slate-600 dark:text-slate-300">
        Schools are switched off on this server. Set <code className="text-xs">SCHOOLS_ENABLED=true</code> on the backend
        (migration <code className="text-xs">014_schools.sql</code> is already applied).
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <SchoolIcon size={14} className="text-violet-500" />
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Schools ({total})</h2>
      </div>

      <form onSubmit={create} className="glass-card rounded-xl p-4 grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
        <label className="col-span-2 text-xs text-slate-500">School name
          <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required maxLength={120} placeholder="Delhi Public School" className={inputCls} />
        </label>
        <label className="text-xs text-slate-500">Country
          <input value={form.country} onChange={e => setForm(f => ({ ...f, country: e.target.value }))} maxLength={2} className={inputCls} />
        </label>
        <label className="text-xs text-slate-500">Seats
          <input type="number" min="0" value={form.seat_limit} onChange={e => setForm(f => ({ ...f, seat_limit: e.target.value }))} className={inputCls} />
        </label>
        <label className="text-xs text-slate-500">AI budget / month ($)
          <input type="number" min="0" step="0.01" value={form.budget} onChange={e => setForm(f => ({ ...f, budget: e.target.value }))} className={inputCls} />
        </label>
        <label className="col-span-2 md:col-span-1 text-xs text-slate-500">Owner email
          <input type="email" value={form.owner_email} onChange={e => setForm(f => ({ ...f, owner_email: e.target.value }))} placeholder="optional" className={inputCls} />
        </label>
        <button type="submit" disabled={creating || !form.name.trim()} className="col-span-2 md:col-span-6 justify-self-start flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-50">
          {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />} Create school
        </button>
      </form>

      {message && (
        <p className={clsx('text-xs', message.tone === 'ok' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400')} role="status">
          {message.text}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <form onSubmit={e => { e.preventDefault(); load() }} className="flex items-center gap-2 flex-1 min-w-[200px]">
          <Search size={13} className="text-slate-400" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search name or slug" className={clsx(inputCls, '!mt-0')} />
        </form>
        <select value={status} onChange={e => setStatus(e.target.value as SchoolStatus | '')} className={selectCls} aria-label="Filter by status">
          <option value="">All statuses</option>
          {(['onboarding', 'active', 'suspended', 'terminated'] as SchoolStatus[]).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>
      ) : schools.length === 0 ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">No schools yet.</p>
      ) : (
        <div className="space-y-3">
          {schools.map(school => {
            const edit = edits[school.id] ?? {}
            const closed = school.status === 'terminated'
            return (
              <div key={school.id} className="glass-card rounded-xl p-4 space-y-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{school.name}</span>
                      <span className={clsx('text-[10px] font-semibold px-2 py-0.5 rounded-full', STATUS_BADGE[school.status])}>{school.status}</span>
                      <span className="text-[10px] text-slate-400">{school.country} · {school.slug}</span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {school.staff_count} staff · {school.student_count}/{school.seat_limit} students ·{' '}
                      {school.dpa_accepted ? 'DPA accepted' : 'DPA not accepted'}
                    </p>
                  </div>
                  <select
                    value={school.status}
                    disabled={closed || acting === school.id}
                    onChange={e => changeStatus(school, e.target.value as SchoolStatus)}
                    className={selectCls}
                    aria-label={`Status of ${school.name}`}
                  >
                    {(['onboarding', 'active', 'suspended', 'terminated'] as SchoolStatus[]).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>

                {!closed && (
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
                    <label className="text-xs text-slate-500">Seats
                      <input
                        type="number" min="0"
                        value={edit.seat_limit ?? String(school.seat_limit)}
                        onChange={e => setEdits(p => ({ ...p, [school.id]: { ...p[school.id], seat_limit: e.target.value } }))}
                        className={inputCls}
                      />
                    </label>
                    <label className="text-xs text-slate-500">AI budget / month ($)
                      <input
                        type="number" min="0" step="0.01"
                        value={edit.budget ?? ((school.monthly_ai_budget_cents ?? 0) / 100).toFixed(2)}
                        onChange={e => setEdits(p => ({ ...p, [school.id]: { ...p[school.id], budget: e.target.value } }))}
                        className={inputCls}
                      />
                    </label>
                    <button
                      onClick={() => saveLimits(school)}
                      disabled={!edits[school.id] || acting === school.id}
                      className="flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 disabled:opacity-40"
                    >
                      <Save size={12} /> Save
                    </button>
                    <label className="col-span-2 md:col-span-2 text-xs text-slate-500">Invite an owner
                      <input
                        type="email"
                        value={ownerEmails[school.id] ?? ''}
                        onChange={e => setOwnerEmails(p => ({ ...p, [school.id]: e.target.value }))}
                        placeholder="principal@school.org"
                        className={inputCls}
                      />
                    </label>
                    <button
                      onClick={() => inviteOwner(school)}
                      disabled={!ownerEmails[school.id]?.trim() || acting === school.id}
                      className="flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-40"
                    >
                      {acting === school.id ? <Loader2 size={12} className="animate-spin" /> : <Mail size={12} />} Send
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
