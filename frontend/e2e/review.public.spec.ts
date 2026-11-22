import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFirebaseUser, deleteFirebaseUser, signInAs } from './signin'

// F1.3 spaced review: a learner with a finished step that is due sees the card on
// Home, opens /review, answers the stored question, gets graded feedback and the
// next review date, and finishes. Seeds and removes its own dev data.
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...a: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'review_fixture.py'), ...a], { stdio: 'pipe' }).toString()

test.use({ video: { mode: 'on', size: { width: 1280, height: 900 } }, viewport: { width: 1280, height: 900 } })

test('home card → review page → graded answer → done', async ({ page }) => {
  test.setTimeout(240_000)
  const stamp = `${Date.now()}`
  const user = await createFirebaseUser(stamp, 'e2e-review')
  try {
    fixture('seed', user.uid, user.email, `e2e-rev-${stamp}`)
    await signInAs(page, user.uid)

    await page.goto('/')
    const card = page.getByTestId('review-card')
    await expect(card).toBeVisible({ timeout: 30_000 })
    await expect(card).toContainText('1 question')
    await card.click({ timeout: 15_000 })

    await expect(page).toHaveURL(/\/review$/)
    await expect(page.getByTestId('review-question')).toHaveText('Why does the daytime sky look blue?', { timeout: 30_000 })
    await page.getByLabel('Your answer').fill('Air molecules scatter blue sunlight more than red light, so the sky looks blue.')
    await page.getByRole('button', { name: 'Check my answer' }).click()

    const feedback = page.getByTestId('review-feedback')
    await expect(feedback).toBeVisible({ timeout: 60_000 })
    await expect(feedback).toContainText(/You'll see this again (tomorrow|in \d+ days)/)
    await page.getByRole('button', { name: 'Finish' }).click()
    await expect(page.getByTestId('review-done')).toBeVisible()

    // Nothing is due any more: the card is gone.
    await page.goto('/')
    await expect(page.getByTestId('review-card')).toHaveCount(0)
  } finally {
    fixture('teardown', user.uid)
    await deleteFirebaseUser(user.uid)
  }
})
