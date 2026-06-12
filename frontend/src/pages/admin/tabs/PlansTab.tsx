import { Check, AlertTriangle, Plus, Save, Loader2, Zap } from 'lucide-react'
import type { PlanRow, NewPlanForm } from '../types'
import { PLAN_ICONS, PLAN_FEATURES, inputCls } from '../constants'

interface PlansTabProps {
  plans: PlanRow[]
  edits: Record<string, Partial<PlanRow>>
  saving: string | null
  provisioning: Record<string, string | null>
  newPlanForm: NewPlanForm
  creatingPlan: boolean
  onSetEdit: (planId: string, field: string, value: string | number | boolean | null) => void
  onSavePlan: (planId: string) => void
  onProvision: (planId: string, gateway: 'stripe' | 'razorpay' | 'both') => void
  onSetNewPlanForm: React.Dispatch<React.SetStateAction<NewPlanForm>>
  onCreatePlan: () => void
}

export function PlansTab({
  plans,
  edits,
  saving,
  provisioning,
  newPlanForm,
  creatingPlan,
  onSetEdit,
  onSavePlan,
  onProvision,
  onSetNewPlanForm,
  onCreatePlan,
}: PlansTabProps) {
  return (
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
                  {plan.max_seats > 1 && <p className="text-xs text-slate-500">Up to {plan.max_seats} users</p>}
                </div>
              </div>
              <div className="mb-3">
                {plan.base_price_cents === 0
                  ? <span className="text-lg font-bold text-slate-800 dark:text-slate-100">Free</span>
                  : <><span className="text-lg font-bold text-slate-800 dark:text-slate-100">${(plan.base_price_cents / 100).toFixed(0)}</span><span className="text-xs text-slate-400">/mo</span></>
                }
              </div>
              <ul className="space-y-1.5 flex-1">
                {features.map(f => (
                  <li key={f} className="flex items-start gap-1.5 text-xs text-slate-600 dark:text-slate-400">
                    <Check size={10} className="text-violet-500 dark:text-violet-400 mt-0.5 shrink-0" />{f}
                  </li>
                ))}
              </ul>
              {!plan.is_active && (
                <span className="mt-2 text-xs text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded self-start">inactive</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="glass-card rounded-2xl p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Plus size={14} className="text-violet-500 dark:text-violet-400" />
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Create New Plan</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
          <div>
            <label className="text-xs text-slate-500">Plan ID slug</label>
            <input value={newPlanForm.plan_id} onChange={e => onSetNewPlanForm(f => ({ ...f, plan_id: e.target.value }))} placeholder="individual" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500">Display Name</label>
            <input value={newPlanForm.name} onChange={e => onSetNewPlanForm(f => ({ ...f, name: e.target.value }))} placeholder="Individual" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500">USD $/mo (cents)</label>
            <input type="number" min="0" value={newPlanForm.base_price_cents} onChange={e => onSetNewPlanForm(f => ({ ...f, base_price_cents: e.target.value }))} placeholder="999" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500">INR ₹/mo (paise)</label>
            <input type="number" min="0" value={newPlanForm.base_price_inr_paise} onChange={e => onSetNewPlanForm(f => ({ ...f, base_price_inr_paise: e.target.value }))} placeholder="79900" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500">Token budget (cents)</label>
            <input type="number" min="0" value={newPlanForm.token_budget_cents} onChange={e => onSetNewPlanForm(f => ({ ...f, token_budget_cents: e.target.value }))} placeholder="5000" className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-500">Max seats</label>
            <input type="number" min="1" value={newPlanForm.max_seats} onChange={e => onSetNewPlanForm(f => ({ ...f, max_seats: e.target.value }))} className={inputCls} />
          </div>
        </div>
        <button
          onClick={onCreatePlan}
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
                  <span className="text-xs text-slate-400 font-mono">{plan.plan_id}</span>
                  {!plan.is_active && (
                    <span className="text-xs text-rose-500 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded">inactive</span>
                  )}
                </div>
                {isDirty && (
                  <button
                    onClick={() => onSavePlan(plan.plan_id)}
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
                  <input type="number" defaultValue={plan.base_price_cents} onChange={e => onSetEdit(plan.plan_id, 'base_price_cents', parseInt(e.target.value))} className={inputCls} />
                </label>
                {plan.base_price_cents > 0 && (
                  <label className="text-xs text-slate-500">
                    INR Price (paise)
                    <input type="number" defaultValue={plan.base_price_inr_paise ?? ''} placeholder="e.g. 79900" onChange={e => onSetEdit(plan.plan_id, 'base_price_inr_paise', parseInt(e.target.value) || null)} className={inputCls} />
                  </label>
                )}
                <label className="text-xs text-slate-500">
                  Token budget (cents)
                  <input type="number" defaultValue={plan.token_budget_cents} onChange={e => onSetEdit(plan.plan_id, 'token_budget_cents', parseInt(e.target.value))} className={inputCls} />
                  {currentTokenBudget > 0 && (
                    <span className="text-xs text-slate-400 mt-0.5 block">≈ ${(currentTokenBudget / 10000).toFixed(2)} of AI spend / month</span>
                  )}
                </label>
                <label className="text-xs text-slate-500">
                  Max seats
                  <input type="number" defaultValue={plan.max_seats} onChange={e => onSetEdit(plan.plan_id, 'max_seats', parseInt(e.target.value))} className={inputCls} />
                </label>
                <label className="text-xs text-slate-500 flex items-center gap-2 self-end pb-1.5">
                  <input type="checkbox" defaultChecked={plan.is_active} onChange={e => onSetEdit(plan.plan_id, 'is_active', e.target.checked)} />
                  Active
                </label>
              </div>

              {plan.base_price_cents > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700/50">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">Gateway Configuration</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
                    <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {plan.stripe_price_id
                          ? <Check size={11} className="text-emerald-500 shrink-0" />
                          : <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                        }
                        <span className="text-xs font-mono text-slate-600 dark:text-slate-400 truncate">
                          {plan.stripe_price_id ? `Stripe ${plan.stripe_price_id}` : 'Stripe: Not provisioned'}
                        </span>
                      </div>
                      <button
                        onClick={() => onProvision(plan.plan_id, 'stripe')}
                        disabled={!!provisioning[plan.plan_id]}
                        className="text-xs shrink-0 flex items-center gap-1 px-2 py-1 rounded-md bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 hover:bg-violet-200 dark:hover:bg-violet-500/25 transition-colors disabled:opacity-50"
                      >
                        {provisioning[plan.plan_id] === 'stripe' && <Loader2 size={9} className="animate-spin" />}
                        {plan.stripe_price_id ? 'Re-provision' : 'Provision'}
                      </button>
                    </div>
                    <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {plan.razorpay_plan_id
                          ? <Check size={11} className="text-emerald-500 shrink-0" />
                          : <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                        }
                        <span className="text-xs font-mono text-slate-600 dark:text-slate-400 truncate">
                          {plan.razorpay_plan_id ? `Razorpay ${plan.razorpay_plan_id}` : 'Razorpay: Not provisioned'}
                        </span>
                      </div>
                      <button
                        onClick={() => onProvision(plan.plan_id, 'razorpay')}
                        disabled={!!provisioning[plan.plan_id]}
                        className="text-xs shrink-0 flex items-center gap-1 px-2 py-1 rounded-md bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 hover:bg-violet-200 dark:hover:bg-violet-500/25 transition-colors disabled:opacity-50"
                      >
                        {provisioning[plan.plan_id] === 'razorpay' && <Loader2 size={9} className="animate-spin" />}
                        {plan.razorpay_plan_id ? 'Re-provision' : 'Provision'}
                      </button>
                    </div>
                  </div>
                  <button
                    onClick={() => onProvision(plan.plan_id, 'both')}
                    disabled={!!provisioning[plan.plan_id]}
                    className="w-full text-xs flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-violet-400 dark:hover:border-violet-500/50 transition-colors disabled:opacity-50"
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
  )
}
