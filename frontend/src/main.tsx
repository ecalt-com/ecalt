import React from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import App from './App'
import { scrubSentryEvent } from './lib/telemetryPrivacy'
import './index.css'

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    environment: import.meta.env.MODE,
    // No personal data in error reports (compliance memo G4): no IPs/cookies,
    // URLs without query/fragment, no user on student sessions.
    sendDefaultPii: false,
    beforeSend: event => scrubSentryEvent(event),
    beforeSendTransaction: event => scrubSentryEvent(event),
  })
}

// SPAs manage their own scroll — prevent the browser from restoring a
// previous scroll position on every page load/navigation.
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual'
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
