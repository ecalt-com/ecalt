import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Award, BookOpen, Flame, ArrowRight, Lock } from 'lucide-react'
import Navigation from '../components/Navigation'
import { useAuth } from '../lib/AuthContext'
import { getPassport, getUserProfile, type PassportData } from '../lib/api'
import { usePageTitle } from '../lib/usePageTitle'

export default function Passport() {
  usePageTitle('Capability Passport')
  const navigate = useNavigate()
  const { user, loading: authLoading, getToken } = useAuth()
  const [passport, setPassport] = useState<PassportData | null>(null)
  const [streakDays, setStreakDays] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authLoading) return
    if (!user) { setLoading(false); return }

    getToken().then(token => {
      if (!token) return
      Promise.all([getPassport(token), getUserProfile(token)]).then(([passportData, profile]) => {
        setPassport(passportData)
        setStreakDays(profile.streak_days ?? 0)
      }).catch(() => {})
    }).finally(() => setLoading(false))
  }, [user, authLoading])

  const fullyCompleted = passport?.journeys.filter(j => j.fully_completed) ?? []
  const inProgress = passport?.journeys.filter(j => !j.fully_completed) ?? []

  if (!authLoading && !user) {
    return (
      <>
        <Navigation />
        <div className="relative min-h-screen pt-28 pb-20 px-4 flex items-center justify-center">
          <div className="glass-card rounded-3xl p-12 text-center max-w-md">
            <Lock size={32} className="text-violet-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Sign in to view your Passport</h2>
            <p className="text-sm text-slate-500 mb-6">Your capability record is tied to your account.</p>
            <button onClick={() => navigate('/')} className="btn-primary mx-auto">Go home</button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[400px] h-[400px] bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <Navigation />

      <div className="relative min-h-screen pt-28 pb-20 px-4 max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-10">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">ECALT</p>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 mb-1">Capability Passport</h1>
            <p className="text-slate-500 text-sm">{user?.displayName ?? 'Your'} verified learning record</p>
          </div>
          <div className="glass rounded-2xl px-4 sm:px-5 py-3 sm:py-4 text-center shrink-0">
            <div className="flex items-center gap-1.5 text-amber-500 dark:text-amber-400 mb-1">
              <Flame size={14} />
              <span className="text-xs font-medium">Earned</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{passport?.total_completed ?? 0}</p>
            <p className="text-xs text-slate-500">badges</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 sm:gap-4 mb-10">
          {[
            { label: 'Missions Complete', value: passport?.total_completed ?? 0,   icon: Award,    color: 'text-violet-600 dark:text-violet-400' },
            { label: 'Topics Explored',   value: passport?.categories.length ?? 0, icon: BookOpen, color: 'text-cyan-600 dark:text-cyan-400' },
            { label: 'Hours Invested',    value: passport?.estimated_hours ?? 0,   icon: Flame,    color: 'text-amber-600 dark:text-amber-400' },
            { label: 'Day Streak',        value: streakDays,                        icon: Flame,    color: 'text-orange-500 dark:text-orange-400' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="glass-card rounded-2xl p-3 sm:p-5 text-center">
              <Icon size={18} className={`${color} mx-auto mb-2`} />
              <p className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100">
                {Number.isInteger(value) ? value : (value as number).toFixed(1)}
              </p>
              <p className="text-[10px] sm:text-xs text-slate-500 mt-1 leading-tight">{label}</p>
            </div>
          ))}
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="shimmer-bg rounded-2xl h-20" />)}
          </div>
        ) : (
          <>
            {/* Earned */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-5">
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                <span className="text-xs text-slate-400 uppercase tracking-widest">Capabilities Earned</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
              </div>

              {fullyCompleted.length === 0 ? (
                <div className="glass-card rounded-2xl p-12 text-center">
                  <div className="text-5xl mb-4">🗺️</div>
                  <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-2">No capabilities yet</h3>
                  <p className="text-sm text-slate-500 mb-6 max-w-xs mx-auto">
                    Complete all steps in a journey to earn a capability badge.
                  </p>
                  <button onClick={() => navigate('/journeys')} className="btn-primary flex items-center gap-2 mx-auto">
                    Browse journeys <ArrowRight size={14} />
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {fullyCompleted.map(j => (
                    <div key={j.id} className="glass-card rounded-2xl p-4 sm:p-5 flex items-center gap-3 sm:gap-4">
                      <span className="text-2xl sm:text-3xl shrink-0">{j.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{j.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          #{j.category} · {new Date(j.completed_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="px-2 sm:px-3 py-1 rounded-full text-xs border border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300 font-medium shrink-0">
                        Earned
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* In progress */}
            {inProgress.length > 0 && (
              <div className="mb-8">
                <div className="flex items-center gap-3 mb-5">
                  <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                  <span className="text-xs text-slate-400 uppercase tracking-widest">In Progress</span>
                  <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                </div>
                <div className="space-y-3">
                  {inProgress.map(j => (
                    <button
                      key={j.id}
                      onClick={() => navigate(`/journey/${j.id}`)}
                      className="w-full glass-card rounded-2xl p-4 flex items-center gap-3 hover:border-violet-300 dark:hover:border-violet-500/40 transition-colors text-left"
                    >
                      <span className="text-2xl shrink-0">{j.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">{j.title}</p>
                        <div className="mt-1.5 h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-violet-500 to-cyan-500 rounded-full"
                            style={{ width: `${Math.round((j.completed_steps / j.total_steps) * 100)}%` }}
                          />
                        </div>
                        <p className="text-xs text-slate-400 mt-1">{j.completed_steps}/{j.total_steps} steps</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Topic cloud */}
            {(passport?.categories.length ?? 0) > 0 && (
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-widest mb-3">Topics Explored</p>
                <div className="flex flex-wrap gap-2">
                  {passport!.categories.map(c => (
                    <span key={c} className="px-3 py-1.5 rounded-full text-sm border border-slate-200 bg-slate-100/60 text-slate-500 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
                      #{c}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
