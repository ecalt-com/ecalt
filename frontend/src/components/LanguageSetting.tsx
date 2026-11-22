import { useEffect, useState } from 'react'
import { Languages, Loader2 } from 'lucide-react'
import { getUserProfile, setPreferredLanguage } from '../lib/api'
import { useAuth } from '../lib/AuthContext'

const OPTIONS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी (Hindi)' },
]

// Profile → "Language" (F2.2): what new journeys, quizzes and chat are written in.
export default function LanguageSetting() {
  const { getToken } = useAuth()
  const [value, setValue] = useState('en')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    getToken().then(t => t ? getUserProfile(t) : null).then(p => { if (p?.preferred_language) setValue(p.preferred_language) }).catch(() => {})
  }, [getToken])

  const change = async (code: string) => {
    const previous = value
    setValue(code); setBusy(true); setMessage(null)
    try {
      const token = await getToken()
      if (!token) return
      await setPreferredLanguage(code, token)
      setMessage({ tone: 'ok', text: code === 'en' ? 'New journeys will be in English.' : 'New journeys and chat will be written in Hindi. Journeys you already have stay as they are.' })
    } catch (e) {
      setValue(previous)
      const detail = (e as { detail?: { message?: string } | string })?.detail
      setMessage({ tone: 'error', text: (typeof detail === 'object' && detail?.message) || "Couldn't change the language. Please try again." })
    } finally { setBusy(false) }
  }

  return (
    <div className="glass-card rounded-2xl p-5 mb-5" data-testid="language-setting">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <Languages size={14} /> Language
      </h2>
      <div className="flex items-center gap-3">
        <select
          value={value}
          onChange={e => change(e.target.value)}
          disabled={busy}
          aria-label="Language for new journeys and chat"
          className="flex-1 px-3 py-2.5 rounded-xl text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-violet-400"
        >
          {OPTIONS.map(o => <option key={o.code} value={o.code}>{o.label}</option>)}
        </select>
        {busy && <Loader2 size={14} className="animate-spin text-violet-500" />}
      </div>
      {message && (
        <p role="status" className={`text-xs mt-2 ${message.tone === 'ok' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
          {message.text}
        </p>
      )}
    </div>
  )
}
