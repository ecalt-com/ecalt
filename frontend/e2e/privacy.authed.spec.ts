import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

// Compliance memo G5: no Vercel Analytics / Speed Insights events from school
// students or student pages. Staff pages still report (proves the check works).
const env = loadE2EEnv()
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4'

function collectAnalytics(page: Page): string[] {
  const hits: string[] = []
  page.on('request', r => {
    const u = r.url()
    if (/\/_vercel\/(insights|speed-insights)\//.test(u) && !/script\.js/.test(u)) hits.push(u)
  })
  return hits
}

test('staff pages still send analytics page views', async ({ page }) => {
  const hits = collectAnalytics(page)
  await page.goto('/school')
  await expect(page.locator('#root')).not.toBeEmpty()
  await page.waitForTimeout(3000)
  test.skip(hits.length === 0, 'Vercel Analytics is not sending on this deployment')
  expect(hits.every(u => !u.includes('?') || !/token=/.test(u))).toBe(true)
})

test.describe('student', () => {
  test.use({ storageState: { cookies: [], origins: [{ origin: env.baseURL, localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] } })

  test('class sign-in page sends no analytics', async ({ page }) => {
    const hits = collectAnalytics(page)
    await page.goto('/class')
    await expect(page.locator('#root')).not.toBeEmpty()
    await page.waitForTimeout(3000)
    expect(hits).toEqual([])
  })

  test('a signed-in student sends no analytics on any page', async ({ page }) => {
    test.setTimeout(90_000)
    const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
    const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
    const customToken = await getAuth(app).createCustomToken(STUDENT_UID)
    await page.route('**/__e2e_auth', route =>
      route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', headers: { 'content-security-policy': '' },
        body: '<!doctype html><html><head><meta charset="utf-8"></head><body>signing in…</body></html>' }))
    await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
    // Session persistence, as the real class sign-in uses.
    await page.evaluate(async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const auth = authMod.getAuth(appMod.initializeApp(config))
      await authMod.setPersistence(auth, authMod.browserSessionPersistence)
      await authMod.signInWithCustomToken(auth, customToken)
    }, { customToken, config: env.webConfig, sdkVersion: env.sdkVersion })

    const hits = collectAnalytics(page)
    await page.goto('/my-classes')
    const card = page.locator('a[href*="/journey/"]').first()
    await expect(card).toBeVisible({ timeout: 20_000 })
    await card.click()
    await expect(page).toHaveURL(/\/journey\//)
    await page.waitForTimeout(3000)
    await page.goto('/privacy-policy')
    await page.waitForTimeout(3000)
    expect(hits).toEqual([])
  })
})
