import { Loader2 } from 'lucide-react'
import type { RetentionData } from '../types'
import { StatCard } from '../components/StatCard'

interface RetentionTabProps { retentionData: RetentionData | null }

export function RetentionTab({ retentionData }: RetentionTabProps) {
  if (!retentionData) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Loading retention data…
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <StatCard label="DAU"        value={String(retentionData.active_users.dau)} />
        <StatCard label="WAU"        value={String(retentionData.active_users.wau)} />
        <StatCard label="MAU"        value={String(retentionData.active_users.mau)} />
        <StatCard label="Stickiness" value={`${retentionData.active_users.stickiness}%`} />
      </div>

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
                        <div className="w-full bg-violet-500/70 dark:bg-violet-500/50 rounded-t" style={{ height: `${Math.max(barPct, 4)}%` }} />
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between mt-2">
                  <span className="text-[9px] text-slate-400">{retentionData.weekly_signups[0]?.week_start}</span>
                  <span className="text-[9px] text-slate-400">{retentionData.weekly_signups[retentionData.weekly_signups.length - 1]?.week_start}</span>
                </div>
              </>
            )
          })()}
        </div>
      )}

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
              const daysSinceSignup = signupDate ? Math.floor((today.getTime() - signupDate.getTime()) / 86_400_000) : null
              const daysSinceActive = lastActive ? Math.floor((today.getTime() - lastActive.getTime()) / 86_400_000) : null
              return (
                <div key={u.uid} className="px-5 py-3 flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">{u.display_name ?? u.email ?? u.uid}</p>
                    <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 shrink-0 hidden sm:block">{u.plan_id}</span>
                  <div className="shrink-0 text-right">
                    <p className="text-[10px] text-slate-500">{daysSinceSignup !== null ? `joined ${daysSinceSignup}d ago` : '—'}</p>
                    <p className="text-[10px] text-amber-500">{daysSinceActive !== null ? `inactive ${daysSinceActive}d` : 'never active'}</p>
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
  )
}
