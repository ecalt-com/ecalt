import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Brain, Shield, Eye, MessageSquare } from 'lucide-react'


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
