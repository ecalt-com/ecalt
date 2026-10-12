import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useOutletContext } from 'react-router-dom'
import { Loader2, School as SchoolIcon, ShieldAlert } from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../../components/Navigation'
import PageMeta from '../../components/PageMeta'
import { useAuth } from '../../lib/AuthContext'
import { useSchool } from '../../lib/SchoolContext'
import { apiErrorCode } from '../../lib/api'
import { getSchool, ROLE_LABEL, schoolErrorMessage, type School } from '../../lib/schoolApi'

export interface SchoolOutletContext {
  school: School
  setSchool: (school: School) => void
  reload: () => Promise<void>
}

export const useSchoolPage = () => useOutletContext<SchoolOutletContext>()

const STATUS_CHIP: Record<string, string> = {
  onboarding: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  suspended: 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4 flex items-start justify-center">
        <div className="glass-card rounded-2xl p-8 max-w-md w-full text-center mt-10">{children}</div>
      </div>
    </>
  )
}

// Staff area shell (backend/plans/school-courses/frontend-changes.md §2).
export default function SchoolLayout() {
  const { user, loading: authLoading, getToken } = useAuth()
  const { loaded, schools, activeSchool, setActiveSchool, refresh } = useSchool()
  const navigate = useNavigate()
  const [school, setSchool] = useState<School | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  const reload = useCallback(async () => {
    if (!activeSchool) return
    const token = await getToken()
    if (!token) return
    try {
      setSchool(await getSchool(activeSchool.id, token))
      setError(null)
    } catch (err) {
      const code = apiErrorCode(err)
      if (code === 'school_not_found') {
        // Removed from the school, or it was terminated: drop it from the switcher.
        setSchool(null)
        await refresh()
        return
      }
      setError(code ?? 'unknown')
    }
  }, [activeSchool, getToken, refresh])

  useEffect(() => {
    setSchool(null)
    setError(null)
    reload()
  }, [reload])

  if (authLoading || !user || !loaded) {
    return <Centered><Loader2 className="animate-spin text-violet-500 mx-auto" /></Centered>
  }

  if (schools.length === 0) {
    return (
      <Centered>
        <div className="w-12 h-12 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
          <SchoolIcon size={24} className="text-violet-600 dark:text-violet-400" />
        </div>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">You're not on a school's staff</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          School access starts with an invite from your school's ECALT admin. Open the invite email on
          this device, signed in with the Google account it was sent to.
        </p>
      </Centered>
    )
  }

  if (error === 'school_access_suspended') {
    return (
      <Centered>
        <ShieldAlert size={28} className="text-rose-500 mx-auto mb-3" />
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">{activeSchool?.name}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{schoolErrorMessage(error)}</p>
      </Centered>
    )
  }

  const tabs = [
    { to: '/school', label: 'Dashboard', end: true },
    { to: '/school/staff', label: 'Staff', end: false },
    { to: '/school/settings', label: 'Settings', end: false },
  ]

  return (
    <>
      <PageMeta title={activeSchool ? `${activeSchool.name} — School` : 'School'} />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-start justify-between gap-3 flex-wrap mb-5">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">
                  {school?.name ?? activeSchool?.name}
                </h1>
                {school && school.status !== 'active' && (
                  <span className={clsx('text-xs px-2 py-0.5 rounded-full capitalize', STATUS_CHIP[school.status])}>
                    {school.status === 'onboarding' ? 'Setting up' : school.status}
                  </span>
                )}
              </div>
              {activeSchool && (
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                  You're {activeSchool.role === 'admin' || activeSchool.role === 'owner' ? 'an' : 'a'}{' '}
                  {ROLE_LABEL[activeSchool.role].toLowerCase()} here
                </p>
              )}
            </div>
            {schools.length > 1 && (
              <label className="text-xs text-slate-500 dark:text-slate-400">
                <span className="sr-only">Switch school</span>
                <select
                  value={activeSchool?.id ?? ''}
                  onChange={e => setActiveSchool(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-violet-400"
                >
                  {schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
            )}
          </div>

          <nav aria-label="School sections" className="flex gap-1 mb-6 p-1 glass-card rounded-xl overflow-x-auto flex-nowrap w-fit max-w-full">
            {tabs.map(t => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) => clsx(
                  'px-4 py-1.5 rounded-lg text-sm font-medium transition-all shrink-0',
                  isActive
                    ? 'bg-violet-600 text-white'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
                )}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>

          {error && error !== 'school_access_suspended' && (
            <div className="glass-card rounded-2xl p-5 mb-5 text-sm text-rose-600 dark:text-rose-400" role="alert">
              {schoolErrorMessage(error, "Couldn't load your school. Please refresh and try again.")}
            </div>
          )}

          {!school && !error && (
            <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
          )}

          {school && <Outlet context={{ school, setSchool, reload } satisfies SchoolOutletContext} />}

        </div>
      </div>
    </>
  )
}
