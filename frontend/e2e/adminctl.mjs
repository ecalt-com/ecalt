// Dev admin/API helper for E2E setup & teardown (no secrets inside — reads
// e2e/.env.e2e). Signs in as the test user via a minted custom token and calls
// the dev API with the Vercel bypass header.
//
// As a CLI:   node e2e/adminctl.mjs <METHOD> <PATH> [jsonBody]
// As a module: import { call, cfg } from './adminctl.mjs'
import { readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
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

export const cfg = {
  apiKey: env.E2E_FIREBASE_API_KEY,
  bypass: env.VERCEL_AUTOMATION_BYPASS_SECRET,
  base: env.E2E_BASE_URL || 'https://ecalt-dev.vercel.app',
  email: env.E2E_USER_EMAIL || 'developer.biswambar@gmail.com',
  sa: path.resolve(DIR, '..', env.FIREBASE_SERVICE_ACCOUNT || 'e2e/service-account.json'),
}

let idTokenPromise
async function idToken() {
  if (!idTokenPromise) {
    idTokenPromise = (async () => {
      const app = getApps().length ? getApps()[0] : initializeApp({ credential: cert(JSON.parse(readFileSync(cfg.sa, 'utf8'))) })
      const user = await getAuth(app).getUserByEmail(cfg.email)
      const customToken = await getAuth(app).createCustomToken(user.uid)
      const ex = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${cfg.apiKey}`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token: customToken, returnSecureToken: true }),
      }).then(r => r.json())
      return ex.idToken
    })()
  }
  return idTokenPromise
}

export async function call(method, apiPath, body) {
  const res = await fetch(`${cfg.base}${apiPath}`, {
    method,
    headers: {
      authorization: `Bearer ${await idToken()}`,
      'x-vercel-protection-bypass': cfg.bypass,
      ...(body ? { 'content-type': 'application/json' } : {}),
    },
    body: body || undefined,
  })
  return { status: res.status, ok: res.ok, body: await res.text() }
}

// CLI mode
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [, , method = 'GET', apiPath = '/api/v1/schools/mine', bodyArg] = process.argv
  const r = await call(method, apiPath, bodyArg)
  console.log(r.status)
  console.log(r.body)
  process.exit(r.ok ? 0 : 1)
}
