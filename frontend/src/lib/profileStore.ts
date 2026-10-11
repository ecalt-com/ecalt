// Module-level store for family profiles so non-React code (api.ts, raw
// fetches) can attach X-Profile-Id / X-Parent-Unlock without React context.
// Updated by ProfileContext. Contract: backend/plans/family-profiles/.

const PROFILE_KEY_PREFIX = 'ecalt.activeProfile.'
const UNLOCK_KEY = 'ecalt.parentUnlock'

let _accountUid: string | null = null
let _activeProfileId: string | null = null
let _pinPrompt: (() => Promise<boolean>) | null = null

function safeGet(storage: Storage, key: string): string | null {
  try { return storage.getItem(key) } catch { return null }
}
function safeSet(storage: Storage, key: string, value: string | null) {
  try {
    if (value === null) storage.removeItem(key)
    else storage.setItem(key, value)
  } catch { /* private mode / blocked storage — in-memory state still works */ }
}

// Called once the signed-in account is known. Restores this device's last
// chosen profile for that account (a device left in a child's profile stays
// there across reloads — that's the point of the lock).
export function setAccount(uid: string | null) {
  _accountUid = uid
  _activeProfileId = uid ? safeGet(localStorage, PROFILE_KEY_PREFIX + uid) : null
}

export function getAccountUid(): string | null {
  return _accountUid
}

// null = no choice made on this device yet (show the picker).
export function getStoredProfileChoice(): string | null {
  return _activeProfileId
}

export function setActiveProfile(profileUid: string | null) {
  _activeProfileId = profileUid
  if (_accountUid) safeSet(localStorage, PROFILE_KEY_PREFIX + _accountUid, profileUid)
  // Entering a child's profile must drop any parent unlock, or the child
  // inherits the parent's PIN session for its remaining minutes.
  if (isKidModeId(profileUid)) clearParentUnlock()
}

function isKidModeId(profileUid: string | null): boolean {
  return !!profileUid && !!_accountUid && profileUid !== _accountUid
}

export function isKidMode(): boolean {
  return isKidModeId(_activeProfileId)
}

// The profile the request should act as, or null for the account itself.
export function getProfileHeaderValue(): string | null {
  return isKidMode() ? _activeProfileId : null
}

// ── Parent unlock (PIN) ──────────────────────────────────────────────────────
// Kept in sessionStorage (this tab only) so a Stripe redirect or reload within
// the 15-minute window doesn't ask for the PIN again.

export function setParentUnlock(token: string, expiresInSeconds: number) {
  const exp = Date.now() + expiresInSeconds * 1000 - 5_000
  safeSet(sessionStorage, UNLOCK_KEY, JSON.stringify({ token, exp, uid: _accountUid }))
}

export function clearParentUnlock() {
  safeSet(sessionStorage, UNLOCK_KEY, null)
}

export function getParentUnlock(): string | null {
  const raw = safeGet(sessionStorage, UNLOCK_KEY)
  if (!raw) return null
  try {
    const { token, exp, uid } = JSON.parse(raw) as { token: string; exp: number; uid: string | null }
    if (Date.now() >= exp || uid !== _accountUid) {
      clearParentUnlock()
      return null
    }
    return token
  } catch {
    clearParentUnlock()
    return null
  }
}

// ProfileContext registers a handler that opens the PIN modal; api.ts calls it
// when the backend answers 403 parent_unlock_required, then retries once.
export function registerPinPrompt(fn: (() => Promise<boolean>) | null) {
  _pinPrompt = fn
}

export function requestParentUnlock(): Promise<boolean> {
  return _pinPrompt ? _pinPrompt() : Promise.resolve(false)
}
