import { expect, test } from '@playwright/test'

// §10 Class progress matrix (SC-505), teacher side, recorded. Opens the Physics
// class and checks the Progress card shows the students × assigned-courses grid.
// Run student_do_course.mjs beforehand so a student shows real progress.
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics
const COURSE = 'Understanding the Water Cycle'
const STUDENT = 'Parijat'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 150 },
})

test('class progress matrix shows students × courses (recorded)', async ({ page }) => {
  test.setTimeout(120_000)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  await page.getByRole('navigation', { name: 'School sections' }).getByRole('link', { name: 'Classes' }).click()
  await page.locator(`a[href="/school/classes/${CLASS_ID}"]`).click()
  await expect(page).toHaveURL(new RegExp(`/school/classes/${CLASS_ID}$`))

  // The Progress card with the matrix.
  const card = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Progress' }) })
  await expect(card).toBeVisible()
  await card.scrollIntoViewIfNeeded()

  // The assigned course is a column header and the student is a row.
  await expect(card.getByText(COURSE)).toBeVisible({ timeout: 15_000 })
  await expect(card.getByText(STUDENT)).toBeVisible()

  // At least one progress cell is rendered (title "N of M steps").
  await expect(card.locator('[title*="steps"]').first()).toBeVisible()
  await page.waitForTimeout(1500) // hold the matrix on screen for the recording

  // eslint-disable-next-line no-console
  console.log(`[class-progress] matrix shows ${STUDENT} × ${COURSE}`)
})
