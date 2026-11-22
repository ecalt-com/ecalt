import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFirebaseUser, deleteFirebaseUser, signInAs } from './signin'

// F2.1: "Listen" on a lesson reads plain sentences through speechSynthesis, with
// pause, resume, stop and a speed toggle. The speech engine is stubbed so the test
// can see exactly what would be spoken (headless Chromium has no voices).
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...a: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'quiz_fixture.py'), ...a], { stdio: 'pipe' }).toString()

test('listen reads the lesson as plain sentences and can be paused and stopped', async ({ page }) => {
  test.setTimeout(180_000)
  const stamp = `${Date.now()}`
  const user = await createFirebaseUser(stamp, 'e2e-listen')
  const jid = `e2e-listen-${stamp}`
  try {
    fixture('seed', user.uid, user.email, jid)
    await signInAs(page, user.uid)
    await page.addInitScript(() => {
      const w = window as unknown as Record<string, unknown>
      w.__spoken = [] as { text: string; rate: number }[]
      w.__calls = [] as string[]
      class Utt { text: string; rate = 1; lang = ''; onend: null | (() => void) = null; onerror: null | (() => void) = null
        constructor(t: string) { this.text = t } }
      w.SpeechSynthesisUtterance = Utt
      w.speechSynthesis = {
        speak: (u: Utt) => { (w.__spoken as { text: string; rate: number }[]).push({ text: u.text, rate: u.rate }); setTimeout(() => u.onend?.(), 40) },
        cancel: () => (w.__calls as string[]).push('cancel'),
        pause: () => (w.__calls as string[]).push('pause'),
        resume: () => (w.__calls as string[]).push('resume'),
      }
    })

    await page.goto(`/journey/${jid}`)
    await page.getByRole('button', { name: /Why the sky is blue/ }).first().click()
    await expect(page.getByText('Sunlight looks white').first()).toBeVisible({ timeout: 30_000 })

    await page.getByRole('button', { name: 'Listen to this' }).click()
    await expect.poll(() => page.evaluate(() => (window as unknown as { __spoken: unknown[] }).__spoken.length)).toBeGreaterThan(3)
    const spoken = await page.evaluate(() => (window as unknown as { __spoken: { text: string }[] }).__spoken.map(s => s.text).join(' '))
    expect(spoken).toContain('Why the sky is blue.')
    expect(spoken).toContain('Rayleigh scattering')
    expect(spoken).not.toMatch(/##|\*\*|<|http/)

    // Finished: back to "Listen". Start again, then pause / resume / stop.
    await expect(page.getByRole('button', { name: 'Listen to this' })).toBeVisible({ timeout: 15_000 })
    await page.evaluate(() => { (window as unknown as { speechSynthesis: { speak: unknown } }).speechSynthesis.speak = () => undefined })
    await page.getByRole('button', { name: 'Listen to this' }).click()
    await page.getByRole('button', { name: 'Pause reading' }).click()
    await page.getByRole('button', { name: 'Resume reading' }).click()
    await page.getByRole('button', { name: /Reading speed 1 times/ }).click()      // changing speed stops playback
    await expect(page.getByRole('button', { name: 'Listen to this' })).toBeVisible()
    const calls = await page.evaluate(() => (window as unknown as { __calls: string[] }).__calls)
    expect(calls).toEqual(expect.arrayContaining(['pause', 'resume', 'cancel']))

    // The mic is a signed-in adult feature, and only where the browser supports it.
    await expect(page.getByRole('button', { name: 'Dictate your question' })).toHaveCount(0)
  } finally {
    fixture('teardown', user.uid)
    await deleteFirebaseUser(user.uid)
  }
})
