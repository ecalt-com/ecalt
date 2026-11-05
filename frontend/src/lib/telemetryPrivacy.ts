// What error reports and web analytics may see (compliance memo G4/G5).
//
// - School students: no Vercel Analytics / Speed Insights events at all, and
//   error reports carry no user, URL query/fragment or request bodies.
// - Everyone: URLs lose their query string and fragment before they leave the
//   browser (badge sign-in tokens live in the fragment, invite/consent tokens in
//   the query).

let studentSession = false

/** AuthContext calls this whenever the signed-in user changes. */
export function setStudentSession(isStudent: boolean): void {
  studentSession = isStudent
}

// Pages only students (or people about to sign in as one) see.
const STUDENT_PATHS = [/^\/class(\/|$)/, /^\/my-classes(\/|$)/]

function storedStudentLogin(): boolean {
  // Firebase keeps a student's session in sessionStorage (shared classroom
  // devices); reading it covers the first page load before auth restores.
  try {
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i) || ''
      if (key.startsWith('firebase:authUser:') && (sessionStorage.getItem(key) || '').includes('"uid":"stu_')) {
        return true
      }
    }
  } catch {
    // storage blocked — fall through
  }
  return false
}

export function isStudentSession(): boolean {
  return studentSession || storedStudentLogin()
}

export function isStudentPath(pathname: string): boolean {
  return STUDENT_PATHS.some(re => re.test(pathname))
}

/** Origin + path only. */
export function stripUrl(url: string | undefined): string | undefined {
  if (!url) return url
  try {
    const u = new URL(url, window.location.origin)
    return `${u.origin}${u.pathname}`
  } catch {
    return url.split(/[?#]/)[0]
  }
}

/** Vercel Analytics / Speed Insights `beforeSend`: null drops the event. */
export function analyticsBeforeSend<T extends { url: string }>(event: T): T | null {
  let path = '/'
  try { path = new URL(event.url).pathname } catch { /* keep '/' */ }
  if (isStudentSession() || isStudentPath(path)) return null
  return { ...event, url: stripUrl(event.url) || event.url }
}

// Minimal structural types so this file doesn't depend on Sentry's internals.
type SentryRequest = { url?: string; query_string?: unknown; data?: unknown; cookies?: unknown; headers?: Record<string, string> }
type SentryEventLike = { request?: SentryRequest; user?: unknown; breadcrumbs?: { data?: Record<string, unknown> }[]; tags?: Record<string, unknown> }

function scrubRequest(req: SentryRequest | undefined): void {
  if (!req) return
  req.url = stripUrl(req.url)
  delete req.query_string
  delete req.data
  delete req.cookies
  if (req.headers) {
    for (const h of Object.keys(req.headers)) {
      if (/authorization|cookie|x-parent-unlock|x-profile-id|x-impersonate/i.test(h)) delete req.headers[h]
    }
  }
}

/** Sentry `beforeSend` / `beforeSendTransaction`. */
export function scrubSentryEvent<T extends SentryEventLike>(event: T): T {
  scrubRequest(event.request)
  for (const crumb of event.breadcrumbs || []) {
    const data = crumb.data
    if (!data) continue
    for (const key of ['url', 'from', 'to']) {
      if (typeof data[key] === 'string') data[key] = stripUrl(data[key] as string)
    }
  }
  if (isStudentSession()) {
    delete event.user
    event.tags = { ...event.tags, school_student: 'true' }
  }
  return event
}
