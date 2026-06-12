import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Brain, Shield, Eye, MessageSquare, Linkedin } from 'lucide-react'

const FOUNDER_NAME = 'Biswambar Pradhan'
const LINKEDIN_URL = 'https://www.linkedin.com/company/ecalt/'
const WHATSAPP_URL = 'https://wa.me/919152893738'

const FAQ = [
  {
    q: 'Is ECALT safe for my child to use unsupervised?',
    a: 'ECALT is designed for independent use. Our AI is configured to stay on educational topics and will not engage with requests for harmful, adult, or off-topic content. That said, we recommend parents review their child\'s Passport page periodically to see what topics they\'re exploring.',
  },
  {
    q: 'What subjects does ECALT cover?',
    a: 'Any topic a curious learner might ask about — science, history, maths, coding, music, geography, philosophy, and more. ECALT follows the learner\'s curiosity rather than a fixed curriculum.',
  },
  {
    q: 'Does my child talk to a real person?',
    a: 'No. All conversations are with an AI (powered by Claude by Anthropic). No human tutor is involved. This is clearly disclosed in the app.',
  },
  {
    q: 'Can ECALT replace school or tutoring?',
    a: 'No, and we\'d never claim that. ECALT is a curiosity companion — it deepens understanding and builds a love of learning alongside school, not instead of it.',
  },
  {
    q: 'What happens to my child\'s data?',
    a: 'We collect only what\'s needed to run the service. We never sell data, show ads, or profile your child for marketing. Full details are in our Privacy Policy.',
  },
  {
    q: 'Can I delete my child\'s account?',
    a: 'Yes, at any time. Sign in, go to Profile → Privacy & Data, and choose Delete Account. All data is purged within 30 days.',
  },
]

function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <div className="glass-card rounded-2xl p-5">
      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">{q}</p>
      <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{a}</p>
    </div>
  )
}

export default function Parents() {
  return (
    <>
      <PageMeta
        title="For Parents — ECALT"
        description="How ECALT works, what the AI will and won't do, what parents can see and control, and who built it."
      />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 pt-24 pb-20">
        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="mb-10">
            <span className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">For Parents</span>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mt-2 mb-3">
              Your child's curiosity deserves better than a search engine.
            </h1>
            <p className="text-base text-slate-600 dark:text-slate-300 leading-relaxed">
              ECALT gives curious learners a patient AI guide that turns any question into a structured
              learning journey — with no ads, no rabbit holes, and no data sold.
            </p>
          </div>

          {/* How it works */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <Brain size={18} className="text-violet-500" /> How ECALT works
            </h2>
            <div className="space-y-3">
              {[
                { step: '1', title: 'Your child asks a question', body: 'Anything — "How do black holes work?" or "I want to build a robot." No topic list, no rigid syllabus.' },
                { step: '2', title: 'ECALT builds a learning journey', body: 'The AI creates a multi-step path: concept → explanation → examples → quiz → next level. Each step is written at the right depth for the learner.' },
                { step: '3', title: 'They explore at their own pace', body: 'Journeys are saved. Your child can pause, revisit, and deepen their understanding whenever curiosity strikes.' },
                { step: '4', title: 'Their Passport grows', body: 'Every topic explored becomes a node in their personal Knowledge Passport — a visual map of everything they\'ve learned.' },
              ].map(({ step, title, body }) => (
                <div key={step} className="glass-card rounded-2xl p-5 flex gap-4">
                  <div className="w-7 h-7 rounded-full bg-violet-100 dark:bg-violet-900/40 flex items-center justify-center shrink-0">
                    <span className="text-xs font-bold text-violet-600 dark:text-violet-400">{step}</span>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">{title}</p>
                    <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{body}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* What AI will / won't do */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <MessageSquare size={18} className="text-violet-500" /> What the AI will and won't do
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="glass-card rounded-2xl p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 mb-3">Will do</p>
                <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-2">
                  {[
                    'Explain complex ideas simply',
                    'Adapt depth to the learner\'s level',
                    'Generate quizzes and examples',
                    'Suggest related topics to explore',
                    'Stay encouraging and patient',
                  ].map(i => <li key={i} className="flex gap-2"><span className="text-emerald-500">✓</span>{i}</li>)}
                </ul>
              </div>
              <div className="glass-card rounded-2xl p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400 mb-3">Won't do</p>
                <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-2">
                  {[
                    'Give medical or legal advice',
                    'Access the internet in real time',
                    'Chat off-topic or socially',
                    'Remember between sessions unless saved',
                    'Pretend to be a human',
                  ].map(i => <li key={i} className="flex gap-2"><span className="text-rose-500">✗</span>{i}</li>)}
                </ul>
              </div>
            </div>
          </section>

          {/* What parents see and control */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <Eye size={18} className="text-violet-500" /> What you can see and control
            </h2>
            <div className="glass-card rounded-2xl p-5 space-y-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Passport view:</span>{' '}
                Every topic your child has explored is visible in their Knowledge Passport. You can sign in with
                their account to review it any time.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Data download:</span>{' '}
                From Profile → Privacy &amp; Data, you can download a full JSON export of everything stored —
                journeys, progress, questions asked.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Account deletion:</span>{' '}
                You can delete the account and all data at any time, permanently.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Consent withdrawal:</span>{' '}
                Email <a href="mailto:support@ecalt.com" className="text-violet-600 dark:text-violet-400 underline">support@ecalt.com</a> at
                any time to revoke consent and trigger immediate deletion.
              </p>
            </div>
          </section>

          {/* Safety */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <Shield size={18} className="text-violet-500" /> Safety approach
            </h2>
            <div className="glass-card rounded-2xl p-5 space-y-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              <p>ECALT's AI is configured with strict content guardrails at the model level — it will not generate harmful, adult, or abusive content regardless of what is asked.</p>
              <p>We require parental consent for every learner under 18 before any data is stored. The account stays inactive until a parent clicks the confirmation link.</p>
              <p>We never sell data. We show no ads. We don't profile your child for marketing — ours or anyone else's.</p>
              <p>Our payment partner is Razorpay (India) or Stripe (international) — both are regulated, PCI-DSS compliant processors. We never see or store your card number.</p>
            </div>
          </section>

          {/* FAQ */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">Frequently asked questions</h2>
            <div className="space-y-3">
              {FAQ.map(({ q, a }) => <FaqItem key={q} q={q} a={a} />)}
            </div>
          </section>

          {/* Founder note */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">A note from the founder</h2>
            <div className="glass-card rounded-2xl p-6 flex flex-col sm:flex-row gap-5">
              <div className="w-14 h-14 rounded-full bg-violet-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
                BP
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-0.5">{FOUNDER_NAME}</p>
                <p className="text-xs text-slate-400 mb-3">Founder, ECALT</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                  I built ECALT because I believe every curious child deserves a patient guide — not a paywall,
                  not an algorithm optimising for engagement, and not a search engine that dumps ten links and
                  walks away. ECALT exists to make deep learning feel like an adventure. Every design decision
                  here — from the consent flow to the data policy — is one I'd be comfortable explaining to
                  a parent at the school gate.
                </p>
                <div className="flex flex-wrap gap-3">
                  <a
                    href={LINKEDIN_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#0077b5] text-white hover:bg-[#006399] transition-colors"
                  >
                    <Linkedin size={13} /> Connect on LinkedIn
                  </a>
                  <a
                    href={WHATSAPP_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#25D366] text-white hover:bg-[#20bc59] transition-colors"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                    Chat on WhatsApp
                  </a>
                </div>
              </div>
            </div>
          </section>

          {/* CTA */}
          <div className="glass-card rounded-2xl p-6 text-center">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">Still have questions?</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">We reply to every parent email within 48 hours.</p>
            <a
              href="/contact"
              className="inline-block px-6 py-2.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-colors"
            >
              Get in touch
            </a>
          </div>

        </div>
      </div>
    </>
  )
}
