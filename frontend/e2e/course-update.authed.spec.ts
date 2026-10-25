import { expect, test } from '@playwright/test'

// M6 course update-from-document (SC-606), recorded: open a published course,
// run "Update from a document" (supplement mode) against a ready document, wait
// for the propose-update job, and review the proposed changes. Does not apply,
// so the shared published fixture stays draft-free.
const SCHOOL = 'Test Public School'
const COURSE = 'Understanding the Water Cycle'
const DOC = 'volcanoes.docx'

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 80 },
})

test('course update — propose from a document + review (recorded)', async ({ page }) => {
  test.setTimeout(300_000)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await expect(page.getByRole('heading', { name: SCHOOL })).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'School sections' })
  await nav.getByRole('link', { name: 'Courses' }).click()

  // Open the PUBLISHED water-cycle course (not the "(copy)" draft).
  await page.getByRole('button').filter({ hasText: COURSE }).filter({ hasText: /Published/ }).first().click()
  await expect(page.getByRole('heading', { name: COURSE })).toBeVisible({ timeout: 20_000 })

  // Entry point on the published-course view.
  const openBtn = page.getByRole('button', { name: /Update from a document/i })
  await expect(openBtn).toBeVisible({ timeout: 20_000 })
  await openBtn.click()

  const dlg = page.getByRole('dialog', { name: /Update from a document/i })
  await expect(dlg).toBeVisible()
  await expect(dlg.getByText('Revise', { exact: true })).toBeVisible()
  await expect(dlg.getByText('Supplement', { exact: true })).toBeVisible()

  // Supplement mode + the volcanoes document, then propose.
  await dlg.getByText('Supplement', { exact: true }).click()
  await dlg.locator('select').selectOption({ label: DOC }).catch(() => {})
  await dlg.getByRole('button', { name: /Propose changes/i }).click()

  // Wait for the job: either a review with an Apply button, or "no changes".
  const apply = dlg.getByRole('button', { name: /Apply/i })
  const empty = dlg.getByText(/No changes suggested/i)
  await expect(apply.or(empty)).toBeVisible({ timeout: 240_000 })

  // If changes were proposed, exercise the review UI (compare + accept). Don't
  // apply — keep the published course free of a lingering draft.
  if (await apply.isVisible()) {
    const accept = dlg.getByRole('button', { name: 'Accept' }).first()
    await expect(accept).toBeVisible()
    const compare = dlg.getByText('Compare').first()
    if (await compare.isVisible().catch(() => false)) await compare.click()
    await accept.click()
    await expect(dlg.getByText(/accepted/i)).toBeVisible()
  }
  await page.waitForTimeout(1500)

  // eslint-disable-next-line no-console
  console.log('[course-update] propose + review OK')
})
