// Mark a course's steps complete AS A STUDENT, in order, via the dev API — used
// to populate real progress for the class progress matrix demo (the UI completes
// steps by passing a per-step quiz, which isn't deterministic in an E2E).
//   node e2e/student_do_course.mjs <studentUid> <journeyId> [howManySteps]
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'

const [, , studentUid, journeyId, nArg] = process.argv
if (!studentUid || !journeyId) {
  console.error('usage: node e2e/student_do_course.mjs <studentUid> <journeyId> [howManySteps]')
  process.exit(2)
}

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
const saPath = path.resolve(DIR, '..', env.FIREBASE_SERVICE_ACCOUNT || 'e2e/service-account.json')

const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(JSON.parse(readFileSync(saPath, 'utf8'))) })
const customToken = await getAuth(app).createCustomToken(studentUid)
const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${apiKey}`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ token: customToken, returnSecureToken: true }),
}).then(r => r.json())
const token = ex.idToken
if (!token) { console.error('token exchange failed', ex); process.exit(1) }

const call = (method, p) => fetch(`${base}${p}`, {
  method, headers: { authorization: `Bearer ${token}`, 'x-vercel-protection-bypass': bypass },
}).then(async r => ({ status: r.status, body: await r.text() }))

const j = r => { try { return JSON.parse(r.body) } catch { return r.body } }

const journey = j(await call('GET', `/api/v1/journeys/${journeyId}`))
const steps = (journey.steps || []).map(s => s.id)
const limit = nArg ? Math.min(Number(nArg), steps.length) : steps.length
console.log(`${studentUid} → "${journey.title}": ${steps.length} steps, completing ${limit}`)
let done = 0
for (const stepId of steps.slice(0, limit)) {
  const r = await call('POST', `/api/v1/progress/${journeyId}/${stepId}`)
  if (r.status === 200) done++
  else { console.log(`  step ${stepId}: ${r.status} ${r.body}`); break }
}
console.log(`completed ${done}/${limit} steps`)
process.exit(0)
