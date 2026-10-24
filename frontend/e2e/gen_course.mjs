// Drives the AI course-builder pipeline via the API (there is no UI yet) on a
// document already uploaded + extracted to "ready".
//   node e2e/gen_course.mjs <schoolId> <filenameSubstr> [targetSteps]
import { call } from './adminctl.mjs'

const [, , schoolId, needle, targetStepsArg] = process.argv
const targetSteps = Number(targetStepsArg || 4)
if (!schoolId || !needle) { console.error('usage: node e2e/gen_course.mjs <schoolId> <filenameSubstr> [targetSteps]'); process.exit(2) }

const j = (r) => { try { return JSON.parse(r.body) } catch { return r.body } }
const sleep = (ms) => new Promise(r => setTimeout(r, ms))

async function pollJob(jobId, label, timeoutMs = 180_000) {
  const t0 = Date.now()
  for (;;) {
    const r = j(await call('GET', `/api/v1/schools/${schoolId}/jobs/${jobId}`))
    const prog = r.progress ? ` ${JSON.stringify(r.progress)}` : ''
    process.stdout.write(`\r  ${label}: ${r.status}${prog}            `)
    if (['succeeded', 'failed', 'cancelled'].includes(r.status)) { console.log(''); return r }
    if (Date.now() - t0 > timeoutMs) { console.log('\n  (timed out)'); return r }
    await sleep(3000)
  }
}

// 1. Find the ready document.
const docs = j(await call('GET', `/api/v1/schools/${schoolId}/documents`)).documents || []
const doc = docs.find(d => d.filename.includes(needle) && d.status === 'ready')
if (!doc) { console.error('No ready document matching', needle, '— have:', docs.map(d => `${d.filename}:${d.status}`)); process.exit(1) }
console.log('📄 Document:', doc.filename, `(${doc.page_count ?? '?'} pages, ${doc.status})`, 'id', doc.id)

// 2. Create a draft course from it.
const title = `E2E Photosynthesis Course ${needle}`
const created = j(await call('POST', `/api/v1/schools/${schoolId}/courses`, JSON.stringify({ title, document_ids: [doc.id] })))
const jid = created.journey_id
console.log('🧩 Course created:', jid, '| draft status:', created.draft?.status)

// 3. Estimate the cost.
const est = j(await call('POST', `/api/v1/schools/${schoolId}/courses/${jid}/estimate`))
console.log('💰 Estimate:', JSON.stringify(est))

// 4. Outline (grounded in the document).
const o = j(await call('POST', `/api/v1/schools/${schoolId}/courses/${jid}/outline`,
  JSON.stringify({ target_steps: targetSteps, follow_document_order: true })))
console.log('📝 Outline job:', o.job_id)
await pollJob(o.job_id, 'outline')
let course = j(await call('GET', `/api/v1/schools/${schoolId}/courses/${jid}`))
console.log(`\n=== OUTLINE (draft status: ${course.draft?.status}) ===`)
console.log('Title:', course.draft?.meta?.title || course.title)
;(course.draft?.steps || []).forEach((s, i) => console.log(`  ${i + 1}. ${s.title}${s.core_question ? ' — ' + s.core_question : ''}`))

// 5. Build step bodies (grounded + critic).
const b = j(await call('POST', `/api/v1/schools/${schoolId}/courses/${jid}/build`))
console.log('\n🔨 Build job:', b.job_id)
await pollJob(b.job_id, 'build')
course = j(await call('GET', `/api/v1/schools/${schoolId}/courses/${jid}`))
const steps = course.draft?.steps || []
console.log(`\n=== BUILT COURSE (draft status: ${course.draft?.status}, ${steps.length} steps) ===`)
steps.forEach((s, i) => {
  const body = (s.body_md || '').replace(/\s+/g, ' ').trim()
  const flags = s.flags?.length ? ` [flags: ${s.flags.length}]` : ''
  console.log(`\n  Step ${i + 1}: ${s.title}${flags}`)
  console.log('   ', body.slice(0, 220) + (body.length > 220 ? '…' : ''))
})

console.log(`\nCLEANUP_IDS journey_id=${jid} document_id=${doc.id}`)
