import { defineConfig, devices } from '@playwright/test'
import { bypassHeaders, loadE2EEnv } from './e2e/env'

// E2E against the ECALT frontend. Default target = the dev Vercel deployment
// (behind Vercel deployment protection); override with E2E_BASE_URL.
// See e2e/README.md for the required env vars and how auth works.
const env = loadE2EEnv()
const isLocal = /localhost|127\.0\.0\.1/.test(env.baseURL)

export default defineConfig({
  testDir: './e2e',
  outputDir: './e2e/.output',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { outputFolder: 'e2e/.report', open: 'never' }]],
  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: env.baseURL,
    // The bypass header rides on every request (page loads AND the same-origin
    // /api/* calls the SPA makes), so the dev backend is reachable too.
    extraHTTPHeaders: bypassHeaders(env),
    // Test in dark mode by default (user preference). The app's theme is driven
    // by localStorage.ecalt_theme (seeded in auth.setup + the public project),
    // and colorScheme covers any prefers-color-scheme media.
    colorScheme: 'dark',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    // 1. Mints a Firebase session and writes e2e/.auth/user.json.
    { name: 'setup', testMatch: /auth\.setup\.ts$/ },

    // 2. Signed-in specs reuse that storageState.
    {
      name: 'authed',
      testMatch: /.*\.authed\.spec\.ts$/,
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: env.storageStatePath },
    },

    // 3. Public specs need no login (but still need the Vercel bypass). Seed the
    //    dark-mode preference since there's no storageState from setup here.
    {
      name: 'public',
      testMatch: /.*\.public\.spec\.ts$/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: { cookies: [], origins: [{ origin: env.baseURL, localStorage: [{ name: 'ecalt_theme', value: 'dark' }] }] },
      },
    },
  ],

  // Only auto-start a dev server when pointed at localhost.
  webServer: isLocal
    ? {
        command: 'npm run dev',
        url: env.baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
})
