import { expect, test } from '@playwright/test'

// No login required. Proves the Vercel bypass works (we reach the app, not the
// vercel.com/sso wall) and the SPA mounts.
test.describe('public smoke', () => {
  test('home page loads and the SPA mounts', async ({ page }) => {
    await page.goto('/')

    // The bypass worked: we are still on the app origin, not redirected to SSO.
    await expect(page).not.toHaveURL(/vercel\.com\/sso/)
    await expect(page).toHaveTitle(/ECALT/i)

    // React mounted into #root.
    const root = page.locator('#root')
    await expect(root).toBeVisible()
    await expect(root).not.toBeEmpty()
  })

  test('student class sign-in page renders', async ({ page }) => {
    await page.goto('/class')
    await expect(page).not.toHaveURL(/vercel\.com\/sso/)
    await expect(page.locator('#root')).not.toBeEmpty()
  })
})

test.describe('staff sign-in', () => {
  test('signed-out /school offers staff sign-in instead of bouncing home', async ({ page }) => {
    await page.goto('/school')
    await expect(page.getByRole('heading', { name: 'Sign in to your school' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible()
    // Microsoft appears only when VITE_MICROSOFT_SIGNIN=true on the deployment.
    if (await page.getByTestId('microsoft-sign-in').count()) {
      await expect(page.getByTestId('microsoft-sign-in')).toHaveText(/Continue with Microsoft/)
    }
  })
})
