import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

// §9 Assignments — student side (SC-507). A school student signs in via a minted
// custom token for a `stu_` uid (same technique as auth.setup, inline here since
// the shared owner session can't act as a student), lands on /my-classes, and
// sees the course assigned to their class. Then opens the student Journey view
// and confirms the marketplace/social actions are hidden. Runs in the `public`
// project (no owner storageState). Depends on assignments.authed leaving the
// course assigned — the API smoke / that spec do so.
const env = loadE2EEnv()
const STUDENT_UID = process.env.E2E_STUDENT_UID || 'stu_da8183dbcf452cb4' // Parijat, Physics @ Test Public School
const CLASS_NAME = 'Physics'
const COURSE = 'Understanding the Water Cycle'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 120 },
})

test('student home — assigned course visible, student journey hides social', async ({ page }) => {
  test.setTimeout(120_000)

  // Mint a custom token for the student uid (ecalt-dev service account).
  const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
  const adminApp = getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) })
  const customToken = await getAuth(adminApp).createCustomToken(STUDENT_UID)

  // Sign in on a blank, CSP-free page served on the real app origin, so the
  // Firebase session lands in this origin's localStorage (the app reads it).
  await page.route('**/__e2e_auth', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      headers: { 'content-security-policy': '' },
      body: '<!doctype html><html><head><meta charset="utf-8"><title>e2e student auth</title></head><body>signing in…</body></html>',
    }),
  )
  await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
  const signedUid = await page.evaluate(
    async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const app = appMod.initializeApp(config)
      const auth = authMod.getAuth(app)
      await authMod.setPersistence(auth, authMod.browserLocalPersistence)
      const cred = await authMod.signInWithCustomToken(auth, customToken)
      await cred.user.getIdToken(true)
      return cred.user.uid as string
    },
    { customToken, config: env.webConfig, sdkVersion: env.sdkVersion },
  )
  expect(signedUid).toBe(STUDENT_UID)

  // Load the student home.
  await page.goto('/my-classes')
  // The class section and the assigned course card both render.
  await expect(page.getByRole('heading', { name: CLASS_NAME })).toBeVisible({ timeout: 20_000 })
  const courseCard = page.getByRole('link').filter({ hasText: COURSE })
  await expect(courseCard.first()).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/\d+ steps/).first()).toBeVisible()

  // SC-703 disclosure: the school has teacher transcript access on (D4).
  await expect(page.getByText(/Your teacher can see your chats with the tutor/)).toBeVisible()

  // Open the student Journey view — social/marketplace actions must be hidden.
  await courseCard.first().click()
  await expect(page).toHaveURL(/\/journey\//, { timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Share' })).toHaveCount(0)
  await expect(page.getByText('More like this')).toHaveCount(0)

  // eslint-disable-next-line no-console
  console.log(`[student-home] ${STUDENT_UID} sees "${COURSE}" in ${CLASS_NAME}; social hidden on journey`)
})
