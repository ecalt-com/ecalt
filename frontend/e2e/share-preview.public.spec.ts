import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// F1.6: link-preview crawlers (WhatsApp, Facebook, X…) don't run JavaScript, so
// Vercel routes them to the backend's share card; people still get the SPA.
// Seeds a journey (with markup in its title) on the dev database and removes it afterwards.
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...args: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'share_fixture.py'), ...args], { stdio: 'pipe' }).toString()
const WHATSAPP = 'WhatsApp/2.23.20 A'

test('a crawler gets the journey title in og:title, a browser gets the app', async ({ request, page }) => {
  const stamp = Date.now()
  const uid = `e2e_share_${stamp}`
  const jid = `e2e-share-${stamp}`
  fixture('seed', uid, jid, 'E2E "Share" & <b>Card</b>')
  try {
    const crawl = await request.get(`/journey/${jid}`, { headers: { 'user-agent': WHATSAPP } })
    expect(crawl.ok()).toBeTruthy()
    const body = await crawl.text()
    expect(body).toContain('property="og:title" content="E2E &quot;Share&quot; &amp; &lt;b&gt;Card&lt;/b&gt; — ECALT"')
    expect(body).not.toContain('<b>Card</b>')
    expect(body).toContain(`og:url" content="`)
    expect(body).toMatch(/og:image" content="https:\/\/[^"]+og-image\.png"/)
    expect(body).not.toContain('id="root"')

    // A normal browser is not rewritten: the SPA mounts.
    await page.goto(`/journey/${jid}`)
    await expect(page.locator('#root')).not.toBeEmpty()
  } finally {
    fixture('teardown', uid)
  }
})
