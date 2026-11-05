import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { call } from './adminctl.mjs'
import { loadE2EEnv } from './env'

// #20: school course pages at phone width (375px), dark mode. Fails when a page
// scrolls sideways; screenshots go to e2e/.output for a visual check.
const env = loadE2EEnv()
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4'

test.use({ viewport: { width: 375, height: 800 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })

async function overflow(page: Page): Promise<{ scroll: number; width: number; culprits: string[] }> {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth
    const culprits: string[] = []
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      const r = (el as HTMLElement).getBoundingClientRect()
      if (r.width && r.right > width + 1) {
        // Skip children of horizontally scrollable containers (tables, chip rows).
        let p = el.parentElement, scrollable = false
        while (p) { const s = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(s.overflowX)) { scrollable = true; break } p = p.parentElement }
        if (!scrollable) culprits.push(`${el.tagName.toLowerCase()}.${String((el as HTMLElement).className).slice(0, 60)} → ${Math.round(r.right)}`)
      }
    }
    return { scroll: document.documentElement.scrollWidth, width, culprits: culprits.slice(0, 8) }
  })
}

async function check(page: Page, name: string, problems: string[]) {
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(800)
  await page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true })
  const o = await overflow(page)
  if (o.scroll > o.width + 1 || o.culprits.length) problems.push(`${name}: scrollWidth ${o.scroll} > ${o.width}; ${o.culprits.join(' | ')}`)
}

test('staff course pages fit a 375px screen', async ({ page }) => {
  test.setTimeout(240_000)
  const problems: string[] = []
  const { schools } = JSON.parse((await call('GET', '/api/v1/schools/mine')).body)
  const school = schools.find((s: { name: string }) => s.name === SCHOOL)
  const base = `/api/v1/schools/${school.id}`
  const courses = JSON.parse((await call('GET', `${base}/courses`)).body).courses
  const published = courses.find((c: { status: string }) => c.status === 'published')
  const draft = courses.find((c: { status: string; draft_status: string | null }) => c.status === 'draft' && c.draft_status === 'built')

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  for (const [name, path] of [
    ['dashboard', '/school'], ['courses', '/school/courses'], ['course-new', '/school/courses/new'],
    ['materials', '/school/materials'], ['usage', '/school/usage'], ['class', `/school/classes/${CLASS_ID}`],
    ['published-course', `/school/courses/${published.journey_id}`],
    ...(draft ? [['draft-editor', `/school/courses/${draft.journey_id}`]] : []),
  ] as [string, string][]) {
    await page.goto(path)
    await check(page, name, problems)
  }
  expect(problems, problems.join('\n')).toEqual([])
})

test.describe('student', () => {
  test.use({ storageState: { cookies: [], origins: [{ origin: env.baseURL, localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] } })

  test('student pages fit a 375px screen', async ({ page }) => {
    test.setTimeout(120_000)
    const problems: string[] = []
    const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
    const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
    const customToken = await getAuth(app).createCustomToken(STUDENT_UID)
    await page.goto('/class')
    await check(page, 'class-sign-in', problems)
    await page.route('**/__e2e_auth', route => route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8',
      headers: { 'content-security-policy': '' }, body: '<!doctype html><html><body>signing in…</body></html>' }))
    await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
    await page.evaluate(async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const auth = authMod.getAuth(appMod.initializeApp(config))
      await authMod.setPersistence(auth, authMod.browserSessionPersistence)
      await authMod.signInWithCustomToken(auth, customToken)
    }, { customToken, config: env.webConfig, sdkVersion: env.sdkVersion })
    await page.goto('/my-classes')
    await expect(page.locator('a[href*="/journey/"]').first()).toBeVisible({ timeout: 20_000 })
    await check(page, 'my-classes', problems)
    await page.locator('a[href*="/journey/"]').first().click()
    await expect(page).toHaveURL(/\/journey\//)
    const start = page.getByRole('button', { name: /Start Journey|Continue/ })
    if (await start.isVisible().catch(() => false)) await start.click()
    await page.waitForTimeout(2500)
    await check(page, 'student-journey', problems)
    expect(problems, problems.join('\n')).toEqual([])
  })
})
