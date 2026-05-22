import { useEffect, useMemo, useState } from 'react'
import { Loader2, MessageCircle, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { getUserProfile, optInWhatsApp } from '../../lib/api'

const DISMISS_KEY = 'ecalt_wa_nudge_dismissed'
const SUPPRESS_MS = 30 * 24 * 60 * 60 * 1000 // 30 days
const TRIGGER_MESSAGES = 3

const COUNTRY_CODES = [
  { code: '+91',  label: 'IN +91' },
  { code: '+1',   label: 'US +1'  },
  { code: '+44',  label: 'UK +44' },
  { code: '+61',  label: 'AU +61' },
  { code: '+65',  label: 'SG +65' },
  { code: '+971', label: 'AE +971' },
  { code: '+49',  label: 'DE +49' },
]

function guessCode(): string {
  try {
    const region = new Intl.Locale(navigator.language).maximize().region
    const map: Record<string, string> = { IN: '+91', US: '+1', GB: '+44', AU: '+61', SG: '+65', AE: '+971', DE: '+49' }
    return (region && map[region]) || '+91'
  } catch { return '+91' }
}

export default function WhatsAppNudgeBanner({ messageCount }: { messageCount: number }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [eligible, setEligible] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [code, setCode] = useState(guessCode())
  const [digits, setDigits] = useState('')
  const [saving, setSaving] = useState(false)

  const localSuppressed = useMemo(() => {
    try {
      const ts = Number(localStorage.getItem(DISMISS_KEY) || 0)
      return ts > 0 && Date.now() - ts < SUPPRESS_MS
    } catch { return false }
  }, [])

  useEffect(() => {
    if (localSuppressed) return
    let cancelled = false
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        const profile = await getUserProfile(token)
        if (cancelled) return
        // Show only to users who have not opted in.
        if (!profile.whatsapp_opted_in) setEligible(true)
      } catch { /* silent */ }
    })()
    return () => { cancelled = true }
  }, [getToken, localSuppressed])

  const visible =
    eligible &&
    !dismissed &&
    !localSuppressed &&
    messageCount >= TRIGGER_MESSAGES

  if (!visible) return null

  const handleDismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())) } catch { /* ignore */ }
    setDismissed(true)
  }

  const handleEnable = async () => {
    const d = digits.replace(/\D/g, '')
    if (d.length < 7 || d.length > 15) {
      addToast('Enter a valid phone number', 'error')
      return
    }
    const token = await getToken()
    if (!token) return
    setSaving(true)
    try {
      await optInWhatsApp(`${code}${d}`, token)
      addToast('WhatsApp notifications enabled ✓')
      setDismissed(true)
    } catch {
      addToast("Couldn't enable WhatsApp", 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="shrink-0 mx-3 mb-3 rounded-xl border border-violet-200 dark:border-violet-500/30 bg-violet-50/80 dark:bg-violet-500/10 backdrop-blur px-3 py-2.5 flex items-center gap-2 text-sm">
      <MessageCircle size={16} className="text-violet-600 dark:text-violet-300 shrink-0" />
      <span className="hidden sm:inline text-slate-700 dark:text-slate-200 mr-1">
        Get a nudge when we find a connection in your topics
      </span>
      <div className={clsx(
        'flex items-stretch rounded-lg border border-violet-200 dark:border-violet-500/40 bg-white dark:bg-slate-900/60 overflow-hidden flex-1 min-w-0 max-w-xs',
      )}>
        <select
          value={code}
          onChange={e => setCode(e.target.value)}
          className="bg-transparent px-2 text-xs text-slate-700 dark:text-slate-300 border-r border-violet-200 dark:border-violet-500/40 focus:outline-none"
        >
          {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
        </select>
        <input
          type="tel"
          inputMode="numeric"
          placeholder="phone number"
          value={digits}
          onChange={e => setDigits(e.target.value)}
          className="flex-1 min-w-0 bg-transparent px-2 py-1 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
        />
      </div>
      <button
        onClick={handleEnable}
        disabled={saving}
        className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white flex items-center gap-1"
      >
        {saving && <Loader2 size={12} className="animate-spin" />}
        Turn on WhatsApp
      </button>
      <button
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="shrink-0 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
      >
        <X size={14} />
      </button>
    </div>
  )
}
