import { Link } from 'react-router-dom'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Brain, Shield, Eye, MessageSquare, Users, SlidersHorizontal } from 'lucide-react'


const FAQ = [
  {
    q: 'Is ECALT safe for my child to use unsupervised?',
    a: 'ECALT is designed for independent use. Our AI is configured to stay on educational topics and will not engage with requests for harmful, adult, or off-topic content. Your Family dashboard shows you what topics your child explores, their progress, and their quiz scores — so you can check in any time without looking over their shoulder.',
  },
  {
    q: 'What subjects does ECALT cover?',
    a: 'Any topic a curious learner might ask about — science, history, maths, coding, music, geography, philosophy, and more. ECALT follows the learner\'s curiosity rather than a fixed curriculum. You can also set a content level for your child from the dashboard.',
  },
  {
    q: 'Does my child talk to a real person?',
    a: 'No. All conversations are with an AI (powered by Claude by Anthropic). No human tutor is involved. This is clearly disclosed in the app, and you can turn AI chat off entirely from your Family dashboard.',
  },
  {
    q: 'Can ECALT replace school or tutoring?',
    a: 'No, and we\'d never claim that. ECALT is a curiosity companion — it deepens understanding and builds a love of learning alongside school, not instead of it.',
  },
  {
    q: 'What happens to my child\'s data?',
    a: 'We collect only what\'s needed to run the service. We never sell data, show ads, or profile your child for marketing. You can export everything we store about your child from the Family dashboard at any time. Full details are in our Privacy Policy.',
  },
  {
    q: 'Can I delete my child\'s account?',
    a: 'Yes, at any time, from your Family dashboard: open your child\'s page and choose Delete in the danger zone. You can also withdraw consent, which pauses the account immediately and deletes it after a 14-day grace window in case you change your mind.',
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
        description="How ECALT works, the Family dashboard, what parents can see and control, and how consent works."
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
              learning journey — with no ads, no rabbit holes, and no data sold. And you get a Family
              dashboard that keeps you in the loop.
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
                { step: '4', title: 'You stay in the loop', body: 'Your Family dashboard shows their progress, streaks, and topics — plus a weekly digest email every Sunday if you want it.' },
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

          {/* Getting your child an account */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <Users size={18} className="text-violet-500" /> Getting your child an account
            </h2>
            <div className="space-y-3">
              <div className="glass-card rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">You create it (recommended)</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  Sign in with Google, open your <Link to="/family" className="text-violet-600 dark:text-violet-400 underline">Family dashboard</Link>,
                  and add your child: their name, date of birth, a consent review, and a login you set for them.
                  They sign in with that email and password at{' '}
                  <Link to="/kids-login" className="text-violet-600 dark:text-violet-400 underline">ecalt.com/kids-login</Link> —
                  their own account, linked to yours.
                </p>
              </div>
              <div className="glass-card rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">They sign up, you approve</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  Teens (13–17) can sign up themselves with Google. Their account stays inactive until we
                  email you and you review and approve it. Approving while signed in also links them to your
                  Family dashboard.
                </p>
              </div>
              <div className="glass-card rounded-2xl p-5">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-1">Identity verification, where required</p>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  For younger children, and for all minors in India, regulations require a stronger signal
                  that a real adult consented. We use a quick card check (₹0/€0 — nothing is charged, no card
                  stored). Elsewhere, email approval plus a follow-up notice is enough.
                </p>
              </div>
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

          {/* What parents see */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <Eye size={18} className="text-violet-500" /> What you can see
            </h2>
            <div className="glass-card rounded-2xl p-5 space-y-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              <p>From your Family dashboard, for each linked child you can see:</p>
              <ul className="list-disc list-inside space-y-1 pl-1">
                <li>The topics they explore and the journeys they create</li>
                <li>Their progress and streaks</li>
                <li>Their quiz scores</li>
                <li>The titles of their AI conversations and how many messages they contain</li>
                <li>Full conversation transcripts <span className="text-slate-400">— only if you turn that on, and your child is told</span></li>
              </ul>
              <p>
                Your child sees exactly the same list on their own Profile page. We think oversight works
                best when it isn't a secret — the same approach Google Family Link takes.
              </p>
            </div>
          </section>

          {/* What parents control */}
          <section className="mb-10">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
              <SlidersHorizontal size={18} className="text-violet-500" /> What you can control
            </h2>
            <div className="glass-card rounded-2xl p-5 space-y-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Pause:</span>{' '}
                Suspend the account temporarily — exam week, screen-time reset, whatever you need.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">AI chat:</span>{' '}
                Turn the conversational tutor off entirely; journeys and quizzes keep working.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Content level:</span>{' '}
                Pin the depth of generated content to kids, teens, or adult level.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Data export:</span>{' '}
                Download everything we store about your child as a JSON file, any time.
              </p>
              <p>
                <span className="font-medium text-slate-700 dark:text-slate-200">Withdraw consent / delete:</span>{' '}
                Withdrawing consent pauses the account immediately and deletes it after a 14-day grace
                window (you can undo). Deleting removes everything permanently, right away.
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
              <p>We require parental consent for every learner under 18 before the account activates. Consent is reviewed and explicitly granted by you — never assumed from a clicked link alone — and we follow up by email so an unexpected approval can be reported and reversed.</p>
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
