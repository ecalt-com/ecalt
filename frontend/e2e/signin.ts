// Shared helpers for specs that sign in as a throwaway Firebase user (ecalt-dev):
// mint a custom token with the service account and sign in on a blank, CSP-free
// page served from the real app origin, so the session lands in localStorage.
import { expect, type Page } from '@playwright/test'
import fs from 'node:fs'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { loadE2EEnv } from './env'

const env = loadE2EEnv()

export const adminAuth = () =>
  getAuth(getApps().length ? getApps()[0] : initializeApp({ credential: cert(JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))) }))

export async function createFirebaseUser(stamp: string, prefix = 'e2e') {
  const email = `${prefix}-${stamp}@example.com`
  const user = await adminAuth().createUser({ email, emailVerified: true, displayName: 'E2E User' })
  return { uid: user.uid, email }
}

export const deleteFirebaseUser = (uid: string) => adminAuth().deleteUser(uid).catch(() => {})

export async function signInAs(page: Page, uid: string) {
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
  const signed = await page.evaluate(
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
      return cred.user.uid as string
    },
    { customToken, config: env.webConfig, sdkVersion: env.sdkVersion },
  )
  expect(signed).toBe(uid)
}
