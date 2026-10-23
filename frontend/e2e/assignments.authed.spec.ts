import { expect, test } from '@playwright/test'

// §9 Assignments — teacher side (SC-507). As the school owner, open a class's
// Courses card, verify an assigned published course with its progress summary,
// then exercise the full round-trip: unassign → reassign via the form → toggle
// the tutor / quiz-required settings. Leaves the course assigned at the end so
// the student-home spec can see it. Recorded (dark mode via the config).
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics
const COURSE = 'Understanding the Water Cycle'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 120 },
})

test('class courses — assign, progress, unassign/reassign, settings', async ({ page }) => {
  test.setTimeout(120_000)

  // Set the active school, then open the class.
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  await page.getByRole('navigation', { name: 'School sections' }).getByRole('link', { name: 'Classes' }).click()
  await page.locator(`a[href="/school/classes/${CLASS_ID}"]`).click()
  await expect(page).toHaveURL(new RegExp(`/school/classes/${CLASS_ID}$`))

  // Scope to the Courses card.
  const card = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Courses' }) })
  await expect(card).toBeVisible()

  // 1. The course is assigned (API smoke left it so) with a progress summary.
  const item = card.locator('li').filter({ hasText: COURSE })
  await expect(item).toBeVisible({ timeout: 15_000 })
  await expect(item.getByText(/\d+ students? ·/)).toBeVisible()

  // 2. Unassign it: trash → Remove. It disappears and becomes assignable again.
  await item.getByRole('button', { name: `Unassign ${COURSE}` }).click()
  await item.getByRole('button', { name: 'Remove' }).click()
  await expect(card.locator('li').filter({ hasText: COURSE })).toHaveCount(0, { timeout: 15_000 })

  // 3. Reassign via the form: pick the course, set a due date, enable quiz, assign.
  await card.locator('select').selectOption({ label: COURSE })
  const due = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10)
  await card.locator('input[type="date"]').first().fill(due)
  await card.getByRole('button', { name: 'Assign' }).click()

  // 4. It reappears with the summary; the inline setting pills show.
  const re = card.locator('li').filter({ hasText: COURSE })
  await expect(re).toBeVisible({ timeout: 15_000 })
  await expect(re.getByText(/\d+ students? ·/)).toBeVisible()
  await expect(re.getByRole('button', { name: /^Tutor (on|off)$/ })).toBeVisible()

  // 5. Toggle the tutor pill off → on and confirm the label flips.
  const tutorPill = re.getByRole('button', { name: /^Tutor (on|off)$/ })
  await expect(tutorPill).toHaveText('Tutor on')
  await tutorPill.click()
  await expect(re.getByRole('button', { name: 'Tutor off' })).toBeVisible({ timeout: 15_000 })
  await re.getByRole('button', { name: 'Tutor off' }).click()
  await expect(re.getByRole('button', { name: 'Tutor on' })).toBeVisible({ timeout: 15_000 })

  // eslint-disable-next-line no-console
  console.log(`[assignments] round-trip OK for "${COURSE}" in class ${CLASS_ID}`)
})
