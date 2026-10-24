import { expect, test } from '@playwright/test'

// SC-703 teacher side (recorded): from the progress-matrix student drill-down,
// the "Tutor conversations" section lists the student's tutor chats; clicking
// one opens its messages (read endpoint, audited server-side). NOTE: the dev
// tutor model currently errors, so seeded conversations have no messages — the
// panel shows "No messages"; the wiring (list + read + render) is what's verified.
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics
const STUDENT = 'Parijat'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 80 },
})

test('teacher reads a student tutor transcript (recorded)', async ({ page }) => {
  test.setTimeout(240_000)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  await page.getByRole('navigation', { name: 'School sections' }).getByRole('link', { name: 'Classes' }).click()
  await page.locator(`a[href="/school/classes/${CLASS_ID}"]`).click()
  await expect(page).toHaveURL(new RegExp(`/school/classes/${CLASS_ID}$`))

  const matrix = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Progress' }) })
  await matrix.scrollIntoViewIfNeeded()
  await matrix.getByRole('button', { name: STUDENT }).click()

  const dlg = page.getByRole('dialog', { name: new RegExp(`${STUDENT} progress`, 'i') })
  await expect(dlg).toBeVisible()

  // The tutor-transcripts section (D4 is on for this school).
  await expect(dlg.getByRole('heading', { name: 'Tutor conversations' })).toBeVisible({ timeout: 15_000 })
  const conv = dlg.getByRole('button', { name: /Tutor chat/ }).first()
  await expect(conv).toBeVisible()
  await conv.click()
  // Opening it loads the conversation (messages, or "No messages" on dev).
  await expect(dlg.getByText(/No messages|^Student$|^Tutor$/).first()).toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(1500)

  // eslint-disable-next-line no-console
  console.log('[transcripts] teacher opened a student tutor conversation')
})
