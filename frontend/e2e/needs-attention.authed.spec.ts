import { expect, test } from '@playwright/test'
import { call } from './adminctl.mjs'

// #14: the class progress matrix's "Needs attention" filter shows exactly the
// students the API flags (SC-702 flags: overdue / low quiz scores / many hints / stalled).
const SCHOOL = 'Test Public School'
const CLASS_ID = '475e02e7-d51a-42a0-b100-bfa531278934' // Physics

test('Needs attention filter shows only flagged students', async ({ page }) => {
  test.setTimeout(90_000)
  const mine = JSON.parse((await call('GET', '/api/v1/schools/mine')).body)
  const school = (mine.schools ?? mine).find((s: { name: string }) => s.name === SCHOOL)
  const r = await call('GET', `/api/v1/schools/${school.id}/classes/${CLASS_ID}/progress`)
  expect(r.ok, r.body).toBeTruthy()
  const data = JSON.parse(r.body)
  const flagged = data.students.filter((s: { needs_attention: boolean }) => s.needs_attention)
  expect(data.students.every((s: { flags: string[] }) => Array.isArray(s.flags))).toBe(true)

  await page.goto('/school')
  await page.getByRole('combobox', { name: 'Switch school' }).selectOption({ label: SCHOOL })
  await page.goto(`/school/classes/${CLASS_ID}`)
  const card = page.locator('.glass-card').filter({ has: page.getByRole('heading', { name: 'Progress' }) })
  const toggle = card.getByTestId('needs-attention-filter')
  await expect(toggle).toHaveText(new RegExp(`Needs attention \\(${flagged.length}\\)`), { timeout: 20_000 })
  await expect(card.getByTestId('progress-row')).toHaveCount(data.students.length)

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  if (flagged.length === 0) {
    await expect(card.getByTestId('needs-attention-empty')).toBeVisible()
  } else {
    await expect(card.getByTestId('progress-row')).toHaveCount(flagged.length)
    await expect(card.locator('[data-testid="progress-row"][data-needs-attention="false"]')).toHaveCount(0)
  }

  await toggle.click()
  await expect(card.getByTestId('progress-row')).toHaveCount(data.students.length)
  // eslint-disable-next-line no-console
  console.log(`[needs-attention] ${flagged.length}/${data.students.length} flagged:`,
    flagged.map((s: { flags: string[] }) => s.flags.join('+')).join(', '))
})
