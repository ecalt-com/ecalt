import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { FileText } from 'lucide-react'

const LAST_UPDATED = 'July 2026'
const CONTACT_EMAIL = 'support@ecalt.com'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-3">{title}</h2>
      <div className="glass-card rounded-2xl p-5 text-sm text-slate-600 dark:text-slate-300 leading-relaxed space-y-3">
        {children}
      </div>
    </section>
  )
}

export default function Terms() {
  return (
    <>
      <PageMeta
        title="Terms of Service — ECALT"
        description="ECALT terms of service — who holds the account, subscriptions, refunds, AI disclosure, and governing law."
      />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 pt-24 pb-20">
        <div className="max-w-2xl mx-auto">

          <div className="mb-10">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={20} className="text-violet-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">Terms of Service</span>
            </div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2">
              Plain terms, no surprises.
            </h1>
            <p className="text-sm text-slate-400">Last updated: {LAST_UPDATED}</p>
          </div>

          <Section title="1. Who these terms apply to">
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Adult learners (18+):</span>{' '}
              sign up for themselves and hold their own account and billing responsibility.
            </p>
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Teens (13–17):</span>{' '}
              may sign up themselves, but the account stays inactive until a parent or guardian
              reviews and approves it. The approving parent accepts these terms on the teen's behalf.
            </p>
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Children (under 13):</span>{' '}
              cannot sign up themselves. A parent or guardian creates and manages their account from the
              Family dashboard, where available.
            </p>
            <p>
              By approving or creating an account for a learner under 18 you confirm you are their
              parent or legal guardian.
            </p>
          </Section>

          <Section title="2. Parent-managed accounts">
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Credentials:</span>{' '}
              For accounts you create from the Family dashboard, you set and are responsible for your
              child's login email and password — keeping them safe, sharing them only with your child,
              and resetting them if compromised.
            </p>
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Your controls:</span>{' '}
              You may pause the account, disable AI chat, set a content level, export data, withdraw
              consent, or delete the account at any time from the Family dashboard. Withdrawing consent
              pauses the account immediately and deletes it after a 14-day grace window.
            </p>
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Turning 18:</span>{' '}
              When a linked learner turns 18, the family link is removed automatically: parental
              controls and visibility end, and the learner continues as an adult account holder who
              accepts these terms for themselves.
            </p>
            <p>
              <span className="font-medium text-slate-700 dark:text-slate-200">Family plan seats:</span>{' '}
              The Family subscription covers the subscribing parent plus up to 4 linked children
              (5 members total), sharing one usage budget. Children beyond the seat limit, or without a
              linked subscribed parent, use the free tier unless separately subscribed.
            </p>
          </Section>

          <Section title="3. What ECALT is">
            <p>
              ECALT is an AI-powered learning platform. It generates explanations, learning journeys,
              quizzes, and knowledge maps in response to questions. It is an educational tool — not
              a school, not a tutoring service, and not a replacement for qualified teachers.
            </p>
            <p>
              We reserve the right to update, modify, or discontinue features with reasonable notice.
              We will not shut down the service without giving subscribers at least 30 days' notice
              and a pro-rata refund of any unused subscription period.
            </p>
          </Section>

          <Section title="4. Acceptable use">
            <p>You agree not to:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Use ECALT for any purpose other than personal, non-commercial learning.</li>
              <li>Attempt to reverse-engineer, scrape, or extract our AI models or content at scale.</li>
              <li>Share your account credentials with others.</li>
              <li>Use the platform to generate harmful, illegal, or abusive content.</li>
              <li>Resell or sublicense access to ECALT.</li>
            </ul>
            <p>
              We may suspend or terminate accounts that violate these terms without refund.
            </p>
          </Section>

          <Section title="5. Subscriptions and billing">
            <p>
              ECALT offers a free tier and paid subscription plans. Paid plans are billed monthly
              or annually as chosen at checkout.
            </p>
            <p>
              Payments in India are processed by Razorpay. Payments elsewhere are processed by Stripe.
              Your card is charged at the start of each billing period. Subscriptions renew automatically
              unless cancelled before the renewal date.
            </p>
            <p>
              You can cancel at any time from your Profile page. Cancellation takes effect at the end
              of the current billing period — you retain access until then.
            </p>
          </Section>

          <Section title="6. Refund policy">
            <div className="glass rounded-xl p-4 border border-violet-200 dark:border-violet-800/40">
              <p className="font-semibold text-slate-700 dark:text-slate-200 mb-2">First-time subscriber guarantee</p>
              <p>
                If you are a first-time paying subscriber and are not satisfied, email us at{' '}
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>{' '}
                within 7 days of your first charge with the subject line "Refund Request". We will
                process a full refund within 5–7 business days, no questions asked.
              </p>
            </div>
            <p>
              After the 7-day window, or after your second billing cycle, refunds are at our discretion.
              Annual plan holders who cancel mid-year may request a pro-rata refund for unused months.
              Refunds are not available for accounts suspended for Terms violations.
            </p>
          </Section>

          <Section title="7. AI disclosure">
            <p>
              ECALT uses large language models (including Claude by Anthropic) to generate learning content.
              AI responses are:
            </p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Generated dynamically — they may contain errors or inaccuracies.</li>
              <li>Educational in intent — not medical, legal, financial, or professional advice.</li>
              <li>Reviewed by our team via sampling — not individually moderated before delivery.</li>
            </ul>
            <p>
              ECALT is an AI tutor, supervised by our safety guardrails, not a replacement for school
              or a licensed professional. For decisions that matter — health, legal, financial — please
              consult a qualified expert.
            </p>
          </Section>

          <Section title="8. Intellectual property">
            <p>
              ECALT's platform, branding, AI models, interface, and curated content are owned by
              AUB Edulearn. You may not copy, reproduce, or redistribute them.
            </p>
            <p>
              The questions you ask and the journeys you create are yours. We use them only to
              operate the service (and only as described in our Privacy Policy). We do not claim
              ownership over user-generated content.
            </p>
          </Section>

          <Section title="9. Governing law">
            <p>
              These terms are governed by the laws of India. Any dispute arising from your use of
              ECALT will be subject to the exclusive jurisdiction of courts in Navi Mumbai,
              Maharashtra, India. We will always attempt to resolve disputes amicably first —
              email <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a> and
              we will respond within 48 hours.
            </p>
          </Section>

          <Section title="10. Changes to these terms">
            <p>
              We will notify account holders by email at least 14 days before any material change
              takes effect. Continued use after the effective date constitutes acceptance of the
              updated terms.
            </p>
          </Section>

          <p className="text-xs text-slate-400 text-center mt-6">
            Questions?{' '}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>
            {' '}· <a href="/privacy-policy" className="hover:underline">Privacy Policy</a>
            {' '}· <a href="/contact" className="hover:underline">Contact us</a>
          </p>
        </div>
      </div>
    </>
  )
}
