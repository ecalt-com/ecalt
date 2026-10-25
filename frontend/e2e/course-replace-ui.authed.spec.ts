import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { call } from './adminctl.mjs'
import { loadE2EEnv } from './env'

// #21 frontend (SC-604/605 §8.6a), recorded, against dev:
//   1. Teacher: on a published course, "Update from a document" → "Rebuild from
//      this document" → the job finishes → the modal closes straight onto the
//      new draft in the step editor (no proposal review).
//   2. Student: having finished steps before the rebuild, sees an "Updated" pill
//      on the finished steps whose content changed once the draft is published.
// Setup/teardown go through the API: a throwaway copy of a published fixture
// course, assigned to the student's class, archived at the end.
const env = loadE2EEnv()
const SCHOOL = 'Test Public School'
const SOURCE_COURSE = 'Introduction to Volcanoes'
const DOC = 'volcanoes.docx'
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4' // Physics @ Test Public School
const CLASS_NAME = process.env.E2E_STUDENT_CLASS || 'Physics'

type Json = Record<string, any>

async function api(method: string, path: string, body?: Json): Promise<Json> {
  const r = await call(method, path, body ? JSON.stringify(body) : undefined)
  expect(r.ok, `${method} ${path} → ${r.status} ${r.body}`).toBeTruthy()
  return r.body ? JSON.parse(r.body) : {}
}

// Student API calls (progress seeding) with a minted student ID token.
function adminApp() {
  const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
  return getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
}
async function studentIdToken(): Promise<string> {
  const customToken = await getAuth(adminApp()).createCustomToken(STUDENT_UID)
  const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${env.webConfig.apiKey}`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ token: customToken, returnSecureToken: true }),
  }).then(r => r.json())
  expect(ex.idToken, 'student token exchange failed').toBeTruthy()
  return ex.idToken
}

test.describe.configure({ mode: 'serial' })
test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 80 },
})

let base = ''
let jid = ''
let assignmentPath = ''
const finished: string[] = []

test.afterAll(async () => {
  if (assignmentPath) await call('DELETE', assignmentPath)
  if (jid) await call('POST', `${base}/courses/${jid}/archive`, '{}')
})

test('teacher rebuilds a published course from a document (recorded)', async ({ page }) => {
  test.setTimeout(900_000)

  // ── Setup: published copy, assigned to the student's class, every step finished.
  const { schools } = await api('GET', '/api/v1/schools/mine')
  const school = schools.find((s: Json) => s.name === SCHOOL)
  expect(school, `school "${SCHOOL}" not on dev`).toBeTruthy()
  base = `/api/v1/schools/${school.id}`

  const courses = await api('GET', `${base}/courses`)
  const source = (courses.courses ?? courses).find(
    (c: Json) => c.title === SOURCE_COURSE && c.status === 'published')
  expect(source, `published "${SOURCE_COURSE}" not on dev`).toBeTruthy()

  jid = (await api('POST', `${base}/courses/${source.journey_id}/duplicate`)).journey_id
  await api('POST', `${base}/courses/${jid}/publish`, {})

  const classes = await api('GET', `${base}/classes`)
  const cls = (classes.classes ?? classes).find((c: Json) => c.name === CLASS_NAME)
  expect(cls, `class "${CLASS_NAME}" not on dev`).toBeTruthy()
  const assignment = await api('POST', `${base}/classes/${cls.id}/courses`, { journey_id: jid })
  assignmentPath = `${base}/classes/${cls.id}/courses/${assignment.id}`

  const stuToken = await studentIdToken()
  const steps = (await api('GET', `/api/v1/journeys/${jid}`)).steps.map((s: Json) => s.id)
  for (const sid of steps) {
    const r = await fetch(`${env.baseURL}/api/v1/progress/${jid}/${sid}`, {
      method: 'POST',
      // Only the secret: the set-bypass-cookie flag redirects plain Node fetch.
      headers: { authorization: `Bearer ${stuToken}`, 'x-vercel-protection-bypass': env.bypassSecret },
    })
    expect(r.ok, `student completes ${sid} → ${r.status} ${await r.text()}`).toBeTruthy()
    finished.push(sid)
  }

  // ── Teacher UI: rebuild in replace mode.
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  await page.goto(`/school/courses/${jid}`)

  await page.getByRole('button', { name: /Update from a document/i }).click()
  const dlg = page.getByRole('dialog', { name: /Update from a document/i })
  await expect(dlg).toBeVisible()
  await dlg.locator('select').selectOption({ label: DOC })
  await dlg.getByText('Rebuild from this document', { exact: true }).click()
  await expect(dlg.getByText(/Steps whose title still matches keep their progress/)).toBeVisible()
  await dlg.getByRole('button', { name: /Rebuild course/i }).click()
  await expect(dlg.getByText(/Building a new version of the course/)).toBeVisible()

  // Completion closes the modal onto the new draft — no proposal review.
  await expect(dlg).toBeHidden({ timeout: 840_000 })
  await expect(page.getByText(/Course rebuilt/)).toBeVisible()
  await expect(page.getByRole('button', { name: /^Publish$/ })).toBeVisible()
  await page.waitForTimeout(1500)

  const course = await api('GET', `${base}/courses/${jid}`)
  expect(course.draft.meta.rebuilt_from_document).toBe(true)
  expect(course.draft.steps.every((s: Json) => !!s.body_md), 'a rebuilt step has no body').toBeTruthy()

  // Publish (API) so the student sees v2.
  await api('POST', `${base}/courses/${jid}/publish`, {})
  // eslint-disable-next-line no-console
  console.log(`[course-replace-ui] rebuilt: ${course.draft.steps.length} steps`)
})

test.describe('student', () => {
  test.use({ storageState: { cookies: [], origins: [{ origin: env.baseURL, localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] } })

  test('student sees "Updated" on finished steps that changed (recorded)', async ({ page }) => {
    test.setTimeout(120_000)
    expect(jid, 'teacher test did not set up the course').toBeTruthy()

    const journey = await api('GET', `/api/v1/journeys/${jid}`)
    const stamped = journey.steps.filter((s: Json) => s.content_updated_at && finished.includes(s.id)).map((s: Json) => s.id)
    expect(stamped.length, 'no finished step was changed by the rebuild').toBeGreaterThan(0)

    // Sign in as the student (same technique as student-course.public.spec.ts).
    const customToken = await getAuth(adminApp()).createCustomToken(STUDENT_UID)
    await page.route('**/__e2e_auth', (route) =>
      route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', headers: { 'content-security-policy': '' },
        body: '<!doctype html><html><head><meta charset="utf-8"><title>e2e student</title></head><body>signing in…</body></html>' }))
    await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
    await page.evaluate(async ({ customToken, config, sdkVersion }) => {
      const b = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      const appMod: any = await import(/* @vite-ignore */ `${b}/firebase-app.js`)
      const authMod: any = await import(/* @vite-ignore */ `${b}/firebase-auth.js`)
      const auth = authMod.getAuth(appMod.initializeApp(config))
      await authMod.setPersistence(auth, authMod.browserLocalPersistence)
      const cred = await authMod.signInWithCustomToken(auth, customToken)
      await cred.user.getIdToken(true)
    }, { customToken, config: env.webConfig, sdkVersion: env.sdkVersion })

    await page.goto(`/journey/${jid}`)
    const badges = page.getByTestId('step-updated-badge')
    await expect(badges.first()).toBeVisible({ timeout: 20_000 })
    await expect(badges).toHaveCount(stamped.length)
    for (const sid of stamped) {
      await expect(page.locator(`#step-${sid}`).getByTestId('step-updated-badge')).toBeVisible()
    }
    await expect(badges.first()).toHaveAttribute('title', /updated this step after you finished it/)
    await badges.first().scrollIntoViewIfNeeded()
    await page.waitForTimeout(2000)
    // eslint-disable-next-line no-console
    console.log(`[course-replace-ui] student sees ${stamped.length} Updated badge(s)`)
  })
})
