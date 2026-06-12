import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Zap, Menu, X, LogOut } from 'lucide-react'
import clsx from 'clsx'
import ThemeToggle from './ThemeToggle'
import { useAuth } from '../lib/AuthContext'
import { useSubscription } from '../lib/SubscriptionContext'

const PUBLIC_LINKS = [
  { to: '/explore', label: 'Explore' },
  { to: '/journeys', label: 'Journeys' },
  { to: '/pricing', label: 'Pricing' },
]

const AUTH_LINKS = [
  { to: '/learn', label: 'Learn' },
  { to: '/passport', label: 'Passport' },
  { to: '/mind-signature', label: 'Mind Signature' },
]

function UserAvatar({ photoURL, displayName }: { photoURL: string | null; displayName: string | null }) {
  if (photoURL) {
    return <img src={photoURL} alt={displayName ?? 'User'} className="w-7 h-7 rounded-full object-cover" referrerPolicy="no-referrer" />
  }
  const initials = (displayName ?? 'U').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div className="w-7 h-7 rounded-full bg-violet-600 flex items-center justify-center text-white text-xs font-bold">
      {initials}
    </div>
  )
}

export default function Navigation() {
  const { pathname } = useLocation()
  const { user, loading, signIn, signOut } = useAuth()
  const { isAdmin } = useSubscription()
  const [open, setOpen] = useState(false)
  const baseLinks = user ? [...PUBLIC_LINKS, ...AUTH_LINKS] : PUBLIC_LINKS
  const visibleLinks = isAdmin ? [...baseLinks, { to: '/admin', label: 'Admin' }] : baseLinks

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 px-4 md:px-8 pb-4 safe-top">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link
            to="/"
            onClick={() => setOpen(false)}
            className="glass rounded-xl px-4 py-2 flex items-center gap-2 group"
          >
            <Zap size={18} className="text-violet-600 dark:text-violet-400 group-hover:text-violet-500 dark:group-hover:text-violet-300 transition-colors" fill="currentColor" />
            <span className="gradient-text font-bold text-lg tracking-tight">ECALT</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex glass rounded-xl px-2 py-1.5 items-center gap-1">
            {visibleLinks.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
                  pathname === to
                    ? 'bg-violet-50 text-violet-700 dark:bg-violet-600/20 dark:text-violet-300'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800/50'
                )}
              >
                {label}
              </Link>
            ))}
            <div className="w-px h-4 bg-slate-200 dark:bg-slate-700 mx-1" />
            <ThemeToggle />
            <div className="w-px h-4 bg-slate-200 dark:bg-slate-700 mx-1" />

            {loading ? (
              <div className="w-20 h-7 rounded-lg bg-slate-200/60 dark:bg-slate-700/40 animate-pulse" />
            ) : user ? (
              <>
                <Link
                  to="/profile"
                  className={clsx(
                    'flex items-center gap-2 px-2 py-1 rounded-lg transition-all',
                    pathname === '/profile'
                      ? 'bg-violet-50 dark:bg-violet-600/20'
                      : 'hover:bg-slate-100 dark:hover:bg-slate-800/50'
                  )}
                >
                  <UserAvatar photoURL={user.photoURL} displayName={user.displayName} />
                  <span className={clsx(
                    'text-sm font-medium max-w-[120px] truncate',
                    pathname === '/profile'
                      ? 'text-violet-700 dark:text-violet-300'
                      : 'text-slate-600 dark:text-slate-400'
                  )}>
                    {user.displayName?.split(' ')[0] ?? user.email}
                  </span>
                </Link>
                <button
                  onClick={signOut}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-slate-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 dark:hover:text-rose-400 transition-all ml-1"
                >
                  <LogOut size={13} />
                  Sign out
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={signIn}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
                >
                  Sign In
                </button>
                <button
                  onClick={signIn}
                  className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-colors ml-1"
                >
                  Start Free
                </button>
              </>
            )}
          </div>

          {/* Mobile controls */}
          <div className="flex md:hidden items-center gap-2">
            <ThemeToggle />
            <button
              onClick={() => setOpen(o => !o)}
              aria-label="Toggle menu"
              className="glass p-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
            >
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile dropdown menu */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
          <div
            className="absolute top-[68px] left-4 right-4 glass rounded-2xl p-3 shadow-xl border border-white/20 dark:border-slate-700/50"
            onClick={e => e.stopPropagation()}
          >
            {/* User info when signed in */}
            {user && (
              <div className="flex items-center gap-3 px-4 py-3 mb-1 border-b border-slate-200/80 dark:border-slate-700/50">
                <UserAvatar photoURL={user.photoURL} displayName={user.displayName} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{user.displayName}</p>
                  <p className="text-xs text-slate-400 truncate">{user.email}</p>
                </div>
              </div>
            )}

            <div className="space-y-0.5">
              {visibleLinks.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setOpen(false)}
                  className={clsx(
                    'flex items-center px-4 py-3 rounded-xl text-sm font-medium transition-all',
                    pathname === to
                      ? 'bg-violet-50 text-violet-700 dark:bg-violet-600/20 dark:text-violet-300'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800/50'
                  )}
                >
                  {label}
                </Link>
              ))}
            </div>

            {!loading && (
              <div className="border-t border-slate-200/80 dark:border-slate-700/50 mt-2 pt-2 space-y-0.5">
                {user ? (
                  <button
                    onClick={() => { signOut(); setOpen(false) }}
                    className="flex items-center gap-2 w-full px-4 py-3 rounded-xl text-sm font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-900/20 transition-colors"
                  >
                    <LogOut size={14} />
                    Sign out
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => { signIn(); setOpen(false) }}
                      className="flex items-center px-4 py-3 rounded-xl text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/50 transition-colors w-full"
                    >
                      Sign In
                    </button>
                    <button
                      onClick={() => { signIn(); setOpen(false) }}
                      className="flex items-center justify-center px-4 py-3 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-colors w-full"
                    >
                      Start Free
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
