// Seed one in-course tutor conversation for a school student (so the teacher
// transcripts drill-down has content). Signs in as the student via a minted
// custom token and POSTs to /chat/stream (journey_tutor), draining the SSE.
//   node e2e/seed_tutor_chat.mjs <studentUid> <journeyId> ["message"]
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { cert, getApps, initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'

const [, , studentUid, journeyId, msgArg] = process.argv
if (!studentUid || !journeyId) {
  console.error('usage: node e2e/seed_tutor_chat.mjs <studentUid> <journeyId> ["message"]')
  process.exit(2)
}
const message = msgArg || 'Can you explain the water cycle in simple words?'

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
const ct = await getAuth(app).createCustomToken(studentUid)
const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${apiKey}`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ token: ct, returnSecureToken: true }),
}).then(r => r.json())
if (!ex.idToken) { console.error('token exchange failed', ex); process.exit(1) }

const res = await fetch(`${base}/api/v1/chat/stream`, {
  method: 'POST',
  headers: { authorization: `Bearer ${ex.idToken}`, 'x-vercel-protection-bypass': bypass, 'content-type': 'application/json' },
  body: JSON.stringify({ message, interaction_type: 'journey_tutor', journey_id: journeyId }),
})
if (!res.ok) { console.error('chat/stream failed', res.status, await res.text()); process.exit(1) }
// Drain the SSE so the assistant reply is persisted to the conversation.
const text = await res.text()
const conv = (text.match(/"conversation_id"\s*:\s*"([^"]+)"/) || [])[1]
console.log(`seeded tutor chat for ${studentUid} on ${journeyId}${conv ? ` (conversation ${conv})` : ''}`)
process.exit(0)
