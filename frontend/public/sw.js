/* ECALT service worker (F2.3). Deliberately small:
 *  - /assets/* (fingerprinted build files): cache-first, so the app opens offline.
 *  - page navigations: network-first; offline, serve the last app shell we saw.
 *  - everything else, and every /api/ call: straight to the network, never cached
 *    (responses are per person and per child profile, and devices are shared).
 * Not registered for school students (lib/pwa.ts). */
const ASSETS = 'ecalt-assets-v1'
const SHELL = 'ecalt-shell-v1'
const KEEP = [ASSETS, SHELL]

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (!KEEP.includes(key)) await caches.delete(key)
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await fetch(req)
        if (res.ok && res.headers.get('content-type')?.includes('text/html')) {
          (await caches.open(SHELL)).put('/', res.clone())
        }
        return res
      } catch {
        return (await caches.match('/')) || new Response('You are offline.', { status: 503, headers: { 'content-type': 'text/plain' } })
      }
    })())
    return
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith((async () => {
      const cache = await caches.open(ASSETS)
      const hit = await cache.match(req)
      if (hit) return hit
      const res = await fetch(req)
      if (res.ok) cache.put(req, res.clone())
      return res
    })())
  }
})
