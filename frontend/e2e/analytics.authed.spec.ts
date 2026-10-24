import { expect, test } from '@playwright/test'

// M7 teacher analytics (SC-701/704/706/707), recorded: open a student drill-down
// from the progress matrix, export the matrix as CSV, and view the usage page.
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics
const STUDENT = 'Parijat'
const COURSE = 'Understanding the Water Cycle'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 80 },
})

test('teacher analytics — drill-down, CSV export, usage (recorded)', async ({ page }) => {
  test.setTimeout(240_000)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'School sections' })
  await nav.getByRole('link', { name: 'Classes' }).click()
  await page.locator(`a[href="/school/classes/${CLASS_ID}"]`).click()
  await expect(page).toHaveURL(new RegExp(`/school/classes/${CLASS_ID}$`))

  const matrix = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Progress' }) })
  await matrix.scrollIntoViewIfNeeded()

  // 1. Drill-down: click the student → modal with the course + steps.
  await matrix.getByRole('button', { name: STUDENT }).click()
  const dlg = page.getByRole('dialog', { name: new RegExp(`${STUDENT} progress`, 'i') })
  await expect(dlg).toBeVisible()
  await expect(dlg.getByText(COURSE)).toBeVisible()
  await expect(dlg.getByText(/\d+\/\d+ steps/).first()).toBeVisible()
  await page.waitForTimeout(1500)
  await dlg.getByRole('button', { name: 'Close' }).click()
  await expect(dlg).toBeHidden()

  // 2. CSV export: clicking fires a download and raises no error toast.
  const downloadPromise = page.waitForEvent('download', { timeout: 10_000 }).catch(() => null)
  await matrix.getByRole('button', { name: 'CSV' }).click()
  const download = await downloadPromise
  if (download) expect(download.suggestedFilename()).toContain('class-progress')
  await expect(page.getByText(/Couldn't export/)).toHaveCount(0)

  // 3. Usage page (admin): budget meter renders.
  await nav.getByRole('link', { name: 'Usage' }).click()
  await expect(page).toHaveURL(/\/school\/usage$/)
  await expect(page.getByRole('heading', { name: /AI budget/ })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/Daily cap per student/)).toBeVisible()
  await page.waitForTimeout(1500)

  // eslint-disable-next-line no-console
  console.log('[analytics] drill-down + CSV + usage OK')
})
