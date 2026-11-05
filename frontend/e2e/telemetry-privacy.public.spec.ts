import { expect, test } from '@playwright/test'
import { analyticsBeforeSend, scrubSentryEvent, setStudentSession, stripUrl } from '../src/lib/telemetryPrivacy'

// Logic checks for compliance memo G4/G5 (runs in Node, no browser). Dev's
// Vercel preview doesn't send analytics, so privacy.authed.spec.ts alone
// can't prove student events are dropped.
test.afterEach(() => setStudentSession(false))

test('analytics drops student pages and student sessions, strips query/fragment', () => {
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/class/badge#tok=abc' })).toBeNull()
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/my-classes' })).toBeNull()
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/school-invite?token=t' }))
    .toEqual({ type: 'pageview', url: 'https://ecalt.app/school-invite' })
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/classroom' })).not.toBeNull()
  setStudentSession(true)
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/journey/j1' })).toBeNull()
  expect(analyticsBeforeSend({ type: 'pageview', url: 'https://ecalt.app/privacy-policy' })).toBeNull()
})

test('error reports lose URL query/fragment, credentials and, for students, the user', () => {
  setStudentSession(true)
  const out = scrubSentryEvent({
    request: { url: 'https://ecalt.app/class/badge?x=1#tok', query_string: 'x=1', data: { a: 1 }, cookies: 'c',
               headers: { Authorization: 'Bearer t', 'X-Profile-Id': 'p', Accept: '*/*' } },
    user: { id: 'stu_1' },
    breadcrumbs: [{ data: { url: '/api/v1/school-student/home?debug=1', from: '/class#tok', to: '/my-classes' } }],
  })
  expect(out.request).toEqual({ url: 'https://ecalt.app/class/badge', headers: { Accept: '*/*' } })
  expect(out.user).toBeUndefined()
  expect(out.tags).toEqual({ school_student: 'true' })
  expect(JSON.stringify(out.breadcrumbs)).not.toMatch(/debug|tok/)
  expect(stripUrl('/a/b?c#d')).toBe('/a/b')
})
