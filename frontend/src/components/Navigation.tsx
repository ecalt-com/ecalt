import { Link, useLocation } from 'react-router-dom'
import { Zap } from 'lucide-react'
import clsx from 'clsx'
import ThemeToggle from './ThemeToggle'

const NAV_LINKS = [
  { to: '/explore', label: 'Explore' },
  { to: '/journeys', label: 'Journeys' },
  { to: '/passport', label: 'Passport' },
]

export default function Navigation() {
  const { pathname } = useLocation()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 px-4 md:px-8 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link to="/" className="glass rounded-xl px-4 py-2 flex items-center gap-2 group">
          <Zap size={18} className="text-violet-600 dark:text-violet-400 group-hover:text-violet-500 dark:group-hover:text-violet-300 transition-colors" fill="currentColor" />
          <span className="gradient-text font-bold text-lg tracking-tight">ECALT</span>
        </Link>

        <div className="glass rounded-xl px-2 py-1.5 flex items-center gap-1">
          {NAV_LINKS.map(({ to, label }) => (
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
          <Link to="/sign-in" className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors">
            Sign In
          </Link>
          <Link to="/get-started" className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-colors ml-1">
            Start Free
          </Link>
        </div>
      </div>
    </nav>
  )
}
