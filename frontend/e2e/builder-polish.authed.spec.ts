import { expect, test } from '@playwright/test'
import { call } from './adminctl.mjs'

// #16 course-builder polish, recorded, against dev. Works on a duplicate of a
// published fixture course (built steps, no AI build needed), archived at the end:
// details (icon/tags), sources, autosave, conflict keep-my-text, drag reorder,
// preview as student, quiz preview (one small real model call).
const SCHOOL = 'Test Public School'
const SOURCE_COURSE = 'Introduction to Volcanoes'
type Json = Record<string, any>

async function api(method: string, path: string, body?: Json): Promise<Json> {
  const r = await call(method, path, body ? JSON.stringify(body) : undefined)
  expect(r.ok, `${method} ${path} → ${r.status} ${r.body}`).toBeTruthy()
  return r.body ? JSON.parse(r.body) : {}
}

test.use({
  video: { mode: 'on', size: { width: 1280, height: 900 } },
  viewport: { width: 1280, height: 900 },
})

let base = ''
let jid = ''
test.afterAll(async () => { if (jid) await call('POST', `${base}/courses/${jid}/archive`, '{}') })

test('course builder polish works end to end (recorded)', async ({ page }) => {
  test.setTimeout(300_000)
  const { schools } = await api('GET', '/api/v1/schools/mine')
  const school = schools.find((s: Json) => s.name === SCHOOL)
  base = `/api/v1/schools/${school.id}`
  const list = await api('GET', `${base}/courses`)
  const source = (list.courses ?? list).find((c: Json) => c.title === SOURCE_COURSE && c.status === 'published')
  expect(source, `published "${SOURCE_COURSE}" not on dev`).toBeTruthy()
  jid = (await api('POST', `${base}/courses/${source.journey_id}/duplicate`)).journey_id
  const initial = (await api('GET', `${base}/courses/${jid}`)).draft
  const firstTitles = initial.steps.map((s: Json) => s.title)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await page.goto(`/school/courses/${jid}`)
  await expect(page.getByRole('button', { name: 'Details' })).toBeVisible({ timeout: 20_000 })

  // 1. Course details: icon + tags.
  await page.getByRole('button', { name: 'Details' }).click()
  await page.getByLabel('Course icon').fill('🌋')
  await page.getByLabel('Tags (comma-separated)').fill('Earth Science, grade 6')
  await page.getByRole('button', { name: 'Save details' }).click()
  await expect(page.locator('h1', { hasText: '🌋' })).toBeVisible()
  const meta = (await api('GET', `${base}/courses/${jid}`)).draft.meta
  expect(meta.icon).toBe('🌋')
  expect(meta.tags).toEqual(['earth science', 'grade 6'])

  // 2. Cited source text with file + pages.
  await page.getByTestId('show-sources').click()
  const chunks = page.getByTestId('source-chunks')
  await expect(chunks).toBeVisible({ timeout: 15_000 })
  await expect(chunks.locator('li').first()).toContainText(/\.(docx|pdf)/)
  await page.keyboard.press('Escape')

  // 3. Autosave: type, wait, saved without pressing anything.
  const editor = page.getByLabel('Step content')
  await editor.click()
  await editor.press('End')
  await editor.pressSequentially('\n\nAutosaved line.', { delay: 20 })
  await expect(page.getByTestId('save-status')).toHaveText('All changes saved', { timeout: 15_000 })
  const afterSave = (await api('GET', `${base}/courses/${jid}`)).draft
  expect(afterSave.steps[0].body_md).toContain('Autosaved line.')

  // 4. Conflict: someone else edits; my next edit is kept aside, not lost.
  await api('PATCH', `${base}/courses/${jid}/draft/steps/${afterSave.steps[0].id}`,
    { body_md: afterSave.steps[0].body_md + '\n\nEdited elsewhere.', expected_revision: afterSave.revision })
  await editor.pressSequentially('\n\nMy unsaved idea.', { delay: 20 })
  const panel = page.getByTestId('conflict-panel')
  await expect(panel).toBeVisible({ timeout: 15_000 })
  await expect(panel.getByLabel('Your unsaved text')).toHaveValue(/My unsaved idea\./)
  await expect(page.getByLabel('Step content')).toHaveValue(/Edited elsewhere\./)
  await panel.getByRole('button', { name: 'Dismiss' }).click()

  // 5. Drag the second step above the first in the step list.
  const items = page.locator('aside li[draggable="true"]')
  await expect(items).toHaveCount(firstTitles.length)
  await items.nth(1).dragTo(items.nth(0))
  await expect.poll(async () => (await api('GET', `${base}/courses/${jid}`)).draft.steps[0].title, { timeout: 15_000 })
    .toBe(firstTitles[1])

  // 6. Preview as student.
  await page.getByRole('button', { name: 'Preview as student' }).click()
  const preview = page.getByTestId('student-preview')
  await expect(preview).toBeVisible()
  await expect(preview).toContainText('Preview — this is how students will see the draft')
  await expect(preview.locator('h1', { hasText: '🌋' })).toBeVisible()
  await page.waitForTimeout(1200)
  await preview.getByRole('button', { name: 'Close' }).click()

  // 7. Quiz preview (real model, nothing saved).
  await page.getByRole('button', { name: 'Quiz' }).click()
  const quiz = page.getByTestId('quiz-preview')
  await expect(quiz).toBeVisible({ timeout: 90_000 })
  expect(await quiz.locator('li').count()).toBeGreaterThanOrEqual(2)
  await quiz.getByRole('button', { name: 'Show answer' }).first().click()
  await expect(quiz).toContainText('Answer:')
  await page.waitForTimeout(1200)
})
