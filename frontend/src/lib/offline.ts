// Offline reading (F2.3): a journey the learner chose to save stays readable
// without a connection. Stored in this browser's IndexedDB, keyed by account and
// active child profile so a shared device never shows one person's saved
// lessons to another; everything is cleared when the learner signs out.
import type { Journey } from './types'
import { getProfileHeaderValue } from './profileStore'

const DB_NAME = 'ecalt-offline'
const STORE = 'journeys'

interface SavedJourney {
  key: string
  journey: Journey
  contents: Record<string, string>
  savedAt: number
}

let scopeUid: string | null = null

/** AuthContext calls this whenever the signed-in user changes. */
export function setOfflineScope(uid: string | null): void {
  if (uid === scopeUid) return
  const signedOut = scopeUid !== null && uid === null
  scopeUid = uid
  if (signedOut) void clearOffline()
}

const keyFor = (journeyId: string) => `${scopeUid}|${getProfileHeaderValue() ?? ''}|${journeyId}`

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new Error('no indexedDB'))
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'key' })
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T | null> {
  try {
    const db = await open()
    return await new Promise<T | null>((resolve) => {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE))
      req.onsuccess = () => { resolve(req.result ?? null); db.close() }
      req.onerror = () => { resolve(null); db.close() }
    })
  } catch {
    return null  // private window or blocked storage: offline reading just isn't available
  }
}

const read = (journeyId: string) =>
  scopeUid ? run<SavedJourney>('readonly', (s) => s.get(keyFor(journeyId))) : Promise.resolve(null)

export async function saveJourneyOffline(journey: Journey, contents: Record<string, string>): Promise<boolean> {
  if (!scopeUid) return false
  const saved: SavedJourney = { key: keyFor(journey.id), journey, contents, savedAt: Date.now() }
  return (await run('readwrite', (s) => s.put(saved))) !== null
}

export const isSavedOffline = async (journeyId: string) => (await read(journeyId)) !== null
export const getOfflineJourney = async (journeyId: string) => (await read(journeyId))?.journey ?? null
export const getOfflineContent = async (journeyId: string, stepId: string) => (await read(journeyId))?.contents[stepId] ?? null
export async function removeOffline(journeyId: string): Promise<void> {
  if (scopeUid) await run('readwrite', (s) => s.delete(keyFor(journeyId)))
}
export async function clearOffline(): Promise<void> {
  await run('readwrite', (s) => s.clear())
}

/** A request that failed because the device is offline (not an HTTP error response). */
export const isNetworkFailure = (e: unknown) =>
  e instanceof TypeError || (typeof navigator !== 'undefined' && navigator.onLine === false)
