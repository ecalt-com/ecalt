import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Shield, Mail, MapPin } from 'lucide-react'

const LAST_UPDATED = 'July 2026'
const CONTACT_EMAIL = 'support@ecalt.com'
const OFFICE_ADDRESS = 'AUB Edulearn, WeGrow Office, Plot No. 88, 8th Floor, Proxima, Arunachal Bhavan, 19, Sector 30A, Vashi, Navi Mumbai, Maharashtra – 400703'

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

export default function PrivacyPolicy() {
  return (
    <>
      <PageMeta
        title="Privacy Policy — ECALT"
        description="How ECALT collects, uses, and protects your child's data. Plain-language summary and full policy."
      />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 pt-24 pb-20">
        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="mb-10">
            <div className="flex items-center gap-2 mb-3">
              <Shield size={20} className="text-violet-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">Privacy Policy</span>
            </div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-2">
              We treat your child's data like we'd want ours treated.
            </h1>
            <p className="text-sm text-slate-400">Last updated: {LAST_UPDATED}</p>
          </div>

          {/* Plain-language summary */}
          <div className="glass-card rounded-2xl p-5 mb-8 border-l-4 border-violet-500">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">The short version</p>
            <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-1.5">
              <li>✦ We collect only what's needed to run the learning service.</li>
              <li>✦ We never sell your data. No ads. No third-party marketing profiling.</li>
              <li>✦ Learners under 18 need a parent's reviewed, verified consent before their account activates.</li>
              <li>✦ Parents can review, export, delete, and control their child's account from the Family dashboard.</li>
              <li>✦ You can download or delete all your data at any time.</li>
              <li>✦ Questions? Email us at <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a> — a human reads every message.</li>
            </ul>
          </div>

          <Section title="1. Who we are">
            <p>
              ECALT is an AI-powered learning platform for curious learners aged 8 and up.
              We are operated from India and comply with India's Digital Personal Data Protection
              Act 2023 (DPDP), the Information Technology Act 2000, and COPPA where applicable
              for users in the United States.
            </p>
          </Section>

          <Section title="2. What we collect — and why">
            <p className="font-medium text-slate-700 dark:text-slate-200">From the parent / account holder:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Name and email address (from Google Sign-In), used to send consent requests, receipts, and account notices.</li>
              <li>Consent records: what you consented to, when, how it was verified, and under which policy version — kept for legal compliance.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">From learners aged 13–17 (self-signup):</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Name and email from Google sign-in, used to personalise their experience.</li>
              <li>Learning questions, journeys, and progress — the core service data.</li>
              <li>AI conversations with the tutor, and AI-generated knowledge topics stored in their Passport.</li>
              <li>Birth year and month (not the exact day), used solely for age checks.</li>
              <li>Country, recorded once at signup as the consent jurisdiction.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">From children under 13 (parent-created accounts):</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>The same learning data, but the login identity (name, email) is created and controlled by the parent.</li>
              <li>AI chat is off by default for under-13s; a parent must explicitly enable it.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">We do NOT collect:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Location (beyond country for payment routing and consent jurisdiction)</li>
              <li>Device identifiers or browser fingerprints</li>
              <li>Photos, voice, or any biometric data</li>
            </ul>
            <p className="pt-1">
              We never use children's data for advertising, marketing profiling, or behavioural tracking.
            </p>
          </Section>

          <Section title="3. How parental consent works">
            <p>
              Every learner under 18 needs a parent or guardian's consent before their account activates.
              There are two paths:
            </p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><span className="font-medium">Parent-created:</span> you create the account from your Family dashboard, reviewing and accepting the data disclosure as part of setup.</li>
              <li><span className="font-medium">Teen self-signup:</span> the teen signs up and names you; we email you a review page where you explicitly approve or decline. The link expires in 7 days, and nothing activates until you decide.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">How we verify it's really a parent:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><span className="font-medium">Email-plus</span> (teens 13+ in most countries): your emailed approval, plus a delayed follow-up notice with a one-click "this wasn't me" link that suspends the account immediately.</li>
              <li><span className="font-medium">Card verification</span> (all under-13s, and all minors in India): a card check via our payment processor confirms an adult is consenting. Nothing is charged and no card details are stored by us.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">Age thresholds by region:</p>
            <p>
              The age at which someone can consent to data processing themselves varies by law — for
              example 13 in the US (COPPA) and UK, 13–16 across the EU (GDPR Art. 8), and 18 in India
              (DPDP Act 2023). We record your country at signup and apply the strictest rule that fits:
              every minor needs parental consent on ECALT, and your jurisdiction decides how strongly we
              verify it.
            </p>
            <p className="pt-1">
              If our privacy policy materially changes, we notify consenting parents and ask them to
              re-accept the new version before continuing.
            </p>
          </Section>

          <Section title="4. Parental rights">
            <p>As the consenting parent, you can at any time — from your Family dashboard, no support email needed:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><span className="font-medium">Review</span> your child's learning activity: topics, journeys, progress, quiz scores, and conversation titles (full transcripts only if you enable it — your child is told what you can see).</li>
              <li><span className="font-medium">Export</span> everything we store about your child as a JSON file.</li>
              <li><span className="font-medium">Control</span> the account: pause it, disable AI chat, set a content level, and manage the weekly digest.</li>
              <li><span className="font-medium">Withdraw consent</span> — the account pauses immediately and is deleted after a 14-day grace window (you can undo within the window).</li>
              <li><span className="font-medium">Delete</span> the account and all its data immediately and permanently.</li>
            </ul>
          </Section>

          <Section title="5. Our promise">
            <p className="font-semibold text-slate-800 dark:text-slate-100">
              We will never sell your child's data. We will never show them ads.
              We will never profile them for any marketing purpose — ours or anyone else's.
            </p>
            <p>
              We use Google Firebase for authentication and Supabase (hosted on AWS) for data storage.
              Both are enterprise-grade providers with their own security certifications.
              We do not share your data with any third party except as required by law.
            </p>
          </Section>

          <Section title="6. Data retention and your rights">
            <ul className="list-disc list-inside space-y-1.5 pl-1">
              <li><span className="font-medium">Active accounts:</span> data is retained while the account is active.</li>
              <li><span className="font-medium">Pending accounts:</span> if parental consent never arrives, the account and all associated data (including the login credential) are deleted after 30 days.</li>
              <li><span className="font-medium">Inactive child accounts:</span> after 12 months of inactivity we notify the parent; if the account stays unused for another 30 days, deletion is scheduled with a 14-day grace window the parent can cancel.</li>
              <li><span className="font-medium">Consent withdrawal:</span> the account pauses immediately and is deleted after a 14-day grace window.</li>
              <li><span className="font-medium">Deleted accounts:</span> personal data is removed immediately on deletion; every deletion is logged.</li>
              <li><span className="font-medium">Consent proof:</span> consent events are retained in pseudonymised form (no name or email) as legally required evidence that consent existed.</li>
              <li><span className="font-medium">Un-actioned policy re-consent:</span> if a parent doesn't re-accept a materially changed policy, the child's account is paused 30 days after the notice.</li>
              <li><span className="font-medium">Turning 18:</span> the family link is graduated — parental controls are removed and the learner re-consents as an adult.</li>
            </ul>
            <p className="pt-1">
              You have the right to access, correct, and delete your data at any time.
              Signed-in users can download or delete their data from{' '}
              <a href="/profile" className="text-violet-600 dark:text-violet-400 underline">Profile → Privacy &amp; Data</a>;
              parents manage their children's data from the{' '}
              <a href="/family" className="text-violet-600 dark:text-violet-400 underline">Family dashboard</a>.
              For any other request, email <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>.
            </p>
          </Section>

          <Section title="7. Security">
            <p>
              All data in transit is encrypted via TLS 1.2+. Data at rest is encrypted by our
              storage provider (Supabase/AWS). We use Firebase Auth for authentication — we never
              store passwords. We conduct periodic internal security reviews and act on
              vulnerability reports within 72 hours. To report a security issue, email{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>{' '}
              with the subject line "Security Report".
            </p>
          </Section>

          <Section title="8. Cookies">
            <p>
              We use only essential session cookies (Firebase Auth). We do not use advertising
              cookies, analytics cookies, or any third-party tracking pixels beyond Vercel
              Analytics (aggregated, anonymised page-view counts with no personal identifiers).
            </p>
          </Section>

          <Section title="9. Changes to this policy">
            <p>
              We will notify you by email (at the address in your account) at least 14 days before
              any material change to this policy takes effect. Where the change affects a child's
              data, the consenting parent is asked to review and re-accept the new version — and the
              child's account is paused if they don't.
            </p>
          </Section>

          {/* Data contact card */}
          <div className="glass-card rounded-2xl p-5 flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <p className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-1">Grievance Officer / Data Contact</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
                For privacy complaints or data requests under the DPDP Act 2023 or IT Act 2000:
              </p>
              <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 mb-1.5">
                <Mail size={14} className="text-violet-500 shrink-0" />
                <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>
              </div>
              <div className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                <MapPin size={14} className="text-violet-500 shrink-0 mt-0.5" />
                <span>ECALT · {OFFICE_ADDRESS}</span>
              </div>
            </div>
            <div className="text-xs text-slate-400 sm:text-right">
              We respond to privacy requests within <span className="font-semibold">48 hours</span>.
            </div>
          </div>

        </div>
      </div>
    </>
  )
}
