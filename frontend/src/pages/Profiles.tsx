import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, Plus, Loader2 } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import ProfileAvatar from '../components/family/ProfileAvatar'
import { useAuth } from '../lib/AuthContext'
import { useProfiles } from '../lib/ProfileContext'

// "Who's learning?" — the profile picker for accounts with child profiles.
export default function Profiles() {
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()
  const { loaded, account, profiles, activeProfile, isKidMode, switchTo, ensureParentUnlock } = useProfiles()
  const [switching, setSwitching] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  if (authLoading || !loaded || !account) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-violet-500" />
      </div>
    )
  }

  const pick = async (uid: string) => {
    if (switching) return
    if (uid === activeProfile?.uid) { navigate('/learn'); return }
    setSwitching(uid)
    const ok = await switchTo(uid)
    if (!ok) setSwitching(null)
  }

  const addChild = async () => {
    if (await ensureParentUnlock('Enter your parent PIN to add a child.')) navigate('/family?add=1')
  }

  const tiles = [
    { uid: account.uid, name: account.display_name, avatar: account.avatar, photo: account.photo_url, parent: true, note: null as string | null },
    ...profiles.map(p => ({
      uid: p.uid,
      name: p.display_name,
      avatar: p.avatar,
      photo: null,
      parent: false,
      note: p.paused ? 'Paused' : p.account_status === 'parental_consent_pending' ? 'Needs verification' : null,
    })),
  ]

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex flex-col items-center justify-center px-4 py-16">
      <PageMeta title="Who's learning?" description="Choose a profile" />
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2 text-center">Who's learning?</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-10 text-center">
        {isKidMode ? 'Switching profiles needs your grown-up\'s PIN.' : 'Pick a profile to continue.'}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 sm:gap-8 max-w-xl w-full">
        {tiles.map(t => (
          <button
            key={t.uid}
            onClick={() => pick(t.uid)}
            disabled={!!switching}
            className="group flex flex-col items-center gap-3 p-3 rounded-2xl transition-all hover:bg-slate-100/70 dark:hover:bg-slate-800/40 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <div className={`relative transition-transform group-hover:scale-105 ${t.uid === activeProfile?.uid ? 'ring-2 ring-violet-500 ring-offset-2 ring-offset-[var(--bg-primary)] rounded-3xl' : ''}`}>
              <ProfileAvatar name={t.name} avatar={t.avatar} photoUrl={t.photo} size="lg" />
              {t.parent && profiles.length > 0 && (
                <span className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-white dark:bg-slate-800 shadow flex items-center justify-center">
                  <Lock size={12} className="text-slate-500" />
                </span>
              )}
              {switching === t.uid && (
                <span className="absolute inset-0 rounded-3xl bg-black/30 flex items-center justify-center">
                  <Loader2 size={20} className="animate-spin text-white" />
                </span>
              )}
            </div>
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate max-w-full">
              {t.name?.split(' ')[0] ?? 'Me'}
            </span>
            {t.note && <span className="text-[11px] text-amber-600 dark:text-amber-400 -mt-2">{t.note}</span>}
          </button>
        ))}

        {!isKidMode && profiles.length < 5 && (
          <button
            onClick={addChild}
            className="group flex flex-col items-center gap-3 p-3 rounded-2xl transition-all hover:bg-slate-100/70 dark:hover:bg-slate-800/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <div className="w-20 h-20 rounded-3xl border-2 border-dashed border-slate-300 dark:border-slate-600 flex items-center justify-center text-slate-400 group-hover:border-violet-400 group-hover:text-violet-500 transition-colors">
              <Plus size={28} />
            </div>
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Add a child</span>
          </button>
        )}
      </div>
    </div>
  )
}
