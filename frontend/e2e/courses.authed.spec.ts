import { expect, test } from '@playwright/test'

// SC-410 smoke: the course library + create wizard render (dark mode by default).
const SCHOOL = process.env.E2E_SCHOOL_NAME_OWNED || 'Test Public School'

test('course builder — library + create wizard render', async ({ page }) => {
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()

  const nav = page.getByRole('navigation', { name: 'School sections' })
  await nav.getByRole('link', { name: 'Courses' }).click()
  await expect(page).toHaveURL(/\/school\/courses$/)
  await expect(page.getByRole('button', { name: 'New course' })).toBeVisible()

  await page.getByRole('button', { name: 'New course' }).click()
  await expect(page).toHaveURL(/\/school\/courses\/new$/)
  await expect(page.getByText('Source material')).toBeVisible()
  await expect(page.getByText('Course setup')).toBeVisible()

  // Confirm dark mode is actually on.
  const isDark = await page.evaluate(() => document.documentElement.classList.contains('dark'))
  expect(isDark, 'app should render in dark mode').toBe(true)
})
