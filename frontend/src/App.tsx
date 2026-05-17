import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { Analytics } from '@vercel/analytics/react'
import { SpeedInsights } from '@vercel/speed-insights/react'
import { ThemeProvider } from './lib/ThemeContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { ToastProvider } from './lib/ToastContext'
import { SubscriptionProvider } from './lib/SubscriptionContext'
import OnboardingModal from './components/OnboardingModal'
import ErrorBoundary from './components/ErrorBoundary'

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
const ComingSoon    = lazy(() => import('./pages/ComingSoon'))

function PageSkeleton() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function AppShell() {
  const { needsOnboarding } = useAuth()
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
      {needsOnboarding && <OnboardingModal />}
    </>
  )
}

export default function App() {
  return (
    <HelmetProvider>
      <ThemeProvider>
        <AuthProvider>
          <SubscriptionProvider>
          <ToastProvider>
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <AppShell />
            </BrowserRouter>
          </ToastProvider>
          </SubscriptionProvider>
        </AuthProvider>
        <Analytics />
        <SpeedInsights />
      </ThemeProvider>
    </HelmetProvider>
  )
}
