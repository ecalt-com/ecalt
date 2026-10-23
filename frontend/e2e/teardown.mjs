// Cleans up the data a lifecycle run created.
//   node e2e/teardown.mjs <stamp> [preflightSchoolId]
// Deletes the demo students + class (matched by <stamp>) from Test Public
// School, and terminates any admin-created "E2E Test School <stamp>" plus an
// optional preflight school.
import { call } from './adminctl.mjs'

const stamp = process.argv[2]
const preflight = process.argv[3]
const TPS = process.env.E2E_SCHOOL_TPS || '64b6fb69-76c0-47f3-941a-d6caf4fb7315' // Test Public School
if (!stamp) { console.error('usage: node e2e/teardown.mjs <stamp> [preflightSchoolId]'); process.exit(2) }

const j = (r) => { try { return JSON.parse(r.body) } catch { return {} } }

// 1. Students in Test Public School matching the stamp.
const sres = await call('GET', `/api/v1/schools/${TPS}/students?q=${encodeURIComponent(stamp)}&limit=50`)
for (const s of (j(sres).students || [])) {
  const d = await call('DELETE', `/api/v1/schools/${TPS}/students/${encodeURIComponent(s.uid)}`)
  console.log('student', s.display_name, '→', d.status)
}

// 2. Class matching the stamp.
const cres = await call('GET', `/api/v1/schools/${TPS}/classes`)
for (const c of (j(cres).classes || [])) {
  if (c.name.includes(stamp)) {
    const d = await call('DELETE', `/api/v1/schools/${TPS}/classes/${encodeURIComponent(c.id)}`)
    console.log('class', c.name, '→', d.status)
  }
}

// 3. Admin-created school(s) matching the stamp → terminate.
const ares = await call('GET', `/api/v1/admin/schools?q=${encodeURIComponent('E2E Test School ' + stamp)}`)
for (const s of (j(ares).schools || [])) {
  if (s.name.includes(stamp)) {
    const d = await call('PATCH', `/api/v1/admin/schools/${encodeURIComponent(s.id)}`, JSON.stringify({ status: 'terminated' }))
    console.log('terminated', s.name, '→', d.status)
  }
}

// 4. Optional preflight school.
if (preflight) {
  const d = await call('PATCH', `/api/v1/admin/schools/${encodeURIComponent(preflight)}`, JSON.stringify({ status: 'terminated' }))
  console.log('terminated preflight', preflight, '→', d.status)
}
console.log('teardown done')
