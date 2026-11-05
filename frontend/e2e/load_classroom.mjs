// SC-802 load test against a deployed environment (default: dev).
//
//   node e2e/load_classroom.mjs [--students 40] [--courses 20] [--keep]
//
// 1. Roster import: a CSV of N students into a fresh class (timed).
// 2. Courses: duplicates + publishes a fixture course C times (no AI) and assigns them.
// 3. Classroom burst: all N students sign in at once with class code + PIN, then
//    open home → the journey → progress (the first minute of a lesson).
// 4. Teacher: the class progress matrix (N × C) a few times.
// 5. Cleanup (unless --keep): delete the students, archive class + course copies,
//    restore the school's seat limit.
// Prints p50/p95/max per call and any errors; writes e2e/.output/load-report.json.
// Uses the E2E owner (adminctl) — never point it at production.
import fs from 'node:fs'
import { call, cfg } from './adminctl.mjs'

const arg = (name, def) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > -1 ? process.argv[i + 1] : def
}
const N = Number(arg('students', 40))
const C = Number(arg('courses', 20))
const KEEP = process.argv.includes('--keep')
const CLEANUP_ONLY = process.argv.includes('--cleanup')  // remove leftovers of earlier runs
const SCHOOL = process.env.E2E_LOAD_SCHOOL || 'Test Public School'
const FIXTURE = 'Introduction to Volcanoes'
if (/ecalt\.vercel\.app|ecalt-production/.test(cfg.base)) throw new Error('refusing to load-test production')

const timings = {}
const errors = []
const time = async (label, fn) => {
  const t0 = performance.now()
  try { return await fn() } finally { (timings[label] ??= []).push(performance.now() - t0) }
}
// Setup/cleanup calls retry on a dropped connection (seen from this network).
async function callRetry(method, path, body) {
  for (let i = 0; ; i++) {
    try { return await call(method, path, body) } catch (e) {
      if (i >= 3) throw e
      await new Promise((r) => setTimeout(r, 1000 * (i + 1)))
    }
  }
}
async function api(method, path, body) {
  const r = await callRetry(method, path, body === undefined ? undefined : JSON.stringify(body))
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${r.body.slice(0, 200)}`)
  return r.body ? JSON.parse(r.body) : {}
}
const headers = { 'x-vercel-protection-bypass': cfg.bypass, 'content-type': 'application/json' }
async function raw(method, path, { token, body } = {}) {
  const res = await fetch(`${cfg.base}${path}`, {
    method, headers: { ...headers, ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${text.slice(0, 160)}`)
  return text ? JSON.parse(text) : {}
}
const stats = (xs) => {
  const s = [...xs].sort((a, b) => a - b)
  const q = (p) => s[Math.min(s.length - 1, Math.floor(p * s.length))]
  return { n: s.length, p50: Math.round(q(0.5)), p95: Math.round(q(0.95)), max: Math.round(s[s.length - 1]) }
}

const { schools } = await api('GET', '/api/v1/schools/mine')
const school = schools.find((s) => s.name === SCHOOL)
if (!school) throw new Error(`school ${SCHOOL} not found`)
const base = `/api/v1/schools/${school.id}`
const adminSchool = await api('GET', `/api/v1/admin/schools/${school.id}`)
const originalSeats = adminSchool.seat_limit
const tag = Date.now().toString(36)
const className = `Load ${tag}`
const created = { students: [], courses: [], classId: null }

// Leftovers of an interrupted run: classes named "Load <tag>" and their students.
async function cleanupLeftovers() {
  const all = (await api('GET', `${base}/classes?include_archived=true`)).classes.filter((c) => /^Load [0-9a-z]+$/.test(c.name))
  let n = 0
  for (const c of all) {
    const d = await api('GET', `${base}/classes/${c.id}`)
    for (const s of d.students ?? []) if (/^Load /.test(s.display_name)) { await callRetry('DELETE', `${base}/students/${s.uid}`); n++ }
    if (!c.archived_at) await callRetry('DELETE', `${base}/classes/${c.id}`)
  }
  console.error(`cleanup: removed ${n} leftover students from ${all.length} load-test classes`)
}
if (CLEANUP_ONLY) { await cleanupLeftovers(); process.exit(0) }

try {
  // Seats for the run.
  if (adminSchool.student_count + N > originalSeats) {
    await api('PATCH', `/api/v1/admin/schools/${school.id}`, { seat_limit: adminSchool.student_count + N + 5 })
  }

  // 1. Roster import.
  const csv = ['name,grade,roll number,class,sign-in',
    ...Array.from({ length: N }, (_, i) => `Load ${tag} ${i + 1},6,LT-${tag}-${i + 1},${className},pin`)].join('\n')
  const report = await time('roster_import', () => api('POST', `${base}/students/import?dry_run=false`, { csv }))
  const cls = (await api('GET', `${base}/classes`)).classes.find((c) => c.name === className)
  if (cls) created.classId = cls.id
  const detail = cls ? await api('GET', `${base}/classes/${cls.id}`) : { students: [] }
  created.students = detail.students.map((s) => s.uid)
  if (created.students.length !== N) throw new Error(`import made ${created.students.length} students, expected ${N}: ${JSON.stringify(report.summary)}`)
  const cards = await time('login_cards', () => api('POST', `${base}/classes/${cls.id}/login-cards`, { reset: true }))
  const pins = Object.fromEntries(cards.cards.map((c) => [c.uid, c.secret]))

  // 2. Courses.
  const list = await api('GET', `${base}/courses`)
  const fixture = (list.courses ?? list).find((c) => c.title === FIXTURE && c.status === 'published')
  if (!fixture) throw new Error(`published "${FIXTURE}" not found`)
  for (let i = 0; i < C; i++) {
    const jid = (await api('POST', `${base}/courses/${fixture.journey_id}/duplicate`)).journey_id
    created.courses.push(jid)
    await api('POST', `${base}/courses/${jid}/publish`, {})
    await api('POST', `${base}/classes/${cls.id}/courses`, { journey_id: jid })
  }
  const firstCourse = created.courses[0]

  // 3. Classroom burst: everyone at once.
  const joinCode = detail.join_code
  const burstStart = performance.now()
  const results = await Promise.allSettled(created.students.map(async (uid) => {
    const session = await time('sign_in', () => raw('POST', '/api/v1/school-login/sessions',
      { body: { class_code: joinCode, student_uid: uid, secret: { kind: 'pin', value: pins[uid] } } }))
    const ex = await time('token_exchange', () => fetch(
      `https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${cfg.apiKey}`,
      { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token: session.custom_token ?? session.token, returnSecureToken: true }) }).then((r) => r.json()))
    if (!ex.idToken) throw new Error('token exchange failed')
    const token = ex.idToken
    await time('bootstrap_users', () => raw('POST', '/api/v1/users', { token, body: {} }))
    await time('student_home', () => raw('GET', '/api/v1/school-student/home', { token }))
    await time('journey', () => raw('GET', `/api/v1/journeys/${firstCourse}`, { token }))
    await time('progress', () => raw('GET', `/api/v1/progress/${firstCourse}`, { token }))
  }))
  const burstMs = performance.now() - burstStart
  results.forEach((r) => { if (r.status === 'rejected') errors.push(String(r.reason?.message ?? r.reason)) })

  // 4. Teacher's matrix.
  for (let i = 0; i < 5; i++) await time('progress_matrix', () => api('GET', `${base}/classes/${cls.id}/progress`))

  const out = {
    target: cfg.base, students: N, courses: C, burst_wall_ms: Math.round(burstMs),
    burst_ok: results.filter((r) => r.status === 'fulfilled').length,
    timings: Object.fromEntries(Object.entries(timings).map(([k, v]) => [k, stats(v)])),
    errors: [...new Set(errors)].slice(0, 10), at: new Date().toISOString(),
  }
  console.log(JSON.stringify(out, null, 2))
  fs.mkdirSync(new URL('./.output/', import.meta.url), { recursive: true })
  fs.writeFileSync(new URL('./.output/load-report.json', import.meta.url), JSON.stringify(out, null, 2))
  if (out.burst_ok !== N) process.exitCode = 1
} finally {
  if (!KEEP) {
    for (const uid of created.students) await callRetry('DELETE', `${base}/students/${uid}`)
    if (created.classId) await callRetry('DELETE', `${base}/classes/${created.classId}`)
    for (const jid of created.courses) await callRetry('POST', `${base}/courses/${jid}/archive`, '{}')
    await callRetry('PATCH', `/api/v1/admin/schools/${school.id}`, JSON.stringify({ seat_limit: originalSeats }))
    console.error(`cleanup: deleted ${created.students.length} students, archived class + ${created.courses.length} course copies`)
  }
}
