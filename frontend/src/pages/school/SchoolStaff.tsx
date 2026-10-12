import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Mail, UserPlus, X } from 'lucide-react'
import clsx from 'clsx'
import ProfileAvatar from '../../components/family/ProfileAvatar'
import { useAuth } from '../../lib/AuthContext'
import { useProfiles } from '../../lib/ProfileContext'
import { useSchool } from '../../lib/SchoolContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  changeStaffRole, inviteStaff, listStaff, removeStaff, revokeInvite, ROLE_LABEL, schoolErrorMessage,
  type StaffInvite, type StaffMember, type StaffRole,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500'

const ROLE_CHIP: Record<StaffRole, string> = {
  owner: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  admin: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  teacher: 'bg-slate-100 text-slate-600 dark:bg-slate-700/50 dark:text-slate-300',
}

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

// /school/staff (frontend-changes.md §3).
export default function SchoolStaff() {
  const { school, reload: reloadSchool } = useSchoolPage()
  const { user, getToken } = useAuth()
  const { account } = useProfiles()
  const { role: myRole, can, refresh: refreshSchools } = useSchool()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const me = account?.uid ?? user?.uid ?? null
  const canManage = can('manage_staff')

  const [members, setMembers] = useState<StaffMember[] | null>(null)
  const [invites, setInvites] = useState<StaffInvite[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)          // uid / invite id being changed
  const [confirming, setConfirming] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<StaffRole>('teacher')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      const data = await listStaff(school.id, token)
      setMembers(data.members)
      setInvites(data.invites)
      setLoadError(null)
    } catch (err) {
      setLoadError(schoolErrorMessage(apiErrorCode(err), "Couldn't load your staff. Please refresh and try again."))
    }
  }, [school.id, getToken])

  useEffect(() => { load() }, [load])

  const withToken = async <T,>(key: string, fn: (token: string) => Promise<T>): Promise<T | undefined> => {
    setBusy(key)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      return await fn(token)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message), 'error')
      return undefined
    } finally {
      setBusy(null)
    }
  }

  const sendInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || inviting) return
    setInviting(true)
    setInviteError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const invite = await inviteStaff(school.id, email.trim(), inviteRole, token)
      addToast(`Invite sent to ${invite.email} ✓`)
      setEmail('')
      setInviteRole('teacher')
      load()
    } catch (err) {
      setInviteError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setInviting(false)
    }
  }

  const changeRole = async (member: StaffMember, role: StaffRole) => {
    if (role === member.role) return
    const ok = await withToken(member.uid, token => changeStaffRole(school.id, member.uid, role, token))
    if (ok) {
      addToast(`${member.display_name ?? member.email ?? 'Staff member'} is now ${ROLE_LABEL[role].toLowerCase()} ✓`)
      load()
      if (member.uid === me) refreshSchools()
    }
  }

  const remove = async (member: StaffMember) => {
    const leaving = member.uid === me
    const done = await withToken(member.uid, token => removeStaff(school.id, member.uid, token).then(() => true))
    setConfirming(null)
    if (!done) return
    if (leaving) {
      addToast(`You left ${school.name}`)
      await refreshSchools()
      navigate('/school', { replace: true })
      return
    }
    addToast('Removed from staff ✓')
    load()
    reloadSchool()
  }

  const revoke = async (invite: StaffInvite) => {
    const done = await withToken(invite.id, token => revokeInvite(school.id, invite.id, token).then(() => true))
    if (done) setInvites(prev => prev.filter(i => i.id !== invite.id))
  }

  const roleOptions: StaffRole[] = myRole === 'owner' ? ['owner', 'admin', 'teacher'] : ['admin', 'teacher']

  if (loadError) {
    return <div className="glass-card rounded-2xl p-5 text-sm text-rose-600 dark:text-rose-400" role="alert">{loadError}</div>
  }
  if (members === null) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
  }

  return (
    <div className="space-y-5">
      {canManage && (
        <form onSubmit={sendInvite} className="glass-card rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-2">
            <UserPlus size={15} className="text-violet-500" /> Invite staff
          </h2>
          <div className="flex flex-col sm:flex-row gap-2">
            <label className="flex-1">
              <span className="sr-only">Email address</span>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="teacher@school.org"
                required
                className={clsx(fieldCls, 'w-full')}
              />
            </label>
            <label>
              <span className="sr-only">Role</span>
              <select value={inviteRole} onChange={e => setInviteRole(e.target.value as StaffRole)} className={clsx(fieldCls, 'w-full sm:w-auto')}>
                {roleOptions.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
            </label>
            <button type="submit" disabled={inviting || !email.trim()} className="btn-primary !py-2.5 flex items-center justify-center gap-2">
              {inviting ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />} Send invite
            </button>
          </div>
          {inviteError && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400" role="alert">{inviteError}</p>}
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            They'll get an email link and must sign in with the Google account for that address. Links expire after 7 days.
          </p>
        </form>
      )}

      <div className="glass-card rounded-2xl p-2 sm:p-3">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 px-3 pt-2 pb-1">Staff ({members.length})</h2>
        <ul className="divide-y divide-slate-200/70 dark:divide-slate-700/50">
          {members.map(member => {
            const isMe = member.uid === me
            const canEdit = canManage && (member.role !== 'owner' || myRole === 'owner')
            const canRemove = isMe || canEdit
            return (
              <li key={member.uid} className="flex items-center gap-3 px-3 py-3 flex-wrap">
                <ProfileAvatar name={member.display_name ?? member.email} photoUrl={member.photo_url} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">
                    {member.display_name ?? member.email}{isMe && <span className="text-slate-400 font-normal"> (you)</span>}
                  </p>
                  {member.email && <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{member.email}</p>}
                </div>

                {canEdit ? (
                  <label>
                    <span className="sr-only">Role for {member.display_name ?? member.email}</span>
                    <select
                      value={member.role}
                      disabled={busy === member.uid}
                      onChange={e => changeRole(member, e.target.value as StaffRole)}
                      className="px-2 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-xs text-slate-700 dark:text-slate-200 focus:outline-none focus:border-violet-400"
                    >
                      {(roleOptions.includes(member.role) ? roleOptions : [member.role, ...roleOptions]).map(r => (
                        <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <span className={clsx('text-xs px-2 py-0.5 rounded-full', ROLE_CHIP[member.role])}>{ROLE_LABEL[member.role]}</span>
                )}

                {canRemove && (confirming === member.uid ? (
                  <span className="flex items-center gap-1.5 text-xs">
                    <span className="text-slate-500 dark:text-slate-400">{isMe ? 'Leave this school?' : 'Remove?'}</span>
                    <button
                      onClick={() => remove(member)}
                      disabled={busy === member.uid}
                      className="px-2 py-1 rounded-lg font-semibold bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-60"
                    >
                      {busy === member.uid ? <Loader2 size={12} className="animate-spin" /> : 'Yes'}
                    </button>
                    <button onClick={() => setConfirming(null)} className="px-2 py-1 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirming(member.uid)}
                    className="text-xs text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400 px-2 py-1"
                  >
                    {isMe ? 'Leave' : 'Remove'}
                  </button>
                ))}
              </li>
            )
          })}
        </ul>
      </div>

      {canManage && invites.length > 0 && (
        <div className="glass-card rounded-2xl p-2 sm:p-3">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 px-3 pt-2 pb-1">Pending invites</h2>
          <ul className="divide-y divide-slate-200/70 dark:divide-slate-700/50">
            {invites.map(invite => (
              <li key={invite.id} className="flex items-center gap-3 px-3 py-3 flex-wrap">
                <Mail size={15} className="text-slate-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-800 dark:text-slate-100 truncate">{invite.email}</p>
                  <p className={clsx('text-xs', invite.expired ? 'text-amber-600 dark:text-amber-400' : 'text-slate-500 dark:text-slate-400')}>
                    {ROLE_LABEL[invite.role]} · {invite.expired ? 'expired — send a new invite' : `expires ${fmtDate(invite.expires_at)}`}
                  </p>
                </div>
                <button
                  onClick={() => revoke(invite)}
                  disabled={busy === invite.id}
                  aria-label={`Revoke invite for ${invite.email}`}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400 px-2 py-1 disabled:opacity-60"
                >
                  {busy === invite.id ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />} Revoke
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
