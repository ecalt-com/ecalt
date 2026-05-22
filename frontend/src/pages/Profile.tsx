import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, MessageCircle, Mail, Clock, Globe2 } from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'
import {
  getNotificationPrefs,
  saveNotificationPrefs,
  optInWhatsApp,
  optOutWhatsApp,
  type NotificationPreferences,
} from '../lib/api'

const HOURS = Array.from({ length: 24 }, (_, i) => i)

const COUNTRY_CODES = [
  { code: '+91', label: 'IN +91' },
  { code: '+1',  label: 'US +1'  },
  { code: '+44', label: 'UK +44' },
  { code: '+61', label: 'AU +61' },
  { code: '+65', label: 'SG +65' },
  { code: '+971', label: 'AE +971' },
  { code: '+49', label: 'DE +49' },
  { code: '+33', label: 'FR +33' },
  { code: '+81', label: 'JP +81' },
  { code: '+86', label: 'CN +86' },
  { code: '+55', label: 'BR +55' },
  { code: '+27', label: 'ZA +27' },
]

function splitPhone(p: string | null): { code: string; digits: string } {
  if (!p) return { code: '+91', digits: '' }
  const hit = COUNTRY_CODES.find(c => p.startsWith(c.code))
  if (hit) return { code: hit.code, digits: p.slice(hit.code.length) }
  return { code: '+91', digits: p.replace(/^\+/, '') }
}

function browserTimezone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' }
  catch { return 'UTC' }
}

export default function Profile() {
  const { user, loading: authLoading, getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null)
  const [countryCode, setCountryCode] = useState('+91')
  const [phoneDigits, setPhoneDigits] = useState('')
  const [savingPhone, setSavingPhone] = useState(false)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [phoneError, setPhoneError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        const data = await getNotificationPrefs(token)
        if (cancelled) return
        setPrefs(data)
        const { code, digits } = splitPhone(data.whatsapp_phone)
        setCountryCode(code)
        setPhoneDigits(digits)
      } catch {
        if (!cancelled) addToast('Could not load preferences', 'error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [getToken, addToast])

  const patch = async (body: Parameters<typeof saveNotificationPrefs>[0]) => {
    const token = await getToken()
    if (!token) return
    setSavingPrefs(true)
    try {
      const next = await saveNotificationPrefs(body, token)
      setPrefs(next)
    } catch {
      addToast("Couldn't save preferences", 'error')
    } finally {
      setSavingPrefs(false)
    }
  }

  const handleEnableWhatsApp = async () => {
    const digits = phoneDigits.replace(/\D/g, '')
    if (digits.length < 7 || digits.length > 15) {
      setPhoneError('Enter a valid phone number')
      return
    }
    setPhoneError(null)
    const token = await getToken()
    if (!token) return
    setSavingPhone(true)
    try {
      const next = await optInWhatsApp(`${countryCode}${digits}`, token)
      setPrefs(next)
      addToast(next.whatsapp_opted_in ? 'WhatsApp enabled' : 'Check WhatsApp to confirm')
    } catch {
      addToast('Could not enable WhatsApp', 'error')
    } finally {
      setSavingPhone(false)
    }
  }

  const handleDisableWhatsApp = async () => {
    const token = await getToken()
    if (!token) return
    setSavingPhone(true)
    try {
      const next = await optOutWhatsApp(token)
      setPrefs(next)
      setPhoneDigits('')
      addToast('WhatsApp notifications turned off')
    } catch {
      addToast('Could not disable', 'error')
    } finally {
      setSavingPhone(false)
    }
  }

  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <Loader2 className="animate-spin text-violet-500" />
      </div>
    )
  }

  return (
    <>
      <PageMeta title="Profile" description="Manage your account and notification preferences." />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-6">Profile</h1>

          {/* Account card */}
          <div className="glass-card rounded-2xl p-5 mb-5">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Account</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Display name</dt><dd className="text-slate-800 dark:text-slate-200">{user.displayName || '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Email</dt><dd className="text-slate-800 dark:text-slate-200">{user.email || '—'}</dd></div>
            </dl>
          </div>

          {/* Notifications card */}
          <div className="glass-card rounded-2xl p-5 mb-5">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Notifications</h2>

            {loading || !prefs ? (
              <div className="flex justify-center py-8"><Loader2 className="animate-spin text-violet-500" /></div>
            ) : (
              <div className="space-y-5">
                {/* Email toggle */}
                <ToggleRow
                  icon={<Mail size={16} />}
                  label="Email updates"
                  description="Daily spark and learning reminders"
                  on={prefs.email_enabled}
                  disabled={savingPrefs}
                  onToggle={v => patch({ email_enabled: v })}
                />

                {/* WhatsApp section */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <MessageCircle size={16} className="text-slate-500" />
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">WhatsApp notifications</span>
                    <span className={clsx(
                      'ml-auto text-xs font-medium px-2 py-0.5 rounded-full',
                      prefs.whatsapp_opted_in
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                        : 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400'
                    )}>
                      {prefs.whatsapp_opted_in ? 'ON' : 'OFF'}
                    </span>
                  </div>

                  <div className="flex items-stretch rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 overflow-hidden mb-2">
                    <select
                      value={countryCode}
                      onChange={e => setCountryCode(e.target.value)}
                      className="bg-transparent px-3 text-sm text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-700 focus:outline-none"
                    >
                      {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                    </select>
                    <input
                      type="tel"
                      inputMode="numeric"
                      placeholder="98765 43210"
                      value={phoneDigits}
                      onChange={e => { setPhoneDigits(e.target.value); if (phoneError) setPhoneError(null) }}
                      className="flex-1 bg-transparent px-3 py-2 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
                    />
                  </div>
                  {phoneError && <p className="text-xs text-rose-600 dark:text-rose-400 mb-2">{phoneError}</p>}

                  <div className="flex gap-2">
                    <button
                      onClick={handleEnableWhatsApp}
                      disabled={savingPhone}
                      className="btn-primary text-sm flex items-center gap-2"
                    >
                      {savingPhone && <Loader2 size={14} className="animate-spin" />}
                      {prefs.whatsapp_opted_in ? 'Update number' : 'Save & enable WhatsApp'}
                    </button>
                    {prefs.whatsapp_opted_in && (
                      <button
                        onClick={handleDisableWhatsApp}
                        disabled={savingPhone}
                        className="px-4 py-2 rounded-lg text-sm font-medium text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-900/20 transition-colors"
                      >
                        Disable
                      </button>
                    )}
                  </div>
                </div>

                {/* Quiet hours */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Clock size={16} className="text-slate-500" />
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">Quiet hours</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-slate-500">From</span>
                    <HourSelect
                      value={prefs.quiet_hours_start}
                      onChange={v => patch({ quiet_hours_start: v })}
                      disabled={savingPrefs}
                    />
                    <span className="text-slate-500">to</span>
                    <HourSelect
                      value={prefs.quiet_hours_end}
                      onChange={v => patch({ quiet_hours_end: v })}
                      disabled={savingPrefs}
                    />
                  </div>
                </div>

                {/* Timezone */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Globe2 size={16} className="text-slate-500" />
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">Timezone</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <code className="px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">{prefs.timezone}</code>
                    {prefs.timezone !== browserTimezone() && (
                      <button
                        onClick={() => patch({ timezone: browserTimezone() })}
                        disabled={savingPrefs}
                        className="text-xs text-violet-600 hover:text-violet-500 dark:text-violet-400"
                      >
                        Use browser timezone ({browserTimezone()})
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function ToggleRow({
  icon, label, description, on, disabled, onToggle,
}: {
  icon: React.ReactNode
  label: string
  description?: string
  on: boolean
  disabled?: boolean
  onToggle: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-start gap-2 min-w-0">
        <span className="text-slate-500 mt-0.5">{icon}</span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{label}</p>
          {description && <p className="text-xs text-slate-500">{description}</p>}
        </div>
      </div>
      <button
        onClick={() => onToggle(!on)}
        disabled={disabled}
        role="switch"
        aria-checked={on}
        className={clsx(
          'shrink-0 w-11 h-6 rounded-full relative transition-colors',
          on ? 'bg-violet-600' : 'bg-slate-300 dark:bg-slate-700',
          disabled && 'opacity-50'
        )}
      >
        <span
          className={clsx(
            'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
            on && 'translate-x-5'
          )}
        />
      </button>
    </div>
  )
}

function HourSelect({ value, onChange, disabled }: { value: number; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <select
      value={value}
      onChange={e => onChange(Number(e.target.value))}
      disabled={disabled}
      className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-violet-400"
    >
      {HOURS.map(h => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
    </select>
  )
}
