// Installable app (F2.3): register the small service worker in production, except
// for school students, whose classroom devices are shared.
import { isStudentSession } from './telemetryPrivacy'

const supported = () => typeof navigator !== 'undefined' && 'serviceWorker' in navigator

export function registerServiceWorker(): void {
  if (!supported() || !import.meta.env.PROD || isStudentSession()) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* installability is a bonus */ })
  })
}

/** Remove the worker (and the caches it made) from this browser. */
export async function unregisterServiceWorkers(): Promise<void> {
  if (!supported()) return
  try {
    for (const reg of await navigator.serviceWorker.getRegistrations()) await reg.unregister()
    if ('caches' in window) for (const key of await caches.keys()) if (key.startsWith('ecalt-')) await caches.delete(key)
  } catch { /* nothing to clean up */ }
}
