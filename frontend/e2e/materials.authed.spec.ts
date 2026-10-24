import { expect, test } from '@playwright/test'
import path from 'node:path'

// Records the document-upload flow (M3) in the Materials tab: pick a real .docx,
// upload it to Supabase Storage via a signed URL, and watch the backend extract
// it to "Ready". This is the source material the AI course builder uses.
//
// Run: E2E_DOC_PATH="/abs/E2E Photosynthesis <stamp>.docx" \
//      npm run test:e2e -- materials.authed.spec.ts --headed

const DOC_PATH = process.env.E2E_DOC_PATH
const DOC_NAME = DOC_PATH ? path.basename(DOC_PATH) : ''
const SCHOOL = process.env.E2E_SCHOOL_NAME_OWNED || 'Test Public School'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 250 },
})

test('materials — upload a document and extract to Ready', async ({ page }) => {
  test.setTimeout(180_000)
  expect(DOC_PATH, 'set E2E_DOC_PATH to the .docx to upload').toBeTruthy()

  // Switch to the target school, open Materials.
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  await page.getByRole('navigation', { name: 'School sections' }).getByRole('link', { name: 'Materials' }).click()
  await expect(page).toHaveURL(/\/school\/materials$/)
  await expect(page.getByText('Upload document')).toBeVisible()

  // Upload (the file input is hidden inside the Upload label).
  await page.locator('input[type="file"]').setInputFiles(DOC_PATH!)

  // The row for our file appears, then its status settles on "Ready" once the
  // backend worker finishes extraction (scoped to this document's row).
  await expect(page.getByText(DOC_NAME)).toBeVisible({ timeout: 30_000 })
  const row = page.getByText(DOC_NAME).locator('xpath=ancestor::div[contains(@class,"p-4")][1]')
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 150_000 })

  // eslint-disable-next-line no-console
  console.log(`[materials] uploaded + extracted: ${DOC_NAME} in ${SCHOOL}`)
})
