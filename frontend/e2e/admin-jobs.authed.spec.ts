import { expect, test } from '@playwright/test'
import { call } from './adminctl.mjs'

// SC-805/806: ECALT admin → Schools → Background jobs shows queue health and
// lists jobs across schools; the API agrees with the panel.
test('admin sees the school job queue', async ({ page }) => {
  const r = await call('GET', '/api/v1/admin/schools/jobs?state=active')
  expect(r.ok, r.body).toBeTruthy()
  const { health } = JSON.parse(r.body)

  await page.goto('/admin')
  await page.getByRole('button', { name: /^Schools$/ }).first().click()
  const panel = page.getByTestId('school-jobs-panel')
  await expect(panel).toBeVisible({ timeout: 20_000 })
  await expect(panel).toContainText(`${health.queued} queued`)
  await panel.getByLabel('Job filter').selectOption('failed')
  await expect(panel.locator('li').or(panel.getByText('Nothing here.')).first()).toBeVisible()
  await page.waitForTimeout(800)
})
