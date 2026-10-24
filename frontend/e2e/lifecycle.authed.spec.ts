import { expect, test } from '@playwright/test'

// Full school lifecycle, recorded, meant to be watched (headed + slow-mo):
//   1. ECALT admin creates a brand-new school (Admin → Schools)
//   2. switch to an owned school (Test Public School)
//   3. create a class
//   4. add 3 students (with generated sign-in secrets), enrolled in the class
//   5. verify the roster
//
// A unique <stamp> tags everything so e2e/teardown.mjs can remove it after.
// Run via: STAMP=$(date +%s) E2E_STAMP=$STAMP npm run test:e2e -- lifecycle.authed.spec.ts --headed

const stamp = process.env.E2E_STAMP || String(Date.now())
const OWNED_SCHOOL = process.env.E2E_SCHOOL_NAME_OWNED || 'Test Public School'

const schoolName = `E2E Test School ${stamp}`
const className = `E2E Class ${stamp}`
const students = [`E2E Alice ${stamp}`, `E2E Bob ${stamp}`, `E2E Cara ${stamp}`]

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
  launchOptions: { slowMo: 350 },
})

test('school lifecycle — create school, class, students', async ({ page }) => {
  test.setTimeout(180_000)

  // ---- 1. Admin creates a school ----------------------------------------
  await page.goto('/admin')
  await page.getByRole('button', { name: 'Schools' }).click()
  await expect(page.getByRole('heading', { name: /^Schools \(/ })).toBeVisible()
  await page.getByPlaceholder('Delhi Public School').fill(schoolName)
  await page.getByRole('button', { name: 'Create school' }).click()
  await expect(page.getByText(`Created ${schoolName}`, { exact: false })).toBeVisible()

  // ---- 2. Switch to an owned school -------------------------------------
  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: OWNED_SCHOOL })
  await expect(page.getByRole('heading', { name: OWNED_SCHOOL })).toBeVisible()

  const nav = page.getByRole('navigation', { name: 'School sections' })

  // ---- 3. Create a class ------------------------------------------------
  await nav.getByRole('link', { name: 'Classes' }).click()
  await expect(page).toHaveURL(/\/school\/classes$/)
  await page.getByRole('button', { name: 'Create class' }).click()
  const classDialog = page.getByRole('dialog', { name: 'Create a class' })
  await classDialog.getByPlaceholder('6A Science').fill(className)
  await classDialog.getByRole('button', { name: 'Create class' }).click()
  // onCreated navigates to the new class detail page.
  await expect(page).toHaveURL(/\/school\/classes\/[0-9a-f-]{36}$/)

  // ---- 4. Add 3 students, enrolled in the class -------------------------
  await nav.getByRole('link', { name: 'Students' }).click()
  await expect(page).toHaveURL(/\/school\/students$/)
  for (const name of students) {
    await page.getByRole('button', { name: 'Add student' }).click()
    const dlg = page.getByRole('dialog', { name: 'Add a student' })
    await dlg.getByPlaceholder('First name + last initial').fill(name)
    const classToggle = dlg.getByRole('button', { name: className })
    if (await classToggle.isVisible().catch(() => false)) await classToggle.click()
    await dlg.getByRole('button', { name: 'Add student' }).click()
    // Success view shows the generated sign-in secret + a Done button.
    await page.getByRole('button', { name: 'Done' }).click()
    await expect(dlg).toBeHidden()
  }

  // ---- 5. Verify the roster ---------------------------------------------
  await page.getByPlaceholder('Search name or roll number').fill(String(stamp))
  await page.getByPlaceholder('Search name or roll number').press('Enter')
  for (const name of students) {
    await expect(page.getByText(name, { exact: false })).toBeVisible()
  }

  // eslint-disable-next-line no-console
  console.log(`[lifecycle] stamp=${stamp} — created school "${schoolName}", class "${className}", students: ${students.join(', ')}`)
})
