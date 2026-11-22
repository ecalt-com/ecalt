import { expect, test } from '@playwright/test'
import { call } from './adminctl.mjs'

// F1.6: link-preview crawlers (WhatsApp, Facebook, X…) don't run JavaScript, so
// Vercel routes them to the backend's share card; people still get the SPA.
const WHATSAPP = 'WhatsApp/2.23.20 A'

test('a crawler gets the journey title in og:title, a browser gets the app', async ({ request, page }) => {
  const res = await call('GET', '/api/v1/journeys')
  const journeys = (JSON.parse(res.body).journeys ?? []).filter((j: { is_curated?: boolean }) => !j.is_curated)
  test.skip(journeys.length === 0, 'the test account has no journeys on dev')
  const j = journeys[0]

  const crawl = await request.get(`/journey/${j.id}`, { headers: { 'user-agent': WHATSAPP } })
  expect(crawl.ok()).toBeTruthy()
  const body = await crawl.text()
  expect(body).toContain('property="og:title"')
  expect(body).toContain(j.title.slice(0, 20).replace(/&/g, '&amp;'))
  expect(body).toMatch(/og:image" content="https:\/\//)
  expect(body).not.toContain('<div id="root">')

  // A normal browser is not rewritten: the SPA mounts.
  await page.goto(`/journey/${j.id}`)
  await expect(page.locator('#root')).not.toBeEmpty()
})
