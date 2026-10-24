import { expect, test } from '@playwright/test'
import { loadE2EEnv } from './env'

// End-to-end walk-through of the school staff area, recorded to video.
// Non-destructive: it navigates every section and opens (then closes) the
// create dialogs WITHOUT submitting, so no test data is created on dev.
//
// Run just this (with the recording settings below):
//   npm run test:e2e -- school-tour.authed.spec.ts
// The webm lands in e2e/.output/<test>/video.webm (also embedded in the report).

const env = loadE2EEnv()

// Force a kept recording + a watchable pace for this file only.
test.use({
  video: { mode: 'on', size: { width: 1280, height: 800 } },
  viewport: { width: 1280, height: 800 },
  launchOptions: { slowMo: 300 },
})

test('school feature — full staff-area tour', async ({ page }) => {
  // ---- 1. Dashboard ------------------------------------------------------
  await page.goto('/school')
  await expect(page).not.toHaveURL(/vercel\.com\/sso/)
  await expect(page.getByRole('heading', { name: env.testSchoolName })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Getting started' })).toBeVisible()

  const nav = page.getByRole('navigation', { name: 'School sections' })

  // ---- 2. Classes — open & close the "Create a class" dialog -------------
  await nav.getByRole('link', { name: 'Classes' }).click()
  await expect(page).toHaveURL(/\/school\/classes$/)
  await page.getByRole('button', { name: 'Create class' }).click()
  const classDialog = page.getByRole('dialog', { name: 'Create a class' })
  await expect(classDialog).toBeVisible()
  await classDialog.getByPlaceholder('6A Science').fill('6A Science (demo — not saved)')
  await classDialog.getByRole('button', { name: 'Close' }).click()
  await expect(classDialog).toBeHidden()

  // ---- 3. Students -------------------------------------------------------
  await nav.getByRole('link', { name: 'Students' }).click()
  await expect(page).toHaveURL(/\/school\/students$/)
  await expect(page.getByPlaceholder('Search name or roll number')).toBeVisible()
  // Show the add-student flow when the owner can manage (DPA accepted).
  const addStudent = page.getByRole('button', { name: 'Add student' })
  if (await addStudent.isVisible().catch(() => false)) {
    await addStudent.click()
    const addDialog = page.getByRole('dialog')
    await expect(addDialog).toBeVisible()
    await addDialog.getByPlaceholder('First name + last initial').fill('Demo Student (not saved)')
    await addDialog.getByRole('button', { name: 'Close' }).click()
    await expect(addDialog).toBeHidden()
  }

  // ---- 4. Materials (document ingestion for the course builder) ----------
  await nav.getByRole('link', { name: 'Materials' }).click()
  await expect(page).toHaveURL(/\/school\/materials$/)
  await expect(page.getByText('Upload document')).toBeVisible()

  // ---- 5. Staff ----------------------------------------------------------
  await nav.getByRole('link', { name: 'Staff' }).click()
  await expect(page).toHaveURL(/\/school\/staff$/)
  await expect(page.getByRole('heading', { name: /^Staff \(/ })).toBeVisible()

  // ---- 6. Settings -------------------------------------------------------
  await nav.getByRole('link', { name: 'Settings' }).click()
  await expect(page).toHaveURL(/\/school\/settings$/)
  await expect(page.getByRole('heading', { name: 'Data processing agreement' })).toBeVisible()

  // ---- back to Dashboard -------------------------------------------------
  await nav.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page).toHaveURL(/\/school$/)
  await expect(page.getByRole('heading', { name: 'Getting started' })).toBeVisible()
})
