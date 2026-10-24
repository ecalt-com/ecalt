# Frontend E2E (Playwright)

End-to-end tests for the ECALT SPA, targeting the **dev Vercel deployment**
(`https://ecalt-dev.vercel.app`) by default.

Two things make the dev target non-trivial, and this harness handles both:

1. **Vercel deployment protection** — the dev deployment sits behind an SSO wall.
   We send a *Protection Bypass for Automation* secret as the
   `x-vercel-protection-bypass` header on every request (page loads and the
   same-origin `/api/*` calls alike).
2. **Firebase Google-popup auth** — Google blocks automated OAuth. Instead the
   setup mints a Firebase **custom token** for the test user (Admin SDK), signs
   in with it under `browserLocalPersistence`, and saves the resulting
   `storageState`. No manual login, CI-friendly.

## One-time setup

```bash
cd frontend
npm install                       # @playwright/test + firebase-admin already in devDeps
npx playwright install chromium   # browser binary
cp e2e/.env.e2e.example e2e/.env.e2e
```

Then fill in `e2e/.env.e2e`:

| Var | Where to get it |
|---|---|
| `VERCEL_AUTOMATION_BYPASS_SECRET` | Vercel → project `ecalt` → Settings → Deployment Protection → **Protection Bypass for Automation** → generate |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase console (project **ecalt-dev**) → Project settings → Service accounts → Generate new private key. Save the JSON somewhere gitignored (e.g. `frontend/e2e/service-account.json`) and point this at it |
| `E2E_FIREBASE_API_KEY` | Firebase console (**ecalt-dev**) → Project settings → General → Your apps → Web API Key |

`E2E_USER_EMAIL` defaults to the project owner; everything else has a working
default. `.env.e2e`, `.auth/`, and `service-account*.json` are gitignored.

## Running

```bash
npm run test:e2e            # all projects (runs auth setup first)
npm run test:e2e:public     # public smoke only — no login, no service account
npm run test:e2e:ui         # Playwright UI mode
npm run test:e2e:headed     # headed (watch it drive)
npm run test:e2e:report     # open the last HTML report
```

Run against a **local** dev server instead:

```bash
E2E_BASE_URL=http://localhost:3000 npm run test:e2e
# (no Vercel bypass needed; Playwright auto-starts `npm run dev`)
```

## Layout

```
e2e/
├── env.ts                   # env loader + validation + bypass headers
├── auth.setup.ts            # project "setup": mints the session → .auth/user.json
├── smoke.public.spec.ts     # project "public": no login
├── school.authed.spec.ts    # project "authed": reuses .auth/user.json
├── .env.e2e.example         # template (copy to .env.e2e)
└── .auth/user.json          # minted storageState (gitignored)
```

Spec naming decides the project: `*.public.spec.ts` (no auth) vs
`*.authed.spec.ts` (needs the login).

## How the custom-token sign-in works (and the one thing to verify)

`auth.setup.ts` serves a blank, CSP-free page on the **real app origin** via
route interception, imports the version-matched Firebase Web SDK from the CDN,
and signs in with the custom token under `browserLocalPersistence` — so the
session lands in `localStorage` (which `storageState` captures; IndexedDB would
not).

The app itself uses Firebase's **default** persistence (IndexedDB-preferring).
On the first real run, confirm the app picks up the localStorage session on load
(Firebase's default persistence also searches localStorage, so it should). If it
doesn't, the fallback is a persistent browser profile — see the session memory
`reference-playwright-e2e-setup`.

> The dev service-account key and bypass secret are dev-only, but still secrets —
> keep them out of git (they are gitignored here).
