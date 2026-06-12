import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { Analytics } from '@vercel/analytics/react'
import { SpeedInsights } from '@vercel/speed-insights/react'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { ToastProvider } from './lib/ToastContext'
import { SubscriptionProvider } from './lib/SubscriptionContext'
import { GeoProvider } from './lib/GeoContext'
import { PaymentConfigProvider } from './lib/PaymentConfig'
import OnboardingModal from './components/OnboardingModal'
import ErrorBoundary from './components/ErrorBoundary'
import BirthYearGate from './components/auth/BirthYearGate'
import Under13Block from './components/auth/Under13Block'
import ParentalConsentForm, { ConsentSentScreen } from './components/auth/ParentalConsentForm'

// LANDING PAGE TOGGLE — swap these two lines to use cosmic home:
// const Home       = lazy(() => import('./pages/HomeCosmic'))
const Home          = lazy(() => import('./pages/Home'))
const Learn         = lazy(() => import('./pages/Learn'))
const Pricing       = lazy(() => import('./pages/Pricing'))
const Admin         = lazy(() => import('./pages/Admin'))
const MindSignature = lazy(() => import('./pages/MindSignature'))
const Verify        = lazy(() => import('./pages/Verify'))
const Explore       = lazy(() => import('./pages/Explore'))
const Journeys      = lazy(() => import('./pages/Journeys'))
const Journey       = lazy(() => import('./pages/Journey'))
const Passport      = lazy(() => import('./pages/Passport'))
const Profile       = lazy(() => import('./pages/Profile'))
const ConsentConfirm = lazy(() => import('./pages/ConsentConfirm'))
const Welcome       = lazy(() => import('./pages/Welcome'))
const ComingSoon    = lazy(() => import('./pages/ComingSoon'))
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'))
const Terms         = lazy(() => import('./pages/Terms'))
const Parents       = lazy(() => import('./pages/Parents'))
const Contact       = lazy(() => import('./pages/Contact'))

function PageSkeleton() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function AppShell() {
  const { needsOnboarding, postSignInPhase, parentEmail, completeBirthYear, markConsentSent, dismissPostSignIn } = useAuth()

  return (
    <>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/" element={<ErrorBoundary><Home /></ErrorBoundary>} />
          <Route path="/learn" element={<ErrorBoundary><Learn /></ErrorBoundary>} />
          <Route path="/pricing" element={<ErrorBoundary><Pricing /></ErrorBoundary>} />
          <Route path="/admin" element={<ErrorBoundary><Admin /></ErrorBoundary>} />
          <Route path="/mind-signature" element={<ErrorBoundary><MindSignature /></ErrorBoundary>} />
          <Route path="/verify/:hash" element={<ErrorBoundary><Verify /></ErrorBoundary>} />
          <Route path="/explore" element={<ErrorBoundary><Explore /></ErrorBoundary>} />
          <Route path="/journeys" element={<ErrorBoundary><Journeys /></ErrorBoundary>} />
          <Route path="/journey/:id" element={<ErrorBoundary><Journey /></ErrorBoundary>} />
          <Route path="/passport" element={<ErrorBoundary><Passport /></ErrorBoundary>} />
          <Route path="/profile" element={<ErrorBoundary><Profile /></ErrorBoundary>} />
          <Route path="/privacy" element={<Navigate to="/profile" replace />} />
          <Route path="/privacy-policy" element={<ErrorBoundary><PrivacyPolicy /></ErrorBoundary>} />
          <Route path="/terms" element={<ErrorBoundary><Terms /></ErrorBoundary>} />
          <Route path="/parents" element={<ErrorBoundary><Parents /></ErrorBoundary>} />
          <Route path="/contact" element={<ErrorBoundary><Contact /></ErrorBoundary>} />
          <Route path="/welcome" element={<ErrorBoundary><Welcome /></ErrorBoundary>} />
          <Route path="/consent/confirm" element={<ErrorBoundary><ConsentConfirm /></ErrorBoundary>} />
          <Route
            path="/sign-in"
            element={<ComingSoon title="Sign In — Coming Soon" description="User accounts are on the way. Drop your email and we'll notify you." />}
          />
          <Route
            path="/get-started"
            element={<ComingSoon title="Early Access" description="Join the waitlist and be among the first to unlock a personalized learning passport." />}
          />
          <Route
            path="*"
            element={<ComingSoon title="Page not found" description="This page doesn't exist yet — but your next learning journey is just one question away." />}
          />
        </Routes>
      </Suspense>

      {/* Post-sign-in compliance gates — rendered in order of priority */}
      {postSignInPhase === 'birth_year' && (
        <BirthYearGate onSubmit={completeBirthYear} />
      )}
      {postSignInPhase === 'under_13' && (
        <Under13Block onDismiss={dismissPostSignIn} />
      )}
      {postSignInPhase === 'consent_pending' && (
        <ParentalConsentForm onSent={markConsentSent} />
      )}
      {postSignInPhase === 'consent_sent' && parentEmail && (
        <ConsentSentScreen parentEmail={parentEmail} onSignOut={dismissPostSignIn} />
      )}

      {needsOnboarding && <OnboardingModal />}
    </>
  )
}

export default function App() {
  return (
    <HelmetProvider>
      <ThemeProvider>
        <AuthProvider>
          <GeoProvider>
          <PaymentConfigProvider>
          <SubscriptionProvider>
          <ToastProvider>
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <AppShell />
            </BrowserRouter>
          </ToastProvider>
          </SubscriptionProvider>
          </PaymentConfigProvider>
          </GeoProvider>
        </AuthProvider>
        <Analytics />
        <SpeedInsights />
      </ThemeProvider>
    </HelmetProvider>
  )
}
