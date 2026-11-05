import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { call } from './adminctl.mjs'
import { loadE2EEnv } from './env'

// #22 — the whole schools story as one recorded demo, against dev (dark mode).
//   1 teacher: upload a document → AI outline → build → polish → publish → assign
//   2 student: class code + PIN sign-in → course → lesson → ask the tutor → quiz
//   3 teacher: progress matrix → drill-down → the tutor transcript
// Each part records its own video; e2e/make_demo_video.sh stitches them.
// Setup/cleanup via the API: a demo class + student, archived/deleted after.
const SCHOOL = 'Test Public School'
const TAG = Date.now().toString(36)
const CLASS_NAME = `Year 6 Science (demo ${TAG})`
const STUDENT = 'Asha K'
const COURSE_TITLE = 'The Solar System'
const OUT = path.resolve('e2e/.output/demo')
const DOC = path.join(OUT, 'solar-system.docx')
type Json = Record<string, any>

async function api(method: string, p: string, body?: Json): Promise<Json> {
  const r = await call(method, p, body ? JSON.stringify(body) : undefined)
  expect(r.ok, `${method} ${p} → ${r.status} ${r.body}`).toBeTruthy()
  return r.body ? JSON.parse(r.body) : {}
}

test.describe.configure({ mode: 'serial' })
test.use({
  video: { mode: 'on', size: { width: 1280, height: 800 } },
  viewport: { width: 1280, height: 800 },
  launchOptions: { slowMo: 120 },
})

const S: { base: string; classId: string; code: string; uid: string; pin: string; jid: string } =
  { base: '', classId: '', code: '', uid: '', pin: '', jid: '' }

test.beforeAll(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  execFileSync(path.resolve('../backend/.venv/bin/python'), [path.resolve('e2e/make_demo_docx.py'), DOC])
  const { schools } = await api('GET', '/api/v1/schools/mine')
  S.base = `/api/v1/schools/${schools.find((s: Json) => s.name === SCHOOL).id}`
  const cls = await api('POST', `${S.base}/classes`, { name: CLASS_NAME, grade: 6, subject: 'Science' })
  S.classId = cls.id
  S.code = (await api('GET', `${S.base}/classes/${cls.id}`)).join_code
  const st = await api('POST', `${S.base}/students`, { display_name: STUDENT, grade: 6, secret_kind: 'pin', class_ids: [cls.id] })
  S.uid = st.uid
  S.pin = st.secret
})

test.afterAll(async () => {
  if (S.uid) await call('DELETE', `${S.base}/students/${S.uid}`)
  if (S.classId) await call('DELETE', `${S.base}/classes/${S.classId}`)
  if (S.jid) await call('POST', `${S.base}/courses/${S.jid}/archive`, '{}')
})

const hold = (page: import('@playwright/test').Page, ms = 1500) => page.waitForTimeout(ms)

test('1 teacher builds and assigns a course', async ({ page }) => {
  test.setTimeout(600_000)
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await hold(page)
  const nav = page.getByRole('navigation', { name: 'School sections' })

  await nav.getByRole('link', { name: 'Materials' }).click()
  await page.locator('input[type="file"]').setInputFiles(DOC)
  const row = page.getByText('solar-system.docx').first().locator('xpath=ancestor::div[contains(@class,"p-4")][1]')
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 150_000 })
  await hold(page)

  await nav.getByRole('link', { name: 'Courses' }).click()
  await page.getByRole('button', { name: 'New course' }).click()
  await page.getByText('solar-system.docx').first().click()
  await page.getByPlaceholder('The Water Cycle').fill(COURSE_TITLE)
  await page.getByPlaceholder('Science').fill('Science').catch(() => {})
  await hold(page, 800)
  await page.getByRole('button', { name: 'Continue to estimate' }).click()
  await expect(page.getByText('Ready to generate the outline')).toBeVisible({ timeout: 30_000 })
  await hold(page, 2500)
  await page.getByRole('button', { name: 'Generate outline' }).click()
  await expect(page).toHaveURL(/\/school\/courses\/[0-9a-f-]{36}$/, { timeout: 30_000 })
  S.jid = page.url().split('/').pop()!

  await expect(page.getByRole('button', { name: /Approve outline & build/ })).toBeVisible({ timeout: 180_000 })
  await hold(page, 3000)
  await page.getByRole('button', { name: /Approve outline & build/ }).click()
  await expect(page.getByRole('button', { name: 'Publish' })).toBeVisible({ timeout: 300_000 })
  await hold(page, 2000)

  // Polish: icon, sources, preview as student.
  await page.getByRole('button', { name: 'Details' }).click()
  await page.getByLabel('Course icon').fill('🪐')
  await page.getByRole('button', { name: 'Save details' }).click()
  await hold(page, 1000)
  await page.getByTestId('show-sources').click()
  await expect(page.getByTestId('source-chunks')).toBeVisible({ timeout: 15_000 })
  await hold(page, 2500)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Preview as student' }).click()
  await hold(page, 3000)
  await page.getByTestId('student-preview').getByRole('button', { name: 'Close', exact: true }).first().click()

  await page.getByRole('button', { name: 'Publish' }).click()
  const dlg = page.getByRole('dialog', { name: 'Publish course' })
  const ack = dlg.getByRole('checkbox')
  if (await ack.isVisible().catch(() => false)) await ack.check()
  await dlg.getByRole('button', { name: 'Publish to students' }).click()
  await expect(dlg).toBeHidden({ timeout: 30_000 })
  await hold(page)

  // Assign to the class.
  await page.goto(`/school/classes/${S.classId}`)
  await page.getByLabel('Assign a course').selectOption(S.jid)
  await hold(page, 800)
  await page.getByRole('button', { name: 'Assign', exact: true }).click()
  await expect(page.getByText(COURSE_TITLE).first()).toBeVisible()
  await hold(page, 2500)
})

test.describe('student', () => {
  // The real class sign-in calls Firebase from the browser; Firebase rejects the
  // Vercel bypass *header*, so this part uses Vercel's bypass *cookie* instead.
  test.use({
    extraHTTPHeaders: {},
    storageState: { cookies: [], origins: [{ origin: 'https://ecalt-dev.vercel.app', localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] },
  })

  test('2 student signs in and learns', async ({ page }) => {
    test.setTimeout(300_000)
    const bypass = loadE2EEnv().bypassSecret
    await page.goto(`/class?x-vercel-protection-bypass=${encodeURIComponent(bypass)}&x-vercel-set-bypass-cookie=samesitenone`)
    await page.goto('/class')
    await page.getByPlaceholder('ABCD-EFGH').pressSequentially(S.code, { delay: 60 })
    await page.getByRole('button', { name: 'Next' }).click()
    await page.getByRole('button', { name: new RegExp(STUDENT) }).click()
    await page.locator('#student-pin').pressSequentially(S.pin, { delay: 120 })
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(page).toHaveURL(/\/my-classes/, { timeout: 30_000 })
    await hold(page, 2000)

    await page.getByRole('link').filter({ hasText: COURSE_TITLE }).click()
    await expect(page).toHaveURL(/\/journey\//)
    const start = page.getByRole('button', { name: /Start Journey|Continue/ })
    await start.waitFor({ timeout: 20_000 }).catch(() => {})
    if (await start.isVisible().catch(() => false)) await start.click()
    await hold(page, 5000)
    await page.mouse.wheel(0, 500)
    await hold(page, 2500)

    // Ask the tutor (docked on the right at desktop width).
    const ask = page.getByPlaceholder('Ask a question…')
    if (!(await ask.isVisible().catch(() => false))) await page.getByRole('button', { name: /Ask Tutor/ }).click()
    await ask.fill('Why does Mercury have the shortest year?')
    await page.keyboard.press('Enter')
    await page.waitForTimeout(12_000)
    await hold(page, 2000)
  })
})

test('3 teacher sees progress and the tutor chat', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await page.goto(`/school/classes/${S.classId}`)
  const card = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Progress' }) })
  await card.scrollIntoViewIfNeeded()
  await expect(card.getByText(STUDENT)).toBeVisible({ timeout: 20_000 })
  await hold(page, 2500)
  await card.getByRole('button', { name: STUDENT }).click()
  await hold(page, 3000)
  const transcripts = page.getByRole('button', { name: /tutor|transcript|chat/i }).first()
  if (await transcripts.isVisible().catch(() => false)) { await transcripts.click(); await hold(page, 4000) }
})
