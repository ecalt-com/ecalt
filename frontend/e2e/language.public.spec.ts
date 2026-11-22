import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFirebaseUser, deleteFirebaseUser, signInAs } from './signin'

// F2.2: an adult sets Hindi in their profile; the setting sticks; a journey generated
// afterwards is written in Hindi (Devanagari); a Hindi journey shows its language chip.
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...a: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'quiz_fixture.py'), ...a], { stdio: 'pipe' }).toString()
const DEVANAGARI = /[ऀ-ॿ]{3,}/

test('set Hindi, generate a journey in Hindi, see the language chip', async ({ page }) => {
  test.setTimeout(420_000)
  const stamp = `${Date.now()}`
  const user = await createFirebaseUser(stamp, 'e2e-lang')
  const jid = `e2e-lang-${stamp}`
  try {
    fixture('seed', user.uid, user.email, jid, 'hi')
    await signInAs(page, user.uid)

    await page.goto('/profile')
    const select = page.getByLabel('Language for new journeys and chat')
    await expect(select).toHaveValue('en', { timeout: 30_000 })
    await select.selectOption('hi')
    await expect(page.getByRole('status')).toContainText('Hindi')
    await page.reload()
    await expect(page.getByLabel('Language for new journeys and chat')).toHaveValue('hi', { timeout: 30_000 })

    // A Hindi journey wears its language.
    await page.goto(`/journey/${jid}`)
    await expect(page.getByTestId('language-badge').first()).toHaveText('हिन्दी', { timeout: 30_000 })

    // A journey generated now is written in Hindi.
    await page.goto('/explore?q=' + encodeURIComponent('How do rainbows form?'))
    await expect(page.getByText(DEVANAGARI).first()).toBeVisible({ timeout: 180_000 })
  } finally {
    fixture('teardown', user.uid)
    await deleteFirebaseUser(user.uid)
  }
})
