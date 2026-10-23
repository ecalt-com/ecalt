import { expect, test } from '@playwright/test'
import { loadE2EEnv } from './env'

// Uses the storageState minted by auth.setup.ts (project "authed").
// Proves the custom-token session is accepted by the app + backend.
const env = loadE2EEnv()

test.describe('authenticated smoke', () => {
  test('session is restored (not bounced to the guest home)', async ({ page }) => {
    await page.goto('/')
    await expect(page).not.toHaveURL(/vercel\.com\/sso/)
    await expect(page.locator('#root')).not.toBeEmpty()

    // The app POSTs /api/v1/users with the restored id token on load; a working
    // session means the School nav (driven by GET /schools/mine) appears for the
    // test owner. If the owner account has family profiles this may route through
    // the profile picker first — tighten this once we have a real run.
    await expect(page.getByRole('link', { name: /school/i }).first()).toBeVisible()
  })

  test('/school dashboard shows the test school', async ({ page }) => {
    await page.goto('/school')
    await expect(page).not.toHaveURL(/vercel\.com\/sso/)
    // The active school's name heads the dashboard shell (the name also appears
    // in the school-switcher <option>, so scope to the heading).
    await expect(page.getByRole('heading', { name: env.testSchoolName })).toBeVisible()
  })
})
