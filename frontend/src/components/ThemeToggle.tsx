import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../lib/ThemeContext'

export default function ThemeToggle() {
  const { isDark, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100
                 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800
                 transition-all duration-200"
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  )
}
