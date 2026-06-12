import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, MessageCircle, Mail, Clock, Globe2, Download, Trash2, AlertTriangle, X, CreditCard, Ticket } from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'
import { useSubscription } from '../lib/SubscriptionContext'
import { useGeo, isIndia } from '../lib/GeoContext'
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

interface UserProfile {
  consent_given_at?: string | null
  consent_status?: string | null
}

export default function Profile() {
  const { user, loading: authLoading, getToken, signOut } = useAuth()
  const { addToast } = useToast()
  const { plan, couponExtras, loading: subLoading } = useSubscription()
  const { country, loading: geoLoading } = useGeo()
  const navigate = useNavigate()

  // Notification prefs
  const [loading, setLoading] = useState(true)
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null)
  const [countryCode, setCountryCode] = useState('+91')
  const [phoneDigits, setPhoneDigits] = useState('')
  const [savingPhone, setSavingPhone] = useState(false)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [phoneError, setPhoneError] = useState<string | null>(null)

  // Privacy & data
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [exporting, setExporting] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteInput, setDeleteInput] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return
    getToken().then(token => {
      if (!token) return
      fetch('/api/v1/users/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setProfile(data) })
        .catch(() => {})
    })
  }, [user, getToken])

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

  const handleExport = async () => {
    setExporting(true)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/users/me/export', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'ecalt-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* non-critical */ } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (deleteInput !== 'DELETE') return
    setDeleting(true)
    setDeleteError(null)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/users/me', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = typeof body.detail === 'string' ? body.detail : ''
        setDeleteError(detail.includes('already_deleted') ? 'This account has already been deleted.' : 'Something went wrong. Please try again.')
        return
      }
      await signOut()
      navigate('/', { replace: true, state: { message: 'Your account has been deleted.' } })
    } catch {
      setDeleteError('Something went wrong. Please try again.')
    } finally {
      setDeleting(false)
    }
  }

  const consentDate = profile?.consent_given_at
    ? new Date(profile.consent_given_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null
  const accountStatus = profile?.consent_status === 'pending'
    ? 'Under review (parental consent pending)'
    : 'Standard'

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
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5"><dt className="text-slate-500">Display name</dt><dd className="text-slate-800 dark:text-slate-200">{user.displayName || '—'}</dd></div>
              <div className="flex flex-col sm:flex-row sm:justify-between gap-0.5"><dt className="text-slate-500">Email</dt><dd className="text-slate-800 dark:text-slate-200 break-all">{user.email || '—'}</dd></div>
            </dl>
          </div>

          {/* Subscription card */}
          <div className="glass-card rounded-2xl p-5 mb-5">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Subscription</h2>
            {subLoading ? (
              <div className="flex items-center gap-2 text-slate-400 text-xs py-2"><Loader2 size={13} className="animate-spin" /> Loading…</div>
            ) : plan ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <CreditCard size={15} className="text-violet-500" />
                    <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{plan.name}</span>
                    {!plan.is_active && (
                      <span className="text-xs text-rose-500 bg-rose-50 dark:bg-rose-500/10 px-1.5 py-0.5 rounded-full">inactive</span>
                    )}
                  </div>
                  <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                    {plan.base_price_cents === 0
                      ? 'Free'
                      : geoLoading
                        ? '—'
                        : isIndia(country) && plan.base_price_inr_paise
                          ? `₹${(plan.base_price_inr_paise / 100).toFixed(0)}/mo`
                          : `$${(plan.base_price_cents / 100).toFixed(0)}/mo`}
                  </span>
                </div>

                {couponExtras && (couponExtras.extra_credits_cents > 0 || couponExtras.bonus_messages > 0) && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20">
                    <Ticket size={13} className="text-violet-500 shrink-0" />
                    <span className="text-xs text-violet-700 dark:text-violet-300 font-medium">Coupon active —</span>
                    <span className="text-xs text-violet-600 dark:text-violet-400">
                      {[
                        couponExtras.extra_credits_cents > 0 && `+$${(couponExtras.extra_credits_cents / 100).toFixed(2)} credit`,
                        couponExtras.bonus_messages > 0 && `+${couponExtras.bonus_messages} messages`,
                      ].filter(Boolean).join(' · ')}
                    </span>
                  </div>
                )}

                <button
                  onClick={() => navigate('/pricing')}
                  className="text-xs text-violet-600 dark:text-violet-400 hover:underline"
                >
                  {plan.base_price_cents === 0 ? 'Upgrade plan →' : 'Manage plan →'}
                </button>
              </div>
            ) : (
              <p className="text-xs text-slate-400">No active plan.</p>
            )}
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
                  <div className="flex items-center flex-wrap gap-3 text-sm">
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
          {/* Privacy & Data card */}
          <div className="glass-card rounded-2xl p-5 mb-5">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Privacy &amp; Data</h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
              <div className="rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <Download size={15} className="text-violet-500" />
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-100">Download my data</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Get a copy of all your ECALT data as a JSON file.</p>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 min-h-[44px] rounded-lg text-xs font-medium bg-violet-600 hover:bg-violet-500 active:bg-violet-500 text-white transition-all disabled:opacity-60"
                >
                  {exporting ? <><Loader2 size={11} className="animate-spin" /> Exporting…</> : <><Download size={11} /> Download</>}
                </button>
              </div>

              <div className="rounded-xl border border-rose-200 dark:border-rose-900/40 p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <Trash2 size={15} className="text-rose-500" />
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-100">Delete my account</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Permanently remove your account and all associated data.</p>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 min-h-[44px] rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 active:bg-rose-500 text-white transition-all"
                >
                  <Trash2 size={11} /> Delete account
                </button>
              </div>
            </div>

            <div className="border-t border-slate-100 dark:border-slate-700/50 pt-4 space-y-3">
              <div className="text-sm text-slate-700 dark:text-slate-300">
                {consentDate
                  ? <>You agreed to our Terms of Service and Privacy Policy on <span className="font-medium">{consentDate}</span>.</>
                  : <span className="text-slate-400">Consent date not available.</span>
                }
                <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="block mt-1 text-xs text-violet-600 dark:text-violet-400 hover:underline">
                  Update consent preferences →
                </a>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300">
                Account type:{' '}
                <span className={profile?.consent_status === 'pending' ? 'font-medium text-amber-600 dark:text-amber-400' : 'font-medium'}>
                  {profile ? accountStatus : '—'}
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} className="text-rose-500 shrink-0 mt-0.5" />
                <h2 id="delete-modal-title" className="text-base font-bold text-slate-900 dark:text-slate-100">Delete your account?</h2>
              </div>
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteInput(''); setDeleteError(null) }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">This will permanently delete:</p>
            <ul className="text-xs text-slate-600 dark:text-slate-400 mb-4 space-y-1">
              {['Your profile and learning history', 'All journeys and progress', 'All conversations', 'Your Mind Signatures', 'Your subscription (if active)'].map(item => (
                <li key={item} className="flex items-center gap-1.5"><span className="text-rose-400">•</span> {item}</li>
              ))}
            </ul>
            <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-4">This cannot be undone.</p>
            <div className="mb-4">
              <label htmlFor="delete-confirm-input" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                Type DELETE to confirm:
              </label>
              <input
                id="delete-confirm-input"
                type="text"
                value={deleteInput}
                onChange={e => { setDeleteInput(e.target.value); if (deleteError) setDeleteError(null) }}
                autoComplete="off"
                spellCheck={false}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-rose-400"
              />
              {deleteError && <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400" role="alert">{deleteError}</p>}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteInput(''); setDeleteError(null) }}
                className="flex-1 px-4 py-2 min-h-[44px] rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-slate-300 active:border-slate-300 dark:hover:border-slate-600 dark:active:border-slate-600 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteInput !== 'DELETE' || deleting}
                className="flex-1 px-4 py-2 min-h-[44px] rounded-xl text-sm font-medium bg-rose-600 hover:bg-rose-500 active:bg-rose-500 text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {deleting ? <><Loader2 size={14} className="animate-spin" /> Deleting…</> : 'Delete Account'}
              </button>
            </div>
          </div>
        </div>
      )}
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
