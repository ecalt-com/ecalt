// A small chip naming a journey's language when it isn't English (F2.2).
const NAMES: Record<string, string> = { hi: 'हिन्दी' }

export const languageName = (code?: string | null) => (code && NAMES[code]) || null

export default function LanguageBadge({ language, className = '' }: { language?: string | null; className?: string }) {
  const name = languageName(language)
  if (!name) return null
  return (
    <span lang={language ?? undefined} data-testid="language-badge"
      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border border-emerald-300/60 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 ${className}`}>
      {name}
    </span>
  )
}
