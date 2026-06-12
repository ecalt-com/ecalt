import { useRef } from 'react'
import { Ticket, Plus, Search, X, Loader2, ToggleLeft, ToggleRight, Copy, Trash2, Pencil, Check } from 'lucide-react'
import clsx from 'clsx'
import type { CouponRow, RedemptionRow, CouponStats } from '../types'
import { inputCls, selectCls } from '../constants'
import { fmtCents } from '../utils'
import { StatCard } from '../components/StatCard'

type CouponForm = {
  code: string
  description: string
  credit_cents: string
  bonus_messages: string
  duration_days: string
  max_redemptions: string
  expires_at: string
}

type BulkForm = {
  prefix: string
  count: string
  description: string
  credit_cents: string
  bonus_messages: string
  duration_days: string
  expires_at: string
}

interface CouponsTabProps {
  coupons: CouponRow[]
  filteredCoupons: CouponRow[]
  couponStats: CouponStats | null
  couponForm: CouponForm
  couponSearch: string
  couponStatusFilter: 'all' | 'active' | 'inactive' | 'expired' | 'depleted'
  couponSort: 'newest' | 'most_used' | 'expiring'
  editingCode: string | null
  editForm: Partial<CouponRow>
  savingEdit: boolean
  confirmDeleteCode: string | null
  deletingCode: string | null
  deleteConfirmInput: string
  copiedCode: string | null
  redemptions: Record<string, RedemptionRow[]>
  loadingRedemptions: string | null
  expandedRedemptionsCode: string | null
  showBulkForm: boolean
  bulkForm: BulkForm
  bulkResult: string[] | null
  bulkGenerating: boolean
  creatingCoupon: boolean
  couponError: string | null
  onSetCouponForm: React.Dispatch<React.SetStateAction<CouponForm>>
  onSetCouponSearch: (v: string) => void
  onSetCouponStatusFilter: (v: 'all' | 'active' | 'inactive' | 'expired' | 'depleted') => void
  onSetCouponSort: (v: 'newest' | 'most_used' | 'expiring') => void
  onCreateCoupon: () => void
  onToggleCoupon: (code: string, active: boolean) => void
  onSaveCoupon: (code: string) => void
  onDeleteCoupon: (code: string) => void
  onLoadRedemptions: (code: string) => void
  onBulkGenerate: () => void
  onSetEditingCode: (code: string | null) => void
  onSetEditForm: React.Dispatch<React.SetStateAction<Partial<CouponRow>>>
  onSetConfirmDeleteCode: (code: string | null) => void
  onSetDeleteConfirmInput: (v: string) => void
  onSetShowBulkForm: React.Dispatch<React.SetStateAction<boolean>>
  onSetBulkForm: React.Dispatch<React.SetStateAction<BulkForm>>
  onSetBulkResult: React.Dispatch<React.SetStateAction<string[] | null>>
  copyCode: (code: string) => void
  onSetExpandedRedemptionsCode: (code: string | null) => void
  onCloneCoupon: (c: CouponRow) => void
}

export function CouponsTab({
  coupons,
  filteredCoupons,
  couponStats,
  couponForm,
  couponSearch,
  couponStatusFilter,
  couponSort,
  editingCode,
  editForm,
  savingEdit,
  confirmDeleteCode,
  deletingCode,
  deleteConfirmInput,
  copiedCode,
  redemptions,
  loadingRedemptions,
  expandedRedemptionsCode,
  showBulkForm,
  bulkForm,
  bulkResult,
  bulkGenerating,
  creatingCoupon,
  couponError,
  onSetCouponForm,
  onSetCouponSearch,
  onSetCouponStatusFilter,
  onSetCouponSort,
  onCreateCoupon,
  onToggleCoupon,
  onSaveCoupon,
  onDeleteCoupon,
  onLoadRedemptions,
  onBulkGenerate,
  onSetEditingCode,
  onSetEditForm,
  onSetConfirmDeleteCode,
  onSetDeleteConfirmInput,
  onSetShowBulkForm,
  onSetBulkForm,
  onSetBulkResult,
  copyCode,
  onSetExpandedRedemptionsCode,
  onCloneCoupon,
}: CouponsTabProps) {
  const createFormRef = useRef<HTMLDivElement>(null)

  const handleCloneCoupon = (c: CouponRow) => {
    onCloneCoupon(c)
    createFormRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <>
      {couponStats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatCard label="Active coupons"     value={String(couponStats.active_coupons)} />
          <StatCard label="Total redemptions"  value={String(couponStats.total_redemptions)} />
          <StatCard label="Unique redeemers"   value={String(couponStats.unique_redeemers)} />
          <StatCard label="Credit distributed" value={`$${(couponStats.total_credit_applied_cents / 100).toFixed(2)}`} />
        </div>
      )}

      <div ref={createFormRef} className="glass-card rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Ticket size={14} className="text-violet-500 dark:text-violet-400" />
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Create Coupon</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Code *</label>
            <input value={couponForm.code} onChange={e => onSetCouponForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} placeholder="LAUNCH50" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Description *</label>
            <input value={couponForm.description} onChange={e => onSetCouponForm(f => ({ ...f, description: e.target.value }))} placeholder="Launch promo — 50 cents AI credit" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">AI Credit (cents)</label>
            <input type="number" min="0" step="1" value={couponForm.credit_cents} onChange={e => onSetCouponForm(f => ({ ...f, credit_cents: e.target.value }))} placeholder="50 = $0.50 extra budget" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Bonus Chat Messages</label>
            <input type="number" min="0" value={couponForm.bonus_messages} onChange={e => onSetCouponForm(f => ({ ...f, bonus_messages: e.target.value }))} placeholder="0 = none" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Credit valid for (days)</label>
            <input type="number" min="1" value={couponForm.duration_days} onChange={e => onSetCouponForm(f => ({ ...f, duration_days: e.target.value }))} placeholder="Leave blank = permanent" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Max users</label>
            <input type="number" min="1" value={couponForm.max_redemptions} onChange={e => onSetCouponForm(f => ({ ...f, max_redemptions: e.target.value }))} placeholder="Leave blank = unlimited" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500 dark:text-slate-400">Expires at</label>
            <input type="datetime-local" value={couponForm.expires_at} onChange={e => onSetCouponForm(f => ({ ...f, expires_at: e.target.value }))} className={inputCls} />
          </div>
        </div>
        {couponError && <p className="text-xs text-rose-500 mb-2">{couponError}</p>}
        <button onClick={onCreateCoupon} disabled={creatingCoupon} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
          {creatingCoupon ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
          Create Coupon
        </button>

        <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700/50">
          <button onClick={() => { onSetShowBulkForm(v => !v); onSetBulkResult(null) }} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
            <Plus size={11} />
            {showBulkForm ? 'Hide bulk generate' : 'Bulk generate unique codes'}
          </button>
          {showBulkForm && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <label className="text-xs text-slate-500">Prefix</label>
                  <input value={bulkForm.prefix} onChange={e => onSetBulkForm(f => ({ ...f, prefix: e.target.value.toUpperCase() }))} placeholder="CONF26" className={inputCls} />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Count</label>
                  <input type="number" min="1" max="1000" value={bulkForm.count} onChange={e => onSetBulkForm(f => ({ ...f, count: e.target.value }))} className={inputCls} />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-slate-500">Description</label>
                  <input value={bulkForm.description} onChange={e => onSetBulkForm(f => ({ ...f, description: e.target.value }))} placeholder="Conference promo" className={inputCls} />
                </div>
                <div>
                  <label className="text-xs text-slate-500">AI Credit ¢</label>
                  <input type="number" min="0" value={bulkForm.credit_cents} onChange={e => onSetBulkForm(f => ({ ...f, credit_cents: e.target.value }))} placeholder="50" className={inputCls} />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Bonus Messages</label>
                  <input type="number" min="0" value={bulkForm.bonus_messages} onChange={e => onSetBulkForm(f => ({ ...f, bonus_messages: e.target.value }))} placeholder="0" className={inputCls} />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Duration days</label>
                  <input type="number" min="1" value={bulkForm.duration_days} onChange={e => onSetBulkForm(f => ({ ...f, duration_days: e.target.value }))} placeholder="30" className={inputCls} />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Expires at</label>
                  <input type="datetime-local" value={bulkForm.expires_at} onChange={e => onSetBulkForm(f => ({ ...f, expires_at: e.target.value }))} className={inputCls} />
                </div>
              </div>
              <button onClick={onBulkGenerate} disabled={bulkGenerating || !bulkForm.prefix || !bulkForm.description} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
                {bulkGenerating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                Generate {bulkForm.count} codes
              </button>
              {bulkResult && (
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">Generated {bulkResult.length} codes</p>
                    <button onClick={() => navigator.clipboard.writeText(bulkResult.join('\n'))} className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 hover:underline">
                      <Copy size={10} /> Copy all
                    </button>
                  </div>
                  <p className="text-xs text-emerald-600 dark:text-emerald-500 font-mono break-all">
                    {bulkResult.slice(0, 20).join(', ')}{bulkResult.length > 20 ? ` … and ${bulkResult.length - 20} more` : ''}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <div className="flex items-center gap-2 glass-card rounded-lg px-3 py-1.5 flex-1 min-w-[200px]">
          <Search size={12} className="text-slate-400 shrink-0" />
          <input
            type="text"
            value={couponSearch}
            onChange={e => onSetCouponSearch(e.target.value)}
            placeholder="Search codes or descriptions…"
            className="bg-transparent text-xs text-slate-700 dark:text-slate-200 placeholder-slate-400 outline-none w-full"
          />
          {couponSearch && (
            <button onClick={() => onSetCouponSearch('')} className="text-slate-400 hover:text-slate-600 shrink-0">
              <X size={11} />
            </button>
          )}
        </div>
        <select value={couponStatusFilter} onChange={e => onSetCouponStatusFilter(e.target.value as typeof couponStatusFilter)} className={`${selectCls} py-1.5`}>
          <option value="all">All status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="expired">Expired</option>
          <option value="depleted">Depleted</option>
        </select>
        <select value={couponSort} onChange={e => onSetCouponSort(e.target.value as typeof couponSort)} className={`${selectCls} py-1.5`}>
          <option value="newest">Newest</option>
          <option value="most_used">Most used</option>
          <option value="expiring">Expiring soon</option>
        </select>
      </div>

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
                          <span className="text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">+{c.credit_cents}¢ credit</span>
                        )}
                        {c.bonus_messages > 0 && (
                          <span className="text-xs text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded">+{c.bonus_messages} messages</span>
                        )}
                        {c.duration_days && (
                          <span className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 px-1.5 py-0.5 rounded">{c.duration_days}d validity</span>
                        )}
                        {!c.is_active && (
                          <span className="text-xs text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded">inactive</span>
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
                            <button onClick={() => onLoadRedemptions(c.code)} className="text-xs tabular-nums text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 transition-colors shrink-0">
                              {c.redemption_count}/{c.max_redemptions} users
                            </button>
                          </div>
                        ) : (
                          <button onClick={() => onLoadRedemptions(c.code)} className="text-xs text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
                            {c.redemption_count} users
                          </button>
                        )}
                        {c.expires_at && (
                          <span className="text-xs text-slate-400">expires {new Date(c.expires_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>

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
                            onSetEditingCode(null)
                            onSetConfirmDeleteCode(null)
                            onSetDeleteConfirmInput('')
                          } else {
                            onSetEditingCode(c.code)
                            onSetEditForm({
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
                        onClick={() => onToggleCoupon(c.code, !c.is_active)}
                        title={c.is_active ? 'Deactivate' : 'Activate'}
                        className="p-0.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                      >
                        {c.is_active ? <ToggleRight size={18} className="text-violet-500" /> : <ToggleLeft size={18} />}
                      </button>
                    </div>
                  </div>

                  {isEditing && (
                    <div className="border-t border-slate-100 dark:border-slate-700/50 px-3 pb-4 pt-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                        <div className="col-span-2">
                          <label className="text-xs text-slate-500">Description</label>
                          <input value={editForm.description ?? ''} onChange={e => onSetEditForm(f => ({ ...f, description: e.target.value }))} className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">AI Credit ¢</label>
                          <input type="number" value={editForm.credit_cents ?? ''} onChange={e => onSetEditForm(f => ({ ...f, credit_cents: parseFloat(e.target.value) || 0 }))} className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Bonus Messages</label>
                          <input type="number" value={editForm.bonus_messages ?? ''} onChange={e => onSetEditForm(f => ({ ...f, bonus_messages: parseInt(e.target.value) || 0 }))} className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Max users</label>
                          <input type="number" value={editForm.max_redemptions ?? ''} onChange={e => onSetEditForm(f => ({ ...f, max_redemptions: parseInt(e.target.value) || null }))} className={inputCls} />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500">Credit days</label>
                          <input type="number" value={editForm.duration_days ?? ''} onChange={e => onSetEditForm(f => ({ ...f, duration_days: parseInt(e.target.value) || null }))} className={inputCls} />
                        </div>
                        <div className="col-span-2">
                          <label className="text-xs text-slate-500">Expires at</label>
                          <input type="datetime-local" value={editForm.expires_at?.slice(0, 16) ?? ''} onChange={e => onSetEditForm(f => ({ ...f, expires_at: e.target.value || null }))} className={inputCls} />
                        </div>
                      </div>
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => { onSetEditingCode(null); onSetConfirmDeleteCode(null); onSetDeleteConfirmInput('') }} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 px-3 py-1.5 transition-colors">
                          Cancel
                        </button>
                        <button onClick={() => onSaveCoupon(c.code)} disabled={savingEdit} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-50">
                          {savingEdit ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                          Save changes
                        </button>
                      </div>

                      <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-700/50">
                        <p className="text-xs font-semibold text-rose-500 uppercase tracking-wide mb-1">Danger zone</p>
                        <p className="text-xs text-slate-400 mb-2">Deleting removes this coupon. Existing redemptions and credits are NOT revoked.</p>
                        {confirmDeleteCode === c.code ? (
                          <div className="flex items-center gap-2 flex-wrap">
                            <input
                              type="text"
                              value={deleteConfirmInput}
                              onChange={e => onSetDeleteConfirmInput(e.target.value)}
                              placeholder={`Type ${c.code} to confirm`}
                              className={inputCls}
                              onKeyDown={e => { if (e.key === 'Enter' && deleteConfirmInput === c.code) onDeleteCoupon(c.code) }}
                            />
                            <button
                              onClick={() => onDeleteCoupon(c.code)}
                              disabled={deleteConfirmInput !== c.code || deletingCode === c.code}
                              className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold transition-colors disabled:opacity-40"
                            >
                              {deletingCode === c.code ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                              Delete
                            </button>
                            <button onClick={() => { onSetConfirmDeleteCode(null); onSetDeleteConfirmInput('') }} className="text-xs text-slate-400 hover:text-slate-600 shrink-0">Cancel</button>
                          </div>
                        ) : (
                          <button onClick={() => onSetConfirmDeleteCode(c.code)} className="flex items-center gap-1.5 text-xs text-rose-500 hover:text-rose-600 transition-colors">
                            <Trash2 size={11} />
                            Delete coupon
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {isRedemptionsOpen && (
                    <div className="border-t border-slate-100 dark:border-slate-700/50 px-3 pb-4 pt-3">
                      <div className="flex items-center justify-between mb-3">
                        <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                          Redemptions ({redemptions[c.code]?.length ?? '…'})
                        </p>
                        <button onClick={() => onSetExpandedRedemptionsCode(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
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
                                <p className="text-xs text-slate-400 truncate">{r.email}</p>
                              </div>
                              {r.credit_applied_cents > 0 && (
                                <span className="text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0">+{fmtCents(r.credit_applied_cents)}</span>
                              )}
                              {r.bonus_messages_applied > 0 && (
                                <span className="text-blue-600 dark:text-blue-400 tabular-nums shrink-0">+{r.bonus_messages_applied} msg</span>
                              )}
                              <span className="text-xs text-slate-400 shrink-0">
                                {new Date(r.redeemed_at).toLocaleDateString('default', { month: 'short', day: 'numeric' })}
                              </span>
                              {r.credit_expires_at && (
                                <span className="text-xs text-slate-400 shrink-0 hidden sm:block">
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
  )
}
