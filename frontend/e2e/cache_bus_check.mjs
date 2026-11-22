// E1 check on dev: with several uvicorn workers, a teacher's change must reach every
// worker within seconds, not after the 60 s cache TTL.
//
//   node e2e/cache_bus_check.mjs
//
// A student loses access when a course is unassigned and regains it when it is
// assigned again. Each student request lands on a random worker. After the change,
// we poll until 12 requests in a row agree, and report how long that took.
// Needs WEB_CONCURRENCY > 1 on the dev API; leaves the course assigned as it found it.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const env = Object.fromEntries(readFileSync(path.join(DIR, '.env.e2e'), 'utf8').split('\n')
  .map((l) => l.trim()).filter((l) => l && !l.startsWith('#') && l.includes('='))
  .map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^["']|["']$/g, '')] }))
const base = env.E2E_BASE_URL || 'https://ecalt-dev.vercel.app'
const SCHOOL = '64b6fb69-76c0-47f3-941a-d6caf4fb7315'
const CLASS = '475e02e7-d51a-42a0-b100-bfa531278934'
const STUDENT = 'stu_da8183dbcf452cb4'

const auth = getAuth(getApps().length ? getApps()[0] : initializeApp({ credential: cert(JSON.parse(readFileSync(path.resolve(DIR, '..', env.FIREBASE_SERVICE_ACCOUNT || 'e2e/service-account.json'), 'utf8'))) }))
const tokens = new Map()
async function token(uid) {
  if (!tokens.has(uid)) {
    const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${env.E2E_FIREBASE_API_KEY}`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ token: await auth.createCustomToken(uid), returnSecureToken: true }),
    }).then((r) => r.json())
    tokens.set(uid, ex.idToken)
  }
  return tokens.get(uid)
}
async function call(uid, method, p, body) {
  const res = await fetch(`${base}${p}`, {
    method, headers: { authorization: `Bearer ${await token(uid)}`, 'x-vercel-protection-bypass': env.VERCEL_AUTOMATION_BYPASS_SECRET, ...(body ? { 'content-type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  return { status: res.status, body: text ? (() => { try { return JSON.parse(text) } catch { return text } })() : null }
}

const owner = (await auth.getUserByEmail(env.E2E_USER_EMAIL || 'developer.biswambar@gmail.com')).uid
const courses = (await call(owner, 'GET', `/api/v1/schools/${SCHOOL}/courses`)).body.courses
const course = courses.find((c) => c.status === 'published')
const jid = course.journey_id
const classCourses = (await call(owner, 'GET', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses`)).body
const existing = classCourses.assignments.find((c) => c.journey_id === jid)

const studentCan = async () => (await call(STUDENT, 'GET', `/api/v1/journeys/${jid}`)).status === 200

// Seconds from the change until the last stale answer (the 12 confirming requests
// themselves take several seconds, so they are not counted).
async function settle(expected, label) {
  const start = Date.now()
  let streak = 0
  let lastStale = 0
  while (Date.now() - start < 45_000) {
    if ((await studentCan()) === expected) streak++
    else { streak = 0; lastStale = Date.now() - start }
    if (streak >= 12) { const s = lastStale / 1000; console.log(`${label}: last stale answer ${s.toFixed(1)} s after the change`); return s }
    await new Promise((r) => setTimeout(r, 250))
  }
  console.log(`${label}: STILL DISAGREEING after 45 s`)
  return Infinity
}

const warm = async () => { for (let i = 0; i < 24; i++) await studentCan() }   // 24 random-worker hits: every worker caches the current answer
const unassign = async (id) => {
  const del = await call(owner, 'DELETE', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses/${id}`)
  if (del.status !== 204) throw new Error(`unassign failed: ${del.status}`)
}
const assign = async () => {
  const a = await call(owner, 'POST', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses`, { journey_id: jid })
  if (![200, 201].includes(a.status)) throw new Error(`assign failed: ${a.status} ${JSON.stringify(a.body)}`)
}

let failures = 0
try {
  if (!existing) throw new Error('the published course is not assigned to the class; assign it first')
  await warm()                                   // every worker has cached "allowed"
  if (!(await studentCan())) throw new Error('precondition: the student should have access')
  await unassign(existing.id)
  const t1 = await settle(false, 'after unassign (student blocked)')
  await warm()                                   // every worker has cached "blocked"
  await assign()
  const t2 = await settle(true, 'after assign   (student allowed)')
  if (!(t1 < 5 && t2 < 5)) failures++
} finally {
  const now = (await call(owner, 'GET', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses`)).body
  if (!now.assignments.find((c) => c.journey_id === jid)) await assign()
}
console.log(failures ? 'FAIL: changes took 5 s or more to reach every worker' : 'OK: changes reached every worker within 5 s')
process.exit(failures ? 1 : 0)
