import { expect, test } from '@playwright/test'
import { call } from './adminctl.mjs'

// M6 SC-605/604 against the dev deployment, driven through the real API. The
// same flow through the UI (Rebuild option + the student's Updated pill) is
// course-replace-ui.authed.spec.ts.
//
// Duplicate a published course, publish the copy, rebuild it from a document in
// `replace` mode, and check what the student-facing side ends up with:
//   * a complete new draft, no proposals to review
//   * a step whose title still matches keeps its id (progress survives)
//   * publishing stamps the changed steps with `content_updated_at`
//   * GET /progress/{id} answers with `updated_step_ids`
// Cleans up by archiving the copy.
const SCHOOL = 'Test Public School'
const SOURCE_COURSE = 'Introduction to Volcanoes'
const DOC = 'volcanoes.docx'

type Json = Record<string, any>

async function api(method: string, path: string, body?: Json): Promise<Json> {
  const r = await call(method, path, body ? JSON.stringify(body) : undefined)
  expect(r.ok, `${method} ${path} → ${r.status} ${r.body}`).toBeTruthy()
  return r.body ? JSON.parse(r.body) : {}
}

test('course replace mode — rebuild from a document, keep ids, badge the changes', async () => {
  test.setTimeout(900_000)

  const { schools } = await api('GET', '/api/v1/schools/mine')
  const school = schools.find((s: Json) => s.name === SCHOOL)
  expect(school, `school "${SCHOOL}" not on dev`).toBeTruthy()
  const base = `/api/v1/schools/${school.id}`

  const courses = await api('GET', `${base}/courses`)
  const source = (courses.courses ?? courses).find(
    (c: Json) => c.title === SOURCE_COURSE && c.status === 'published')
  expect(source, `published "${SOURCE_COURSE}" not on dev`).toBeTruthy()

  const docs = await api('GET', `${base}/documents`)
  const doc = (docs.documents ?? docs).find((d: Json) => d.filename === DOC && d.status === 'ready')
  expect(doc, `ready "${DOC}" not on dev`).toBeTruthy()

  // A throwaway copy so the shared fixture course keeps its history.
  const copy = await api('POST', `${base}/courses/${source.journey_id}/duplicate`)
  const jid = copy.journey_id
  expect(jid).toBeTruthy()

  try {
    const v1 = await api('POST', `${base}/courses/${jid}/publish`, {})
    expect(v1.status).toBe('published')
    const idsBefore = (await api('GET', `/api/v1/journeys/${jid}`)).steps.map((s: Json) => s.id)
    expect(idsBefore.length).toBeGreaterThan(0)

    // Rebuild from the document in replace mode and wait for the job.
    const started = await api('POST', `${base}/courses/${jid}/update`,
                              { document_id: doc.id, mode: 'replace' })
    expect(started.mode).toBe('replace')
    let job: Json = {}
    for (let i = 0; i < 180; i++) {
      job = await api('GET', `${base}/jobs/${started.job_id}`)
      if (['succeeded', 'failed', 'cancelled'].includes(job.status)) break
      await new Promise(r => setTimeout(r, 5_000))
    }
    expect(job.status, `job ended ${job.status}: ${JSON.stringify(job.result ?? {})}`).toBe('succeeded')
    expect(job.result?.status).toBe('replaced')

    // A whole new draft, not a list of proposals.
    expect((await api('GET', `${base}/courses/${jid}/proposals`)).proposals).toEqual([])
    const draft = (await api('GET', `${base}/courses/${jid}`)).draft
    expect(draft.meta.rebuilt_from_document).toBe(true)
    expect(draft.meta.updated_from_version).toBe(1)
    expect(draft.steps.length).toBeGreaterThan(0)
    for (const s of draft.steps) expect(s.body_md, `step ${s.id} has no body`).toBeTruthy()

    // At least one id survived on a title match (same document → same sections).
    const kept = draft.steps.filter((s: Json) => idsBefore.includes(s.id))
    expect(job.result.kept_step_ids).toBe(kept.length)
    expect(kept.length, 'no step id survived the rebuild').toBeGreaterThan(0)

    // Publishing stamps the steps whose body actually changed.
    await api('POST', `${base}/courses/${jid}/publish`, {})
    const published = await api('GET', `/api/v1/journeys/${jid}`)
    const stamped = published.steps.filter((s: Json) => s.content_updated_at)
    expect(stamped.length, 'no step was marked as updated').toBeGreaterThan(0)
    for (const s of stamped) expect(idsBefore).toContain(s.id)   // only re-published steps

    // The badge's data source answers on a school course.
    const progress = await api('GET', `/api/v1/progress/${jid}`)
    expect(Array.isArray(progress.updated_step_ids)).toBeTruthy()

    // eslint-disable-next-line no-console
    console.log(`[course-replace] ${draft.steps.length} steps, ${kept.length} ids kept, ` +
                `${stamped.length} badged`)
  } finally {
    await call('POST', `${base}/courses/${jid}/archive`, '{}')
  }
})
