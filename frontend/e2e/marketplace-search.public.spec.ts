import { expect, test } from '@playwright/test'

// F2.4: the marketplace searches and sorts on the server. The query is sent as
// `q`, the sort as `sort`, and an empty result names what was searched for.
test('search and sort go to the server; no-match message names the query', async ({ page }) => {
  const seen: string[] = []
  page.on('request', (r) => { if (r.url().includes('/api/v1/journeys/marketplace')) seen.push(new URL(r.url()).search) })

  await page.goto('/marketplace')
  await expect(page.getByRole('heading', { name: 'Marketplace' })).toBeVisible()

  await page.getByLabel('Search the marketplace').fill('zzzzqqqq')
  await expect(page.getByText('No journeys match “zzzzqqqq”')).toBeVisible({ timeout: 15_000 })
  expect(seen.some((s) => s.includes('q=zzzzqqqq'))).toBeTruthy()

  await page.getByLabel('Sort journeys').selectOption('new')
  await expect.poll(() => seen.some((s) => s.includes('sort=new') && s.includes('q=zzzzqqqq'))).toBeTruthy()

  await page.getByLabel('Search the marketplace').fill('')
  await expect(page.getByText('No journeys match')).toHaveCount(0, { timeout: 15_000 })
})
