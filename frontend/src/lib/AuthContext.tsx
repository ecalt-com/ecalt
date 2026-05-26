import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  getAdditionalUserInfo,
  type User,
} from 'firebase/auth'
import { firebaseAuth, googleProvider } from './firebase'

export type PostSignInPhase = 'none' | 'birth_year' | 'under_13' | 'consent_pending' | 'consent_sent'

interface AuthContextValue {
  user: User | null
  loading: boolean
  needsOnboarding: boolean
  postSignInPhase: PostSignInPhase
  parentEmail: string | null
  signIn: () => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
  dismissOnboarding: () => void
  completeBirthYear: (birthYear: number) => Promise<void>
  markConsentSent: (email: string) => void
  dismissPostSignIn: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  needsOnboarding: false,
  postSignInPhase: 'none',
  parentEmail: null,
  signIn: async () => {},
  signOut: async () => {},
  getToken: async () => null,
  dismissOnboarding: () => {},
  completeBirthYear: async () => {},
  markConsentSent: () => {},
  dismissPostSignIn: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // firebaseAuth.currentUser is populated synchronously from the persisted
  // session (IndexedDB/localStorage), so initializing here avoids the 1-second
  // flash while onAuthStateChanged fires asynchronously.
  const [user, setUser] = useState<User | null>(firebaseAuth.currentUser)
  const [loading, setLoading] = useState(true)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  const [postSignInPhase, setPostSignInPhase] = useState<PostSignInPhase>('none')
  const [parentEmail, setParentEmail] = useState<string | null>(null)
  const userRef = useRef<User | null>(firebaseAuth.currentUser)
  const signingIn = useRef(false)
  const pendingUserRef = useRef<User | null>(null)

  useEffect(() => {
    const unsub = onAuthStateChanged(firebaseAuth, u => {
      userRef.current = u
      setUser(u)
      setLoading(false)
    })
    return unsub
  }, [])

  const signIn = async () => {
    if (signingIn.current) return
    signingIn.current = true
    let result
    try {
      result = await signInWithPopup(firebaseAuth, googleProvider)
    } finally {
      signingIn.current = false
    }

    const isNewUser = getAdditionalUserInfo(result)?.isNewUser ?? false

    if (isNewUser) {
      // Intercept to collect birth year before creating the backend user record
      pendingUserRef.current = result.user
      setPostSignInPhase('birth_year')
      return
    }

    // Returning user — upsert backend profile, then check if age verification is still needed
    try {
      const token = await result.user.getIdToken()
      const res = await fetch('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          email: result.user.email,
          display_name: result.user.displayName,
          photo_url: result.user.photoURL,
        }),
      })
      if (res.ok) {
        const profile = await res.json()
        if (profile.needs_birth_year === true) {
          // Existing account without age verification — show gate retroactively
          pendingUserRef.current = result.user
          setPostSignInPhase('birth_year')
          return
        }
        if (profile.consent_status === 'pending') {
          setPostSignInPhase('consent_pending')
          return
        }
        if (profile.onboarding_done === false) {
          setNeedsOnboarding(true)
        }
      }
    } catch { /* non-critical */ }
  }

  const completeBirthYear = async (birthYear: number) => {
    // pendingUserRef is set for new users; fall back to userRef for returning users
    // who are being age-gated retroactively.
    const u = pendingUserRef.current ?? userRef.current
    if (!u) return
    try {
      const token = await u.getIdToken()
      const res = await fetch('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          email: u.email,
          display_name: u.displayName,
          photo_url: u.photoURL,
          birth_year: birthYear,
        }),
      })
      if (res.status === 403) {
        const data = await res.json().catch(() => ({}))
        const err = typeof data.error === 'string' ? data.error : (typeof data.detail === 'string' ? data.detail : '')
        if (err === 'under_13') {
          // Sign out immediately — don't leave a partial Firebase session
          await firebaseSignOut(firebaseAuth)
          pendingUserRef.current = null
          setPostSignInPhase('under_13')
          return
        }
      }
      if (res.ok) {
        const profile = await res.json()
        pendingUserRef.current = null
        if (profile.consent_status === 'pending') {
          setPostSignInPhase('consent_pending')
          return
        }
        setPostSignInPhase('none')
        if (profile.onboarding_done === false) {
          setNeedsOnboarding(true)
        }
      }
    } catch { /* non-critical */ }
  }

  const markConsentSent = (email: string) => {
    setParentEmail(email)
    setPostSignInPhase('consent_sent')
  }

  const dismissPostSignIn = () => {
    setPostSignInPhase('none')
    pendingUserRef.current = null
    setParentEmail(null)
  }

  const signOut = async () => {
    await firebaseSignOut(firebaseAuth)
    setNeedsOnboarding(false)
    setPostSignInPhase('none')
    pendingUserRef.current = null
    setParentEmail(null)
  }

  // Use the ref so this function is stable and always returns a fresh token
  // from the React-state-tracked user, not the Firebase singleton.
  const getToken = useCallback(async (): Promise<string | null> => {
    const u = userRef.current
    if (!u) return null
    try {
      return await u.getIdToken()
    } catch {
      return null
    }
  }, [])

  const dismissOnboarding = () => setNeedsOnboarding(false)

  return (
    <AuthContext.Provider value={{
      user, loading, needsOnboarding, postSignInPhase, parentEmail,
      signIn, signOut, getToken,
      dismissOnboarding, completeBirthYear, markConsentSent, dismissPostSignIn,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
