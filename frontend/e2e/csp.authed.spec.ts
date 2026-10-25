import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

// #25: the CSP no longer allows inline scripts. These tests browse the main
// pages (signed-in owner, then a school student) and fail on any blocked
// script, and prove the policy is live: an injected inline handler must not run.
const env = loadE2EEnv()
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4'

type Violation = { directive: string; blocked: string; sample: string; page: string }

async function watchCsp(page: Page) {
  await page.addInitScript(() => {
    ;(window as any).__csp = []
    document.addEventListener('securitypolicyviolation', (e) => {
      ;(window as any).__csp.push({ directive: e.effectiveDirective, blocked: e.blockedURI, sample: e.sample, page: location.pathname })
    })
  })
}

async function violations(page: Page): Promise<Violation[]> {
  return page.evaluate(() => (window as any).__csp || [])
}

// Script violations are the ones this change can cause; collect them across pages.
async function visit(page: Page, path: string, seen: Violation[]) {
  await page.goto(path)
  await expect(page.locator('#root')).not.toBeEmpty()
  await page.waitForLoadState('networkidle').catch(() => {})
  seen.push(...(await violations(page)).filter((v) => v.directive.startsWith('script-src')))
}

test('policy is served without unsafe-inline for scripts', async ({ request }) => {
  const r = await request.get('/')
  const csp = r.headers()['content-security-policy'] || ''
  const scriptSrc = csp.split(';').map((d) => d.trim()).find((d) => d.startsWith('script-src')) || ''
  expect(scriptSrc).toContain("'self'")
  expect(scriptSrc).not.toContain("'unsafe-inline'")
  expect(csp).toContain("object-src 'none'")
})

test('owner pages run with no blocked scripts', async ({ page }) => {
  test.setTimeout(180_000)
  await watchCsp(page)
  const seen: Violation[] = []
  for (const p of ['/', '/learn', '/pricing', '/journeys', '/explore', '/profile', '/admin',
    '/school', '/school/classes', '/school/courses', '/school/materials', '/school/usage', '/school/settings']) {
    await visit(page, p, seen)
  }

  // A course page (lesson content, diagrams).
  await page.goto('/school/courses')
  const course = page.locator('a[href*="/school/courses/"]').first()
  if (await course.isVisible().catch(() => false)) {
    await course.click()
    await page.waitForLoadState('networkidle').catch(() => {})
    seen.push(...(await violations(page)).filter((v) => v.directive.startsWith('script-src')))
  }

  // Razorpay checkout script loads the same way the app loads it.
  const rzp = await page.evaluate(() => new Promise<boolean>((resolve) => {
    const s = document.createElement('script')
    s.src = 'https://checkout.razorpay.com/v1/checkout.js'
    s.onload = () => resolve(!!(window as any).Razorpay)
    s.onerror = () => resolve(false)
    document.body.appendChild(s)
  }))
  expect(rzp, 'Razorpay checkout.js should load under the CSP').toBe(true)
  seen.push(...(await violations(page)).filter((v) => v.directive.startsWith('script-src')))

  expect(seen, JSON.stringify(seen, null, 2)).toEqual([])
})

test('injected inline handlers do not run', async ({ page }) => {
  await watchCsp(page)
  await page.goto('/')
  await expect(page.locator('#root')).not.toBeEmpty()
  await page.evaluate(() => {
    const d = document.createElement('div')
    d.innerHTML = '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" onload="window.__xss=1"><svg onload="window.__xss=2"></svg>'
    document.body.appendChild(d)
    const s = document.createElement('script')
    s.textContent = 'window.__xss = 3'
    document.body.appendChild(s)
  })
  await page.waitForTimeout(500)
  expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined()
  const v = await violations(page)
  expect(v.some((x) => x.directive === 'script-src-attr' || x.directive === 'script-src-elem')).toBe(true)
})

test.describe('student', () => {
  test.use({ storageState: { cookies: [], origins: [{ origin: env.baseURL, localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] } })

  test('student pages run with no blocked scripts', async ({ page }) => {
    test.setTimeout(120_000)
    const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
    const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
    const customToken = await getAuth(app).createCustomToken(STUDENT_UID)
    // Sign-in stub page (its own empty CSP so the CDN SDK import works); the real pages after it get the real CSP.
    await page.route('**/__e2e_auth', (route) =>
      route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', headers: { 'content-security-policy': '' },
        body: '<!doctype html><html><head><meta charset="utf-8"></head><body>signing in…</body></html>' }))
    await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
    await page.evaluate(async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const auth = authMod.getAuth(appMod.initializeApp(config))
      await authMod.setPersistence(auth, authMod.browserLocalPersistence)
      await authMod.signInWithCustomToken(auth, customToken)
    }, { customToken, config: env.webConfig, sdkVersion: env.sdkVersion })

    await watchCsp(page)
    const seen: Violation[] = []
    await visit(page, '/my-classes', seen)

    // Open an assigned course and its first lesson.
    const card = page.locator('a[href*="/journey/"]').first()
    await expect(card).toBeVisible({ timeout: 20_000 })
    await card.click()
    await expect(page).toHaveURL(/\/journey\//)
    await page.waitForLoadState('networkidle').catch(() => {})
    const start = page.getByRole('button', { name: /Start Journey|Continue/ })
    if (await start.isVisible().catch(() => false)) await start.click()
    await page.waitForTimeout(4000)
    seen.push(...(await violations(page)).filter((v) => v.directive.startsWith('script-src')))

    // Public sign-in pages (Firebase auth helpers).
    await visit(page, '/class', seen)
    await visit(page, '/sign-in', seen)

    expect(seen, JSON.stringify(seen, null, 2)).toEqual([])
  })
})
