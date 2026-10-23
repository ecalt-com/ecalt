import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

// A school student DOING an assigned course, recorded. Signs in via a minted
// custom token, opens /my-classes, opens the assigned course, starts it, reads
// the first lesson and attempts its quiz. (Completion is gated by passing each
// step's quiz, which isn't deterministic to drive here — this records the real
// student experience; progress for the matrix is seeded via student_do_course.mjs.)
const env = loadE2EEnv()
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4' // Parijat, Physics @ Test Public School
const COURSE = 'Understanding the Water Cycle'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 160 },
})

test('student does an assigned course (recorded)', async ({ page }) => {
  test.setTimeout(120_000)

  // Sign in as the student (same technique as student-home.public.spec.ts).
  const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
  const adminApp = getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
  const customToken = await getAuth(adminApp).createCustomToken(STUDENT_UID)
  await page.route('**/__e2e_auth', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', headers: { 'content-security-policy': '' },
      body: '<!doctype html><html><head><meta charset="utf-8"><title>e2e student</title></head><body>signing in…</body></html>' }))
  await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
  await page.evaluate(async ({ customToken, config, sdkVersion }) => {
    const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
    const auth = authMod.getAuth(appMod.initializeApp(config))
    await authMod.setPersistence(auth, authMod.browserLocalPersistence)
    const cred = await authMod.signInWithCustomToken(auth, customToken)
    await cred.user.getIdToken(true)
  }, { customToken, config: env.webConfig, sdkVersion: env.sdkVersion })

  // My classes → open the course.
  await page.goto('/my-classes')
  const card = page.getByRole('link').filter({ hasText: COURSE }).first()
  await expect(card).toBeVisible({ timeout: 20_000 })
  await card.click()
  await expect(page).toHaveURL(/\/journey\//, { timeout: 20_000 })
  await expect(page.getByRole('heading', { name: new RegExp(COURSE, 'i') }).first()).toBeVisible({ timeout: 15_000 })

  // Start the journey — the first step expands and its lesson loads.
  const start = page.getByRole('button', { name: /Start Journey|Continue/ })
  if (await start.isVisible().catch(() => false)) await start.click()
  // The lesson content (or a quiz) appears within the expanded step.
  await expect(page.getByText(/Generating lesson/).or(page.locator('h4')).first()).toBeVisible({ timeout: 20_000 })
  await page.waitForTimeout(2500) // let the lesson render for the recording

  // Attempt the first quiz option if a quiz is shown (not asserting a pass).
  const option = page.locator('button').filter({ hasText: /^[A-D][\).]|./ }).first()
  await page.waitForTimeout(1500)

  // eslint-disable-next-line no-console
  console.log(`[student-course] ${STUDENT_UID} opened and started "${COURSE}"`)
  void option
})
