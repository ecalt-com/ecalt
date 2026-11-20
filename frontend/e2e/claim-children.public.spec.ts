import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

// Issue #23: a teen approved through the emailed consent link has no family
// link, so their parent's dashboard was empty. The Family page now calls
// POST /family/claim-children when the list is empty and links them.
// Seeds fresh dev-DB rows (claim_children_fixture.py) and fresh ecalt-dev
// Firebase users for each run, and removes both afterwards.
const env = loadE2EEnv()
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const FIXTURE = path.join(DIR, 'claim_children_fixture.py')
const fixture = (...args: string[]) => execFileSync(PY, ['-I', FIXTURE, ...args], { stdio: 'pipe' }).toString()

const sa = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
const adminAuth = () => getAuth(getApps().length ? getApps()[0] : initializeApp({ credential: cert(sa) }))

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
})

async function signInAs(page: Page, uid: string) {
  const customToken = await adminAuth().createCustomToken(uid)
  await page.route('**/__e2e_auth', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      headers: { 'content-security-policy': '' },
      body: '<!doctype html><html><head><meta charset="utf-8"></head><body>signing in…</body></html>',
    }),
  )
  await page.goto(new URL('/__e2e_auth', env.baseURL).toString())
  await page.evaluate(
    async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const auth = authMod.getAuth(appMod.initializeApp(config))
      await authMod.setPersistence(auth, authMod.browserLocalPersistence)
      const cred = await authMod.signInWithCustomToken(auth, customToken)
      await cred.user.getIdToken(true)
    },
    { customToken, config: env.webConfig, sdkVersion: env.sdkVersion },
  )
}

async function newParent(stamp: string) {
  const email = `e2e-claim-${stamp}@example.com`
  const user = await adminAuth().createUser({ email, emailVerified: true, displayName: 'E2E Parent' })
  return { uid: user.uid, email }
}

test('empty dashboard auto-links a teen approved by email', async ({ page }) => {
  test.setTimeout(120_000)
  const stamp = `${Date.now()}`
  const teenUid = `e2e_teen_${stamp}`
  const teenName = `E2E Teen ${stamp.slice(-5)}`
  const parent = await newParent(stamp)
  try {
    fixture('seed', parent.uid, parent.email, teenUid, teenName)
    await signInAs(page, parent.uid)
    await page.goto('/family')

    await expect(page.getByTestId('claim-note')).toContainText(`We found and linked ${teenName}`, { timeout: 30_000 })
    await expect(page.getByText(teenName, { exact: true })).toBeVisible()
    await expect(page.getByText('No children linked yet')).toHaveCount(0)

    // Idempotent: a reload shows the child without re-claiming (no note).
    await page.reload()
    await expect(page.getByText(teenName, { exact: true })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('claim-note')).toHaveCount(0)
  } finally {
    fixture('teardown', parent.uid, teenUid)
    await adminAuth().deleteUser(parent.uid).catch(() => {})
  }
})

test('manual check explains a non-matching sign-in email', async ({ page }) => {
  test.setTimeout(120_000)
  const stamp = `${Date.now()}n`
  const parent = await newParent(stamp)
  try {
    fixture('seed', parent.uid, parent.email, '-')
    await signInAs(page, parent.uid)
    await page.goto('/family')

    await expect(page.getByText('No children linked yet')).toBeVisible({ timeout: 30_000 })
    await page.getByRole('button', { name: "I already approved my child's account" }).click()
    await expect(page.getByTestId('claim-note')).toContainText(`No approved child accounts are tied to ${parent.email}`)
  } finally {
    fixture('teardown', parent.uid)
    await adminAuth().deleteUser(parent.uid).catch(() => {})
  }
})
