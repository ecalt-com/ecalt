import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Lock, X } from 'lucide-react'
import { useProfiles } from '../../lib/ProfileContext'
import ProfileAvatar from './ProfileAvatar'

// Pages that belong to the account holder, never to a child profile.
const PARENT_ONLY = ['/family', '/pricing', '/profile', '/admin', '/welcome']
// Pages reachable before a profile is picked.
const PICKER_EXEMPT = ['/profiles', '/claim', '/consent/', '/privacy-policy', '/terms', '/parents', '/contact']

const matches = (pathname: string, prefixes: string[]) =>
  prefixes.some(p => pathname === p || pathname.startsWith(p.endsWith('/') ? p : `${p}/`))

// Sends accounts with child profiles to the picker until this device has
// chosen one. Returns true when it rendered a redirect.
export function usePickerRedirect(): JSX.Element | null {
  const { pathname } = useLocation()
  const { needsPicker } = useProfiles()
  if (needsPicker && !matches(pathname, PICKER_EXEMPT)) return <Navigate to="/profiles" replace />
  return null
}

// Wraps the routes: inside a child profile, parent-only pages are replaced by
// a "grown-ups only" screen offering a PIN-protected switch back.
export function KidModeGuard({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { isKidMode, account, activeProfile, switchTo } = useProfiles()

  if (!isKidMode || !matches(pathname, PARENT_ONLY) || !account) return <>{children}</>

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
      <div className="glass-card rounded-3xl p-8 max-w-sm w-full text-center">
        <div className="flex justify-center mb-4">
          <ProfileAvatar name={activeProfile?.display_name ?? null} avatar={activeProfile?.avatar} size="lg" />
        </div>
        <div className="flex items-center justify-center gap-2 mb-2">
          <Lock size={16} className="text-violet-500" />
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">This part is for grown-ups</h1>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
          Ask your parent to switch to their profile with their PIN.
        </p>
        <button onClick={() => navigate('/learn')} className="w-full btn-primary mb-3">Back to learning</button>
        <button
          onClick={() => switchTo(account.uid)}
          className="w-full text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400 dark:hover:text-violet-400 py-1 transition-colors"
        >
          I'm the parent — switch with PIN
        </button>
      </div>
    </div>
  )
}

const NOTICE_KEY = 'ecalt.kidNoticeDismissed'

// Required disclosure inside a child profile: who manages it and what the
// parent can see. Teens are told plainly that the parent can open the profile.
export function KidModeNotice() {
  const { isKidMode, activeProfile } = useProfiles()
  // Profiles load after mount, so compare against the stored uid at render.
  const [dismissedUid, setDismissedUid] = useState<string | null>(() => {
    try { return sessionStorage.getItem(NOTICE_KEY) } catch { return null }
  })
  if (!isKidMode || !activeProfile || dismissedUid === activeProfile.uid) return null

  const dismiss = () => {
    try { sessionStorage.setItem(NOTICE_KEY, activeProfile.uid) } catch { /* ignore */ }
    setDismissedUid(activeProfile.uid)
  }
  const name = activeProfile.display_name?.split(' ')[0] ?? 'This'
  return (
    <div className="fixed bottom-4 left-4 right-4 sm:right-auto sm:max-w-sm z-40 glass rounded-2xl px-4 py-3 shadow-lg flex items-start gap-3">
      <ProfileAvatar name={activeProfile.display_name} avatar={activeProfile.avatar} />
      <p className="flex-1 text-xs text-slate-600 dark:text-slate-300">
        {activeProfile.age_group === 'child'
          ? <>You're in <strong>{name}'s</strong> profile. Your grown-up can see what you learn here.</>
          : <>You're in <strong>{name}'s</strong> profile. It's managed by your parent, who can open it and see everything in it — including chats.</>}
      </p>
      <button onClick={dismiss} aria-label="Dismiss" className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
        <X size={14} />
      </button>
    </div>
  )
}
