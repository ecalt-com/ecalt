import { useState } from 'react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Mail, MapPin, Send, Loader2, Linkedin } from 'lucide-react'

const SUPPORT_EMAIL = 'support@ecalt.com'
const WHATSAPP_URL = 'https://wa.me/919152893738'
const WHATSAPP_DISPLAY = '+91 91528 93738'
const LINKEDIN_URL = 'https://www.linkedin.com/company/ecalt/'
const OFFICE_ADDRESS = [
  'AUB Edulearn, WeGrow Office',
  'Plot No. 88, 8th Floor, Proxima',
  'Arunachal Bhavan, 19, Sector 30A',
  'Vashi, Navi Mumbai, Maharashtra – 400703',
]

type SenderType = 'parent' | 'school' | 'other'

export default function Contact() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [type, setType] = useState<SenderType>('parent')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  const valid = name.trim() && email.trim() && message.trim()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setSending(true)

    const label = type === 'parent' ? 'Parent' : type === 'school' ? 'School / Educator' : 'Other'
    const subject = encodeURIComponent(`[ECALT Contact] ${label} – ${name}`)
    const body = encodeURIComponent(
      `Name: ${name}\nEmail: ${email}\nType: ${label}\n\n${message}`
    )
    window.location.href = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`

    setTimeout(() => {
      setSending(false)
      setSent(true)
    }, 800)
  }

  return (
    <>
      <PageMeta
        title="Contact — ECALT"
        description="Get in touch with ECALT. Email, WhatsApp, or send a message — we reply within 48 hours."
      />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 pt-24 pb-20">
        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="mb-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">Contact</span>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mt-2 mb-2">
              We reply within 48 hours.
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              A real human reads every message. No bots, no auto-replies.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            {/* Email */}
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="glass-card rounded-2xl p-4 flex flex-col gap-2 hover:ring-1 hover:ring-violet-400/40 transition-all"
            >
              <Mail size={18} className="text-violet-500" />
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">Email us</p>
              <p className="text-xs text-violet-600 dark:text-violet-400 break-all">{SUPPORT_EMAIL}</p>
            </a>

            {/* WhatsApp */}
            <a
              href={WHATSAPP_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="glass-card rounded-2xl p-4 flex flex-col gap-2 hover:ring-1 hover:ring-emerald-400/40 transition-all"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className="text-[#25D366]"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">WhatsApp</p>
              <p className="text-xs text-[#25D366]">{WHATSAPP_DISPLAY}</p>
            </a>

            {/* LinkedIn */}
            <a
              href={LINKEDIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="glass-card rounded-2xl p-4 flex flex-col gap-2 hover:ring-1 hover:ring-[#0077b5]/40 transition-all"
            >
              <Linkedin size={18} className="text-[#0077b5]" />
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">LinkedIn</p>
              <p className="text-xs text-[#0077b5]">ECALT Company Page</p>
            </a>
          </div>

          {/* Form */}
          <div className="glass-card rounded-2xl p-6 mb-8">
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-5">Send us a message</h2>

            {sent ? (
              <div className="text-center py-8">
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-3">
                  <Send size={20} className="text-emerald-600 dark:text-emerald-400" />
                </div>
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">Your email client is open</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Hit send in your email app and we'll get back to you within 48 hours.
                </p>
                <button
                  onClick={() => { setSent(false); setName(''); setEmail(''); setMessage('') }}
                  className="mt-4 text-xs text-violet-600 dark:text-violet-400 hover:underline"
                >
                  Send another message
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                      Name <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      required
                      placeholder="Your name"
                      className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                      Email <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      required
                      placeholder="you@example.com"
                      className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">I am a</label>
                  <div className="flex gap-2 flex-wrap">
                    {(['parent', 'school', 'other'] as SenderType[]).map(t => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setType(t)}
                        className={`px-4 py-2 rounded-xl text-xs font-medium border transition-all ${
                          type === t
                            ? 'bg-violet-600 text-white border-violet-600'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-violet-400 dark:hover:border-violet-500'
                        }`}
                      >
                        {t === 'parent' ? 'Parent / Guardian' : t === 'school' ? 'School / Educator' : 'Other'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                    Message <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    required
                    rows={5}
                    placeholder="How can we help?"
                    className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 transition-colors resize-none"
                  />
                </div>

                <button
                  type="submit"
                  disabled={!valid || sending}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sending
                    ? <><Loader2 size={14} className="animate-spin" /> Opening email…</>
                    : <><Send size={14} /> Send message</>}
                </button>
              </form>
            )}
          </div>

          {/* Office address */}
          <div className="glass-card rounded-2xl p-5 flex gap-3">
            <MapPin size={16} className="text-violet-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Office address</p>
              {OFFICE_ADDRESS.map(line => (
                <p key={line} className="text-xs text-slate-500 dark:text-slate-400">{line}</p>
              ))}
            </div>
          </div>

        </div>
      </div>
    </>
  )
}
