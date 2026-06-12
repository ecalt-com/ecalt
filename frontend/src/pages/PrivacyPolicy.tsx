import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { Shield, Mail, MapPin } from 'lucide-react'

const LAST_UPDATED = 'June 2026'
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
              <li>✦ Children under 18 need a parent to confirm their account before anything is stored.</li>
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
              <li>Name and email address (from Google Sign-In), used to send consent confirmation and account notices.</li>
              <li>Consent records: date and time you confirmed your child's account, kept for legal compliance.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">From the child / learner:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>First name and Google account ID, used to personalise their experience.</li>
              <li>Learning questions, journeys, and progress — the core service data.</li>
              <li>AI-generated knowledge nodes (topics explored), stored in their Passport.</li>
              <li>Birth year (not full date of birth), used solely to enforce the age gate.</li>
            </ul>
            <p className="font-medium text-slate-700 dark:text-slate-200 pt-2">We do NOT collect:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li>Location (beyond country for payment routing)</li>
              <li>Device identifiers or browser fingerprints</li>
              <li>Photos, voice, or any biometric data</li>
            </ul>
          </Section>

          <Section title="3. How parental consent works">
            <p>
              When a learner under 18 signs up, we send a confirmation email to their parent or guardian.
              The account is inactive — no data is stored beyond the parent's email — until the parent
              clicks the confirmation link. The link expires in 7 days. If the parent does not confirm,
              all data is deleted automatically.
            </p>
            <p>
              Parents can withdraw consent at any time by emailing{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>.
              Withdrawal triggers immediate account deletion.
            </p>
          </Section>

          <Section title="4. Our promise">
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

          <Section title="5. Data retention and your rights">
            <ul className="list-disc list-inside space-y-1.5 pl-1">
              <li><span className="font-medium">Active accounts:</span> data is retained while the account is active.</li>
              <li><span className="font-medium">Deleted accounts:</span> purged within 30 days of deletion request.</li>
              <li><span className="font-medium">Consent records:</span> retained for 3 years as required by law.</li>
            </ul>
            <p className="pt-1">
              You have the right to access, correct, and delete your data at any time.
              Signed-in users can download or delete their data from{' '}
              <a href="/profile" className="text-violet-600 dark:text-violet-400 underline">Profile → Privacy &amp; Data</a>.
              For any other request, email <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>.
            </p>
          </Section>

          <Section title="6. Security">
            <p>
              All data in transit is encrypted via TLS 1.2+. Data at rest is encrypted by our
              storage provider (Supabase/AWS). We use Firebase Auth for authentication — we never
              store passwords. We conduct periodic internal security reviews and act on
              vulnerability reports within 72 hours. To report a security issue, email{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-violet-600 dark:text-violet-400 underline">{CONTACT_EMAIL}</a>{' '}
              with the subject line "Security Report".
            </p>
          </Section>

          <Section title="7. Cookies">
            <p>
              We use only essential session cookies (Firebase Auth). We do not use advertising
              cookies, analytics cookies, or any third-party tracking pixels beyond Vercel
              Analytics (aggregated, anonymised page-view counts with no personal identifiers).
            </p>
          </Section>

          <Section title="8. Changes to this policy">
            <p>
              We will notify you by email (at the address in your account) at least 14 days before
              any material change to this policy takes effect. Continued use after the effective
              date constitutes acceptance.
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
