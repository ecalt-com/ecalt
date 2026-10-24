// §9 Assignments API smoke on dev (SC-501/502/503). Signs in as the school
// OWNER and as a STUDENT via minted custom tokens (ecalt-dev service account),
// then drives the real dev API with the Vercel bypass header:
//   owner  → assign a published course to a class, list it, read progress
//   student→ GET /school-student/home reflects the assignment
//   owner  → toggle tutor/quiz settings, then leave the class assigned
//
// Usage: node e2e/verify_assignments.mjs
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const env = {}
for (const line of readFileSync(path.join(DIR, '.env.e2e'), 'utf8').split('\n')) {
  const l = line.trim()
  if (!l || l.startsWith('#')) continue
  const i = l.indexOf('=')
  if (i < 0) continue
  let v = l.slice(i + 1).trim()
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1)
  env[l.slice(0, i).trim()] = v
}

const apiKey = env.E2E_FIREBASE_API_KEY
const bypass = env.VERCEL_AUTOMATION_BYPASS_SECRET
const base = env.E2E_BASE_URL || 'https://ecalt-dev.vercel.app'
const email = env.E2E_USER_EMAIL || 'developer.biswambar@gmail.com'
const saPath = path.resolve(DIR, '..', env.FIREBASE_SERVICE_ACCOUNT || 'e2e/service-account.json')

const SCHOOL = '64b6fb69-76c0-47f3-941a-d6caf4fb7315' // Test Public School
const CLASS = '475e02e7-d51a-42a0-b100-bfa531278934'  // Physics
const STUDENTS = ['stu_da8183dbcf452cb4', 'stu_22fdc632741aa12f']

const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(JSON.parse(readFileSync(saPath, 'utf8'))) })
const auth = getAuth(app)

const tokenCache = new Map()
async function idTokenFor(uid) {
  if (tokenCache.has(uid)) return tokenCache.get(uid)
  const customToken = await auth.createCustomToken(uid)
  const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${apiKey}`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ token: customToken, returnSecureToken: true }),
  }).then(r => r.json())
  if (!ex.idToken) throw new Error(`token exchange failed for ${uid}: ${JSON.stringify(ex)}`)
  tokenCache.set(uid, ex.idToken)
  return ex.idToken
}

async function callAs(uid, method, apiPath, body) {
  const token = await idTokenFor(uid)
  const res = await fetch(`${base}${apiPath}`, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      'x-vercel-protection-bypass': bypass,
      ...(body ? { 'content-type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let json
  try { json = JSON.parse(text) } catch { json = text }
  return { status: res.status, ok: res.ok, body: json }
}

let pass = 0, fail = 0
const ok = (cond, msg) => { if (cond) { pass++; console.log(`  ✓ ${msg}`) } else { fail++; console.log(`  ✗ ${msg}`) } }

const ownerUid = (await auth.getUserByEmail(email)).uid
console.log(`owner uid = ${ownerUid}`)

// 1. Find a published course in the school.
console.log('\n[1] find a published course')
const courses = await callAs(ownerUid, 'GET', `/api/v1/schools/${SCHOOL}/courses`)
ok(courses.ok, `GET /courses → ${courses.status}`)
const published = (courses.body.courses || []).find(c => c.status === 'published')
ok(!!published, `found a published course: ${published ? `"${published.title}" (journey ${published.journey_id})` : 'NONE'}`)
if (!published) { console.log('\nno published course to assign — aborting'); process.exit(1) }
const journeyId = published.journey_id

// 2. Assign it to the class (tolerate already-assigned).
console.log('\n[2] assign course to class (owner)')
const dueIso = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10) + 'T23:59:59Z'
const assign = await callAs(ownerUid, 'POST', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses`, {
  journey_id: journeyId, due_at: dueIso, tutor_enabled: true, quiz_required: false,
})
const already = assign.status === 409 && assign.body?.detail?.error === 'already_assigned'
ok(assign.ok || already, `POST assign → ${assign.status}${already ? ' (already assigned — fine)' : ''}`)

// 3. List assignments + progress summary.
console.log('\n[3] list assignments (owner)')
const list = await callAs(ownerUid, 'GET', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses`)
ok(list.ok, `GET assignments → ${list.status}`)
const a = (list.body.assignments || []).find(x => x.journey_id === journeyId)
ok(!!a, `assignment present for the published course`)
if (a) {
  ok(a.progress && a.progress.enrolled === STUDENTS.length, `progress.enrolled = ${a.progress?.enrolled} (expected ${STUDENTS.length})`)
  ok(typeof a.progress?.avg_percent === 'number', `progress.avg_percent present (${a.progress?.avg_percent}%)`)
  ok(a.settings?.tutor_enabled === true && a.settings?.quiz_required === false, `settings tutor=on quiz=optional`)
  ok(!!a.due_at, `due date set (${a.due_at})`)
}

// 4. Student home reflects the assignment.
console.log('\n[4] student home (each enrolled student)')
for (const stu of STUDENTS) {
  const home = await callAs(stu, 'GET', '/api/v1/school-student/home')
  const cls = (home.body.classes || []).find(c => c.class_id === CLASS)
  const course = cls?.courses?.find(c => c.journey_id === journeyId)
  ok(home.ok && !!course, `${stu}: sees "${course?.title ?? '—'}" in "${cls?.class_name ?? '?'}" (teacher: ${cls?.teacher_name ?? '—'})`)
  if (course) ok(typeof course.percent === 'number' && typeof course.total_steps === 'number', `  course has progress shape (percent=${course.percent}, steps=${course.total_steps}, tutor=${course.tutor_enabled})`)
}

// 5. Toggle settings (SC-503 surface): quiz required on, then back off.
console.log('\n[5] update settings (owner)')
if (a) {
  const up1 = await callAs(ownerUid, 'PATCH', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses/${a.id}`, { quiz_required: true, tutor_enabled: false })
  ok(up1.ok && up1.body?.settings?.quiz_required === true && up1.body?.settings?.tutor_enabled === false, `PATCH → quiz required, tutor off (${up1.status})`)
  const up2 = await callAs(ownerUid, 'PATCH', `/api/v1/schools/${SCHOOL}/classes/${CLASS}/courses/${a.id}`, { quiz_required: false, tutor_enabled: true })
  ok(up2.ok && up2.body?.settings?.quiz_required === false && up2.body?.settings?.tutor_enabled === true, `PATCH → back to quiz optional, tutor on (${up2.status})`)
}

console.log(`\n=== ${pass} passed, ${fail} failed ===`)
process.exit(fail ? 1 : 0)
