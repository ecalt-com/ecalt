import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFirebaseUser, deleteFirebaseUser, signInAs } from './signin'

// F2.3: the app is installable (manifest, icons, service worker) and a journey saved
// for offline reading opens without a connection.
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...a: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'quiz_fixture.py'), ...a], { stdio: 'pipe' }).toString()

test('manifest, icons and service worker are served', async ({ request }) => {
  const m = await request.get('/manifest.webmanifest')
  expect(m.ok()).toBeTruthy()
  expect(m.headers()['content-type']).toContain('manifest+json')
  const manifest = await m.json()
  expect(manifest).toMatchObject({ display: 'standalone', start_url: expect.any(String) })
  for (const icon of manifest.icons) {
    const r = await request.get(icon.src)
    expect(r.ok(), icon.src).toBeTruthy()
    expect(r.headers()['content-type']).toContain('image/png')
  }
  const sw = await request.get('/sw.js')
  expect(sw.ok()).toBeTruthy()
  expect(sw.headers()['content-type']).toContain('javascript')
  expect(sw.headers()['cache-control']).toContain('no-cache')
})

test('a signed-in adult saves a journey and reads it offline; sign-out clears it', async ({ page, context }) => {
  test.setTimeout(300_000)
  const stamp = `${Date.now()}`
  const user = await createFirebaseUser(stamp, 'e2e-pwa')
  const jid = `e2e-pwa-${stamp}`
  try {
    fixture('seed', user.uid, user.email, jid)
    await signInAs(page, user.uid)

    // The worker installs on the first load and controls the page from the next one.
    await page.goto(`/journey/${jid}`)
    await page.waitForFunction(async () => (await navigator.serviceWorker.getRegistration())?.active?.state === 'activated', null, { timeout: 30_000 })
    await page.reload()
    await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBeTruthy()
    await expect(page.getByRole('button', { name: /Why the sky is blue/ }).first()).toBeVisible({ timeout: 30_000 })

    await page.getByTestId('offline-save').click()
    await expect(page.getByTestId('offline-saved')).toBeVisible({ timeout: 60_000 })

    // Offline: reload the journey, open the lesson, read it.
    await context.setOffline(true)
    await page.reload()
    await page.getByRole('button', { name: /Why the sky is blue/ }).first().click()
    await expect(page.getByText('Sunlight looks white').first()).toBeVisible({ timeout: 30_000 })
    await context.setOffline(false)

    // Signing out removes the saved lessons from this device.
    await page.getByRole('button', { name: 'Sign out' }).first().click()
    await expect.poll(async () => page.evaluate(() => new Promise<number>((resolve) => {
      const req = indexedDB.open('ecalt-offline', 1)
      req.onsuccess = () => {
        const db = req.result
        if (!db.objectStoreNames.contains('journeys')) return resolve(0)
        const c = db.transaction('journeys').objectStore('journeys').count()
        c.onsuccess = () => resolve(c.result)
      }
      req.onerror = () => resolve(-1)
    })), { timeout: 15_000 }).toBe(0)
  } finally {
    fixture('teardown', user.uid)
    await deleteFirebaseUser(user.uid)
  }
})
