import { expect, test } from '@playwright/test'
import path from 'node:path'

// Course creation end-to-end, recorded: a teacher uploads a document, creates a
// course from it, reviews the AI outline, builds the step content, and publishes
// it to students. (Same flow as course-e2e.authed.spec.ts; separate so it can be
// recorded with a fresh document for the full-loop demo.)
const DOC_PATH = process.env.E2E_DOC_PATH
const DOC_NAME = DOC_PATH ? path.basename(DOC_PATH) : ''
const SCHOOL = process.env.E2E_SCHOOL_NAME_OWNED || 'Test Public School'
const COURSE_TITLE = process.env.E2E_COURSE_TITLE || 'Volcanoes'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 140 },
})

test('course builder — upload, outline, build, publish (recorded)', async ({ page }) => {
  test.setTimeout(300_000)
  expect(DOC_PATH, 'set E2E_DOC_PATH').toBeTruthy()

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'School sections' })

  // 1. Upload the material and wait for extraction.
  await nav.getByRole('link', { name: 'Materials' }).click()
  await page.locator('input[type="file"]').setInputFiles(DOC_PATH!)
  await expect(page.getByText(DOC_NAME)).toBeVisible({ timeout: 30_000 })
  const row = page.getByText(DOC_NAME).locator('xpath=ancestor::div[contains(@class,"p-4")][1]')
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 150_000 })

  // 2. Create a course from it.
  await nav.getByRole('link', { name: 'Courses' }).click()
  await page.getByRole('button', { name: 'New course' }).click()
  await expect(page).toHaveURL(/\/school\/courses\/new$/)
  await page.getByText(DOC_NAME).click()
  await page.getByPlaceholder('The Water Cycle').fill(COURSE_TITLE)
  await page.getByRole('button', { name: 'Continue to estimate' }).click()
  await expect(page.getByText('Ready to generate the outline')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Generate outline' }).click()

  // 3. Review outline → approve → build.
  await expect(page.getByRole('button', { name: /Approve outline & build/ })).toBeVisible({ timeout: 150_000 })
  await page.getByRole('button', { name: /Approve outline & build/ }).click()

  // 4. Build finishes → Publish is offered.
  await expect(page.getByRole('button', { name: 'Publish' })).toBeVisible({ timeout: 200_000 })
  await page.getByRole('button', { name: 'Publish' }).click()
  const dlg = page.getByRole('dialog', { name: 'Publish course' })
  await expect(dlg).toBeVisible()
  const ack = dlg.getByRole('checkbox')
  if (await ack.isVisible().catch(() => false)) await ack.check()
  await dlg.getByRole('button', { name: 'Publish to students' }).click()
  await expect(dlg).toBeHidden({ timeout: 30_000 })

  // 5. The library shows a published course.
  await nav.getByRole('link', { name: 'Courses' }).click()
  await expect(page).toHaveURL(/\/school\/courses$/)
  await expect(page.getByText(/Published/).first()).toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(1500)

  // eslint-disable-next-line no-console
  console.log(`[course-create] published a course from ${DOC_NAME}`)
})
