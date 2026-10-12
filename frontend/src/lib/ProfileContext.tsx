import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { isStudentUid, useAuth } from './AuthContext'
import { getUserProfile } from './api'
import { getProfiles, type PickerAccount, type PickerProfile } from './familyApi'
import {
  getParentUnlock,
  getStoredProfileChoice,
  isKidMode as storeIsKidMode,
  registerPinPrompt,
  setActiveProfile,
} from './profileStore'
import PinPrompt from '../components/family/PinPrompt'

// Family profiles (backend/plans/family-profiles): one parent login, a
// "Who's learning?" picker, and a parent PIN to leave a child's profile.

export interface ActiveProfile {
  uid: string
  display_name: string | null
  avatar: string | null
  photo_url: string | null
  isChild: boolean
  age_group: PickerProfile['age_group']
}

interface ProfileContextValue {
  loaded: boolean
  account: PickerAccount | null
  profiles: PickerProfile[]
  pinSet: boolean
  activeProfile: ActiveProfile | null
  isKidMode: boolean
  // Has child profiles but this device hasn't picked one yet → show the picker.
  needsPicker: boolean
  refresh: () => Promise<void>
  // Resolves false if a required PIN was cancelled.
  switchTo: (uid: string) => Promise<boolean>
  // Prompt for the PIN unless a fresh unlock already exists (or no PIN needed).
  ensureParentUnlock: (reason?: string) => Promise<boolean>
  markPinSet: () => void
}

const ProfileContext = createContext<ProfileContextValue>({
  loaded: false,
  account: null,
  profiles: [],
  pinSet: false,
  activeProfile: null,
  isKidMode: false,
  needsPicker: false,
  refresh: async () => {},
  switchTo: async () => false,
  ensureParentUnlock: async () => false,
  markPinSet: () => {},
})

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const { user, getToken, postSignInPhase, requireOnboarding } = useAuth()
  const [loaded, setLoaded] = useState(false)
  const [account, setAccount] = useState<PickerAccount | null>(null)
  const [profiles, setProfiles] = useState<PickerProfile[]>([])
  const [pinSet, setPinSet] = useState(false)
  const [choice, setChoice] = useState<string | null>(null)
  const [prompt, setPrompt] = useState<{ reason?: string } | null>(null)
  const pending = useRef<{ promise: Promise<boolean>; resolve: (ok: boolean) => void } | null>(null)

  const askPin = useCallback((reason?: string): Promise<boolean> => {
    if (pending.current) return pending.current.promise
    let resolve!: (ok: boolean) => void
    const promise = new Promise<boolean>(r => { resolve = r })
    pending.current = { promise, resolve }
    setPrompt({ reason })
    return promise
  }, [])

  const finishPrompt = (ok: boolean) => {
    setPrompt(null)
    pending.current?.resolve(ok)
    pending.current = null
  }

  useEffect(() => {
    registerPinPrompt(() => askPin())
    return () => registerPinPrompt(null)
  }, [askPin])

  const refresh = useCallback(async () => {
    if (!user) return
    try {
      const token = await getToken()
      if (!token) return
      const data = await getProfiles(token)
      setAccount(data.account)
      setProfiles(data.profiles)
      setPinSet(data.pin_set)

      let stored = getStoredProfileChoice()
      // A stored child profile that's gone (deleted, unlinked, claimed) → picker.
      if (stored && stored !== data.account.uid && !data.profiles.some(p => p.uid === stored)) {
        setActiveProfile(null)
        stored = null
      }
      // A parent who just unlocked (e.g. created their first profile) is
      // already the active profile — don't bounce them to the picker.
      if (!stored && data.profiles.length > 0 && getParentUnlock()) {
        setActiveProfile(data.account.uid)
        stored = data.account.uid
      }
      setChoice(stored)
    } catch {
      // No backend row yet (mid sign-up) or transient error: behave as a
      // plain account with no profiles.
      setAccount(null)
      setProfiles([])
    } finally {
      setLoaded(true)
    }
  }, [user, getToken])

  useEffect(() => {
    if (!user) {
      setLoaded(false)
      setAccount(null)
      setProfiles([])
      setChoice(null)
      return
    }
    // Wait for the sign-up gates — the account row may not exist yet.
    if (postSignInPhase !== 'none') return
    // School students have no family profiles.
    if (isStudentUid(user.uid)) { setLoaded(true); return }
    refresh()
  }, [user, postSignInPhase, refresh])

  const kidMode = loaded && storeIsKidMode() && choice !== null
  const activeChild = kidMode ? profiles.find(p => p.uid === choice) ?? null : null

  // A child profile has its own onboarding (interests), separate from the parent's.
  useEffect(() => {
    if (!activeChild) return
    let cancelled = false
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const me = await getUserProfile(token)
        if (!cancelled && me.onboarding_done === false) requireOnboarding()
      } catch { /* non-critical */ }
    })()
    return () => { cancelled = true }
  }, [activeChild?.uid, getToken, requireOnboarding]) // eslint-disable-line react-hooks/exhaustive-deps

  const activeProfile: ActiveProfile | null = activeChild
    ? {
        uid: activeChild.uid,
        display_name: activeChild.display_name,
        avatar: activeChild.avatar,
        photo_url: null,
        isChild: true,
        age_group: activeChild.age_group,
      }
    : account
      ? {
          uid: account.uid,
          display_name: account.display_name,
          avatar: account.avatar,
          photo_url: account.photo_url,
          isChild: false,
          age_group: 'adult',
        }
      : null

  const ensureParentUnlock = useCallback(async (reason?: string): Promise<boolean> => {
    if (getParentUnlock()) return true
    if (!pinSet && profiles.length === 0) return true  // no PIN → backend asks for none
    return askPin(reason)
  }, [pinSet, profiles.length, askPin])

  const switchTo = useCallback(async (uid: string): Promise<boolean> => {
    if (!account) return false
    const goingToParent = uid === account.uid
    const leavingChild = storeIsKidMode()
    // PIN to leave a child's profile, or to pick the parent on a device that
    // hasn't chosen yet (a child may be the one holding it).
    const needsPin = profiles.length > 0 && (leavingChild || (goingToParent && choice === null))
    if (needsPin && !(await ensureParentUnlock(
      goingToParent ? 'Enter your parent PIN to switch to your profile.' : 'Enter your parent PIN to switch profiles.'
    ))) {
      return false
    }
    setActiveProfile(uid)
    // Full reload: every context and cached request restarts as the new profile.
    window.location.assign('/learn')
    return true
  }, [account, profiles.length, choice, ensureParentUnlock])

  const value: ProfileContextValue = {
    loaded,
    account,
    profiles,
    pinSet,
    activeProfile,
    isKidMode: kidMode,
    needsPicker: loaded && profiles.length > 0 && choice === null,
    refresh,
    switchTo,
    ensureParentUnlock,
    markPinSet: () => setPinSet(true),
  }

  return (
    <ProfileContext.Provider value={value}>
      {children}
      {prompt && <PinPrompt reason={prompt.reason} onDone={finishPrompt} />}
    </ProfileContext.Provider>
  )
}

export const useProfiles = () => useContext(ProfileContext)
