import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createFirebaseUser, deleteFirebaseUser, signInAs } from './signin'

// F1.1: a step's quiz is generated only when the learner reaches it, and a reload
// shows the same unanswered questions (no second generation).
// F1.2: opening and reading the step is recorded as funnel events.
const DIR = path.dirname(fileURLToPath(import.meta.url))
const PY = path.resolve(DIR, '../../backend/.venv/bin/python')
const fixture = (...a: string[]) => execFileSync(PY, ['-I', path.join(DIR, 'quiz_fixture.py'), ...a], { stdio: 'pipe' }).toString()
const counts = (uid: string, jid: string) => JSON.parse(fixture('counts', uid, jid).trim().split('\n').pop()!)

test.use({ video: { mode: 'on', size: { width: 1280, height: 900 } }, viewport: { width: 1280, height: 700 } })

test('quiz generates on reach, is reused on reload; funnel events are recorded', async ({ page }) => {
  test.setTimeout(300_000)
  const stamp = `${Date.now()}`
  const user = await createFirebaseUser(stamp, 'e2e-quiz')
  const jid = `e2e-quiz-${stamp}`
  try {
    fixture('seed', user.uid, user.email, jid)
    await signInAs(page, user.uid)

    const quizRequests: string[] = []
    page.on('request', (r) => { if (r.method() === 'POST' && /\/api\/v1\/quiz$/.test(r.url())) quizRequests.push(r.postData() ?? '') })

    await page.goto(`/journey/${jid}`)
    await page.getByRole('button', { name: /Why the sky is blue/ }).first().click()
    await expect(page.getByText('Sunlight looks white').first()).toBeVisible({ timeout: 30_000 })

    // Content is on screen but the quiz card is below the fold: nothing generated yet.
    await page.waitForTimeout(2500)
    expect(quizRequests).toHaveLength(0)
    expect(counts(user.uid, jid).sessions).toBe(0)

    // Scroll to the end of the lesson: the quiz is generated now.
    await page.getByRole('button', { name: 'Start the quiz' }).scrollIntoViewIfNeeded()
    const firstQuestion = page.locator('[data-testid="quiz-question"]').first()
    await expect(firstQuestion).toBeVisible({ timeout: 90_000 })
    const questions = await page.locator('[data-testid="quiz-question"]').allInnerTexts()
    expect(questions.length).toBeGreaterThanOrEqual(2)
    expect(quizRequests).toHaveLength(1)
    const afterFirst = counts(user.uid, jid)
    expect(afterFirst.sets).toBe(1)

    // Reload and reach the quiz again: the same questions, no new generation.
    await page.reload()
    await page.getByRole('button', { name: /Why the sky is blue/ }).first().click()
    await expect(page.getByText('Sunlight looks white').first()).toBeVisible({ timeout: 30_000 })
    await page.getByRole('button', { name: 'Start the quiz' }).scrollIntoViewIfNeeded()
    await expect(page.locator('[data-testid="quiz-question"]').first()).toBeVisible({ timeout: 90_000 })
    expect(await page.locator('[data-testid="quiz-question"]').allInnerTexts()).toEqual(questions)
    expect(counts(user.uid, jid).sets).toBe(1)

    // Funnel events were batched to the server (flushed when the page is hidden).
    await page.goto('about:blank')
    await expect.poll(() => counts(user.uid, jid).events, { timeout: 30_000, intervals: [2000] })
      .toMatchObject({ step_open: expect.any(Number), quiz_view: expect.any(Number), quiz_ready: expect.any(Number) })
  } finally {
    fixture('teardown', user.uid)
    await deleteFirebaseUser(user.uid)
  }
})
