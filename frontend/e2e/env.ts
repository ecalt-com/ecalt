import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const E2E_DIR = path.dirname(fileURLToPath(import.meta.url))

/**
 * Minimal, dependency-free `.env.e2e` loader. Reads KEY=VALUE lines from
 * `frontend/e2e/.env.e2e` (gitignored) into process.env without overriding
 * anything already set in the real environment (CI wins over the file).
 */
function loadDotEnvFile() {
  const file = path.join(E2E_DIR, '.env.e2e')
  if (!fs.existsSync(file)) return
  for (const raw of fs.readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq === -1) continue
    const key = line.slice(0, eq).trim()
    let val = line.slice(eq + 1).trim()
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1)
    }
    if (process.env[key] === undefined) process.env[key] = val
  }
}

export interface E2EWebConfig {
  apiKey: string
  authDomain: string
  projectId: string
}

export interface E2EEnv {
  /** App under test. Default = the dev Vercel deployment. */
  baseURL: string
  /** Vercel "Protection Bypass for Automation" secret (empty on an unprotected target). */
  bypassSecret: string
  /** Path to the ecalt-dev Firebase service-account JSON (used to mint a custom token). */
  serviceAccountPath: string
  /** Test user to sign in as. uid wins; otherwise the email is looked up via Admin. */
  userEmail: string
  userUid: string
  /** Firebase Web SDK version pulled from the CDN in the auth setup — match the app's. */
  sdkVersion: string
  /** The dev deployment's Firebase *web* config (for the in-page custom-token sign-in). */
  webConfig: E2EWebConfig
  /** Where the signed-in storageState is written / read. */
  storageStatePath: string
  /** Fixtures on dev (see memory: reference-playwright-e2e-setup). */
  testSchoolId: string
  testSchoolName: string
}

/** Resolve a path relative to the frontend root (one level up from e2e/). */
function resolveFromFrontend(p: string): string {
  if (!p) return ''
  return path.isAbsolute(p) ? p : path.resolve(E2E_DIR, '..', p)
}

export function loadE2EEnv(): E2EEnv {
  loadDotEnvFile()
  return {
    baseURL: process.env.E2E_BASE_URL || 'https://ecalt-dev.vercel.app',
    bypassSecret: process.env.VERCEL_AUTOMATION_BYPASS_SECRET || '',
    serviceAccountPath: resolveFromFrontend(process.env.FIREBASE_SERVICE_ACCOUNT || ''),
    userEmail: process.env.E2E_USER_EMAIL || 'developer.biswambar@gmail.com',
    userUid: process.env.E2E_USER_UID || '',
    sdkVersion: process.env.E2E_FIREBASE_SDK_VERSION || '12.13.0',
    webConfig: {
      apiKey: process.env.E2E_FIREBASE_API_KEY || '',
      authDomain: process.env.E2E_FIREBASE_AUTH_DOMAIN || 'ecalt-dev.firebaseapp.com',
      projectId: process.env.E2E_FIREBASE_PROJECT_ID || 'ecalt-dev',
    },
    storageStatePath: path.join(E2E_DIR, '.auth', 'user.json'),
    testSchoolId: process.env.E2E_SCHOOL_ID || '1b48bd4b-60d9-43ed-a569-f80147c760c4',
    testSchoolName: process.env.E2E_SCHOOL_NAME || 'Invite Test School',
  }
}

/** Headers that get a request past Vercel deployment protection. */
export function bypassHeaders(env: E2EEnv): Record<string, string> {
  if (!env.bypassSecret) return {}
  return {
    'x-vercel-protection-bypass': env.bypassSecret,
    'x-vercel-set-bypass-cookie': 'true',
  }
}

/**
 * Validate the inputs the authenticated setup needs, with an actionable error
 * listing exactly what is missing (see e2e/README.md for where each comes from).
 */
export function assertAuthEnv(env: E2EEnv): void {
  const missing: string[] = []
  if (!env.bypassSecret) missing.push('VERCEL_AUTOMATION_BYPASS_SECRET (Vercel → Settings → Deployment Protection → Protection Bypass for Automation)')
  if (!env.serviceAccountPath) missing.push('FIREBASE_SERVICE_ACCOUNT (path to the ecalt-dev service-account JSON)')
  else if (!fs.existsSync(env.serviceAccountPath)) missing.push(`FIREBASE_SERVICE_ACCOUNT points at a missing file: ${env.serviceAccountPath}`)
  if (!env.webConfig.apiKey) missing.push('E2E_FIREBASE_API_KEY (ecalt-dev → Project settings → Web API Key)')
  if (missing.length) {
    throw new Error(
      `Playwright auth setup is missing required config:\n  - ${missing.join('\n  - ')}\n` +
      `Set them in frontend/e2e/.env.e2e (copy .env.e2e.example) or the environment. See e2e/README.md.`,
    )
  }
}
