import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Loader2, MessageCircle } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../lib/AuthContext'
import { completeOnboarding, optInWhatsApp, saveNotificationPrefs } from '../lib/api'

const TOPICS = [
  { emoji: '🧬', label: 'Biology' },
  { emoji: '⚛️', label: 'Physics' },
  { emoji: '🤖', label: 'AI & Tech' },
  { emoji: '🧮', label: 'Math' },
  { emoji: '🚀', label: 'Space' },
  { emoji: '💰', label: 'Finance' },
  { emoji: '🎵', label: 'Music' },
  { emoji: '🌍', label: 'Climate' },
  { emoji: '🏛️', label: 'History' },
  { emoji: '🧠', label: 'Psychology' },
  { emoji: '⚙️', label: 'Engineering' },
  { emoji: '🎨', label: 'Arts' },
]

// Minimal country-code list — covers the largest WhatsApp markets.
// Default uses browser locale where possible.
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

function guessDefaultCode(): string {
  try {
    const region = new Intl.Locale(navigator.language).maximize().region
    const map: Record<string, string> = {
      IN: '+91', US: '+1', GB: '+44', AU: '+61', SG: '+65', AE: '+971',
      DE: '+49', FR: '+33', JP: '+81', CN: '+86', BR: '+55', ZA: '+27',
    }
    return (region && map[region]) || '+91'
  } catch {
    return '+91'
  }
}

export default function OnboardingModal() {
  const navigate = useNavigate()
  const { getToken, dismissOnboarding } = useAuth()
  const [step, setStep] = useState<1 | 2>(1)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)

  const [countryCode, setCountryCode] = useState<string>(guessDefaultCode())
  const [phoneDigits, setPhoneDigits] = useState('')
  const [phoneError, setPhoneError] = useState<string | null>(null)

  const toggle = (label: string) =>
    setSelected(prev => {
      const next = new Set(prev)
      next.has(label) ? next.delete(label) : next.add(label)
      return next
    })

  const finish = async (opts: { phone?: string; declined?: boolean }) => {
    setSaving(true)
    try {
      const token = await getToken()
      if (token) {
        const topics = Array.from(selected).map(t => t.toLowerCase())
        const calls: Promise<unknown>[] = [
          completeOnboarding(token),
        ]
        if (selected.size > 0) {
          calls.push(
            fetch('/api/v1/users/me/interests', {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ topics }),
            }),
          )
        }
        if (opts.phone) {
          calls.push(optInWhatsApp(opts.phone, token))
        } else if (opts.declined) {
          calls.push(saveNotificationPrefs({ whatsapp_declined_onboarding: true }, token))
        }
        await Promise.allSettled(calls)
      }
    } catch { /* non-critical */ } finally {
      dismissOnboarding()
      navigate('/')
    }
  }

  const handleTopicsContinue = () => setStep(2)
  const handleTopicsSkip   = () => finish({ declined: true })

  const handleWhatsAppEnable = () => {
    const digits = phoneDigits.replace(/\D/g, '')
    if (digits.length < 7 || digits.length > 15) {
      setPhoneError('Enter a valid phone number')
      return
    }
    setPhoneError(null)
    finish({ phone: `${countryCode}${digits}` })
  }

  const handleWhatsAppSkip = () => finish({ declined: true })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm modal-overlay">
      <div className="animate-celebration glass-card rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl">
        {step === 1 ? (
          <>
            <div className="text-center mb-6">
              <div className="text-4xl mb-3">✦</div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">What sparks your curiosity?</h2>
              <p className="text-sm text-slate-500">Pick the topics you'd like to explore — we'll tailor your journeys.</p>
            </div>

            <div className="grid grid-cols-2 min-[400px]:grid-cols-3 gap-2 mb-6">
              {TOPICS.map(({ emoji, label }) => (
                <button
                  key={label}
                  onClick={() => toggle(label)}
                  className={clsx(
                    'flex flex-col items-center gap-1 py-3 px-2 rounded-xl border text-xs font-medium transition-all duration-150',
                    selected.has(label)
                      ? 'border-violet-400 bg-violet-50 text-violet-700 dark:border-violet-500/60 dark:bg-violet-500/15 dark:text-violet-300'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-violet-300 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400 dark:hover:border-violet-500/40'
                  )}
                >
                  <span className="text-xl leading-none">{emoji}</span>
                  {label}
                </button>
              ))}
            </div>

            <button
              onClick={handleTopicsContinue}
              disabled={saving}
              className="w-full btn-primary flex items-center justify-center gap-2"
            >
              Continue <ArrowRight size={14} />
            </button>

            <button
              onClick={handleTopicsSkip}
              disabled={saving}
              className="w-full mt-2 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-1 transition-colors"
            >
              Skip for now
            </button>

            <p className="mt-3 text-xs text-center text-slate-400 dark:text-slate-500">
              By continuing you agree to our{' '}
              <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600 dark:hover:text-slate-400">Terms of Service</a>{' '}
              and{' '}
              <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600 dark:hover:text-slate-400">Privacy Policy</a>.
            </p>
          </>
        ) : (
          <>
            <div className="text-center mb-6">
              <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                <MessageCircle size={22} className="text-violet-600 dark:text-violet-300" />
              </div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">Get updates that matter to you</h2>
              <p className="text-sm text-slate-500">We'll notify you on WhatsApp when something connects to your learning.</p>
            </div>

            <div className="mb-3">
              <div className={clsx(
                'flex items-stretch rounded-xl border bg-white dark:bg-slate-800/50 overflow-hidden',
                phoneError ? 'border-rose-400' : 'border-slate-200 dark:border-slate-700 focus-within:border-violet-400'
              )}>
                <select
                  value={countryCode}
                  onChange={e => setCountryCode(e.target.value)}
                  className="bg-transparent px-3 text-sm text-slate-700 dark:text-slate-300 border-r border-slate-200 dark:border-slate-700 focus:outline-none"
                >
                  {COUNTRY_CODES.map(c => (
                    <option key={c.code} value={c.code}>{c.label}</option>
                  ))}
                </select>
                <input
                  type="tel"
                  inputMode="numeric"
                  placeholder="98765 43210"
                  value={phoneDigits}
                  onChange={e => { setPhoneDigits(e.target.value); if (phoneError) setPhoneError(null) }}
                  className="flex-1 bg-transparent px-3 py-2.5 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
                />
              </div>
              {phoneError && (
                <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">{phoneError}</p>
              )}
            </div>

            <button
              onClick={handleWhatsAppEnable}
              disabled={saving}
              className="w-full btn-primary flex items-center justify-center gap-2"
            >
              {saving
                ? <><Loader2 size={14} className="animate-spin" />Saving…</>
                : <>Enable WhatsApp notifications</>}
            </button>

            <button
              onClick={handleWhatsAppSkip}
              disabled={saving}
              className="w-full mt-2 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-1 transition-colors"
            >
              Skip for now
            </button>

            <p className="mt-4 text-xs leading-relaxed text-center text-slate-400 dark:text-slate-500">
              By continuing you agree to receive learning updates on WhatsApp.
              Reply STOP to opt out anytime, or change this in settings.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
