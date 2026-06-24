import { useEffect, useState } from 'react'
import { Shield, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import type { ImpersonationSession } from '../types'

interface ImpersonationLogTabProps {
  getToken: () => Promise<string | null>
}

function sessionStatus(s: ImpersonationSession): { label: string; cls: string } {
  if (s.ended_at) return { label: 'ended', cls: 'text-slate-400 bg-slate-100 dark:bg-slate-700/50' }
  if (new Date(s.expires_at) <= new Date()) return { label: 'expired', cls: 'text-slate-400 bg-slate-100 dark:bg-slate-700/50' }
  return { label: 'active', cls: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10' }
}

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function ImpersonationLogTab({ getToken }: ImpersonationLogTabProps) {
  const [sessions, setSessions] = useState<ImpersonationSession[]>([])
  const [loading, setLoading] = useState(true)
  const [revoking, setRevoking] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const token = await getToken()
      if (!token) return
      const res = await fetch('/api/v1/admin/impersonation-log', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok && !cancelled) {
        const data = await res.json()
        setSessions(data.sessions ?? [])
      }
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [getToken])

  const handleRevoke = async (sessionId: string) => {
    setRevoking(sessionId)
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch(`/api/v1/admin/impersonate/sessions/${sessionId}/revoke`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setSessions(prev =>
          prev.map(s => s.id === sessionId ? { ...s, ended_at: new Date().toISOString(), ended_by: 'revoke' } : s)
        )
      }
    } finally {
      setRevoking(null)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 size={18} className="animate-spin text-violet-500" />
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="text-center py-12 text-xs text-slate-400">
        No impersonation sessions recorded yet.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <Shield size={14} className="text-violet-500" />
        <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
          Impersonation Log ({sessions.length})
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-200 dark:border-slate-700">
              <th className="text-left py-2 pr-4 font-medium">Admin</th>
              <th className="text-left py-2 pr-4 font-medium">Target user</th>
              <th className="text-left py-2 pr-4 font-medium">Started</th>
              <th className="text-left py-2 pr-4 font-medium">Ended</th>
              <th className="text-right py-2 pr-4 font-medium">Requests</th>
              <th className="text-left py-2 pr-4 font-medium">Reason</th>
              <th className="text-left py-2 font-medium">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {sessions.map(s => {
              const status = sessionStatus(s)
              const isActive = status.label === 'active'
              return (
                <tr key={s.id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 pr-4">
                    <p className="font-medium text-slate-800 dark:text-slate-200">{s.admin_name ?? '—'}</p>
                    <p className="text-slate-400 truncate max-w-[140px]">{s.admin_email ?? s.admin_uid}</p>
                  </td>
                  <td className="py-2.5 pr-4">
                    <p className="font-medium text-slate-800 dark:text-slate-200">{s.target_name ?? '—'}</p>
                    <p className="text-slate-400 truncate max-w-[140px]">{s.target_email ?? s.target_uid}</p>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-500 whitespace-nowrap">{fmt(s.created_at)}</td>
                  <td className="py-2.5 pr-4 text-slate-500 whitespace-nowrap">
                    {s.ended_at ? fmt(s.ended_at) : (isActive ? '—' : fmt(s.expires_at))}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-slate-600 dark:text-slate-300">
                    {s.request_count}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-400 max-w-[120px] truncate">
                    {s.reason ?? '—'}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', status.cls)}>
                      {status.label}
                    </span>
                  </td>
                  <td className="py-2.5">
                    {isActive && (
                      <button
                        onClick={() => handleRevoke(s.id)}
                        disabled={revoking === s.id}
                        className="text-xs text-rose-500 hover:text-rose-600 dark:text-rose-400 px-2 py-0.5 rounded hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors"
                      >
                        {revoking === s.id ? <Loader2 size={10} className="animate-spin inline" /> : 'Revoke'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
