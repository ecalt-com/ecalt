import { Search, ShieldCheck, ShieldOff, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import type { UserRow, UserDetail } from '../types'
import { fmtCents, fmtPct, calcPct } from '../utils'
import { UserDetailPanel } from '../components/UserDetailPanel'

interface UsersTabProps {
  users: UserRow[]
  filteredUsers: UserRow[]
  userSearch: string
  togglingUid: string | null
  expandedUid: string | null
  userDetails: Record<string, UserDetail>
  loadingDetail: string | null
  onSetUserSearch: (v: string) => void
  onExpandUser: (uid: string) => void
  onToggleAdmin: (uid: string) => void
}

export function UsersTab({
  users,
  filteredUsers,
  userSearch,
  togglingUid,
  expandedUid,
  userDetails,
  loadingDetail,
  onSetUserSearch,
  onExpandUser,
  onToggleAdmin,
}: UsersTabProps) {
  return (
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
            onChange={e => onSetUserSearch(e.target.value)}
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
              <div
                className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                onClick={() => onExpandUser(u.uid)}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                    {u.display_name ?? 'Unknown'}
                    {u.is_admin && (
                      <span className="ml-2 text-[10px] text-violet-600 dark:text-violet-300 bg-violet-100 dark:bg-violet-500/20 px-1.5 py-0.5 rounded-full">admin</span>
                    )}
                  </p>
                  <p className="text-[11px] text-slate-500 truncate">{u.email ?? u.uid}</p>
                </div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono shrink-0 hidden sm:block">{u.plan_id}</span>
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
                <span className="text-[10px] text-slate-400 tabular-nums shrink-0 hidden md:block w-16 text-right">
                  {u.message_count} req
                </span>
                <div className="flex items-center gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => onToggleAdmin(u.uid)}
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

              {isExpanded && (
                <div className="border-t border-slate-100 dark:border-slate-700/50 px-4 pb-5 pt-4">
                  <UserDetailPanel detail={detail} isLoading={isLoadingThis} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
