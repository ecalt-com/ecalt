import { expect, test as setup } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { assertAuthEnv, bypassHeaders, loadE2EEnv } from './env'

// How we sign in WITHOUT driving Google OAuth (which Google actively blocks for
// automation):
//
//   1. Mint a Firebase *custom token* for the test user with the ecalt-dev
//      service account (Admin SDK, done here in Node).
//   2. Open a blank, CSP-free page we serve on the REAL app origin
//      (https://ecalt-dev.vercel.app) via route interception. Same origin =
//      shared localStorage with the app; no CSP = we can import the Firebase
//      Web SDK from the CDN.
//   3. In that page, initialise the DEFAULT Firebase app with the dev *web*
//      config, force `browserLocalPersistence`, and `signInWithCustomToken`.
//      The SDK then writes `firebase:authUser:<apiKey>:[DEFAULT]` to
//      localStorage — which storageState captures (IndexedDB would not).
//   4. Save storageState. When an authed spec restores it and loads the app,
//      Firebase (whose default persistence searches localStorage too) finds the
//      session and refreshes the id token from the stored refresh token.

const env = loadE2EEnv()

setup('authenticate via custom token', async ({ browser }) => {
  assertAuthEnv(env)

  // 1. Mint the custom token (Admin SDK, ecalt-dev service account).
  const serviceAccount = JSON.parse(fs.readFileSync(env.serviceAccountPath, 'utf8'))
  const adminApp = getApps().length ? getApps()[0] : initializeApp({ credential: cert(serviceAccount) })
  const adminAuth = getAuth(adminApp)

  const uid = env.userUid || (await adminAuth.getUserByEmail(env.userEmail)).uid
  const customToken = await adminAuth.createCustomToken(uid)

  // 2. Fresh context carrying the Vercel bypass header.
  const context = await browser.newContext({ extraHTTPHeaders: bypassHeaders(env) })
  const page = await context.newPage()

  // Serve our own blank HTML (no CSP) on the app origin.
  await page.route('**/__e2e_auth', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html; charset=utf-8',
      headers: { 'content-security-policy': '' },
      body: '<!doctype html><html><head><meta charset="utf-8"><title>e2e auth</title></head><body>signing in…</body></html>',
    }),
  )
  const authUrl = new URL('/__e2e_auth', env.baseURL).toString()
  await page.goto(authUrl)

  // 3. Sign in inside that page with the Firebase Web SDK (CDN, version-matched).
  const result = await page.evaluate(
    async ({ customToken, config, sdkVersion }) => {
      const base = `https://www.gstatic.com/firebasejs/${sdkVersion}`
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const appMod: any = await import(/* @vite-ignore */ `${base}/firebase-app.js`)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const authMod: any = await import(/* @vite-ignore */ `${base}/firebase-auth.js`)
      const app = appMod.initializeApp(config) // DEFAULT app → storage key suffix "[DEFAULT]"
      const auth = authMod.getAuth(app)
      await authMod.setPersistence(auth, authMod.browserLocalPersistence)
      const cred = await authMod.signInWithCustomToken(auth, customToken)
      await cred.user.getIdToken(true)
      return { uid: cred.user.uid as string }
    },
    { customToken, config: env.webConfig, sdkVersion: env.sdkVersion },
  )
  expect(result.uid, 'custom-token sign-in should resolve to the test uid').toBe(uid)

  // Seed the dark-mode preference (user default) — rides in storageState.
  await page.evaluate(() => { try { localStorage.setItem('ecalt_theme', 'dark') } catch { /* ignore */ } })

  // 4. Confirm the SDK persisted the session to localStorage, then save it.
  const key = `firebase:authUser:${env.webConfig.apiKey}:[DEFAULT]`
  const stored = await page.evaluate((k) => localStorage.getItem(k), key)
  expect(stored, `Firebase session should be in localStorage under "${key}"`).toBeTruthy()

  fs.mkdirSync(path.dirname(env.storageStatePath), { recursive: true })
  await context.storageState({ path: env.storageStatePath })
  await context.close()

  // eslint-disable-next-line no-console
  console.log(`[auth.setup] signed in as uid=${uid}; storageState → ${env.storageStatePath}`)
})
