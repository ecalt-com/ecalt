import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import {
  onAuthStateChanged,
  signInWithPopup,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  getAdditionalUserInfo,
  type User,
} from 'firebase/auth'
import { firebaseAuth, googleProvider } from './firebase'

export type PostSignInPhase = 'none' | 'birth_year' | 'under_13' | 'consent_pending' | 'consent_sent'
export type UserRole = 'learner' | 'parent'

interface AuthContextValue {
  user: User | null
  loading: boolean
  needsOnboarding: boolean
  postSignInPhase: PostSignInPhase
  parentEmail: string | null
  role: UserRole | null
  signIn: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
  dismissOnboarding: () => void
  completeBirthYear: (birthYear: number, birthMonth?: number, country?: string) => Promise<void>
  submitParentalConsent: (parentEmail: string) => Promise<void>
  markConsentSent: (email: string) => void
  dismissPostSignIn: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  needsOnboarding: false,
  postSignInPhase: 'none',
  parentEmail: null,
  role: null,
  signIn: async () => {},
  signInWithEmail: async () => {},
  signOut: async () => {},
  getToken: async () => null,
  dismissOnboarding: () => {},
  completeBirthYear: async () => {},
  submitParentalConsent: async () => {},
  markConsentSent: () => {},
  dismissPostSignIn: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(firebaseAuth.currentUser)
  const [loading, setLoading] = useState(true)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  const [postSignInPhase, setPostSignInPhase] = useState<PostSignInPhase>('none')
  const [parentEmail, setParentEmail] = useState<string | null>(null)
  const [role, setRole] = useState<UserRole | null>(null)
  const [pendingBirthYear, setPendingBirthYear] = useState<number | null>(null)
  const [pendingBirthMonth, setPendingBirthMonth] = useState<number | null>(null)
  const [pendingCountry, setPendingCountry] = useState<string | null>(null)
  const userRef = useRef<User | null>(firebaseAuth.currentUser)
  const signingIn = useRef(false)
  const pendingUserRef = useRef<User | null>(null)
  // Tracks whether the initial auth state check (page load / refresh) has run.
  // Prevents the restore-session profile check from re-running on subsequent
  // auth changes triggered by signInWithPopup.
  const initialAuthCheckDone = useRef(false)

  // A pending teen who refreshes or re-logs in lands back on the parent-email
  // form; submitting it re-POSTs /users, whose teen branch requires birth_year
  // in the body. Recover it from the profile so the form still works.
  const enterConsentPending = (profile: { birth_year?: number | null; birth_month?: number | null }) => {
    if (profile.birth_year != null) setPendingBirthYear(profile.birth_year)
    if (profile.birth_month != null) setPendingBirthMonth(profile.birth_month)
    setPostSignInPhase('consent_pending')
  }

  useEffect(() => {
    const unsub = onAuthStateChanged(firebaseAuth, async u => {
      userRef.current = u
      setUser(u)
      setLoading(false)

      if (!u) {
        // Reset so the next page load re-checks the restored session.
        initialAuthCheckDone.current = false
        return
      }

      // On page load / refresh: a session was restored from IndexedDB but
      // postSignInPhase reset to 'none'. Re-check the backend so users who
      // never submitted their birth year can't bypass the gate with a refresh.
      if (!initialAuthCheckDone.current && !signingIn.current) {
        initialAuthCheckDone.current = true
        try {
          const token = await u.getIdToken()
          const res = await fetch('/api/v1/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ email: u.email, display_name: u.displayName, photo_url: u.photoURL }),
          })
          if (res.ok) {
            const profile = await res.json()
            if (profile.role) setRole(profile.role)
            if (profile.needs_birth_year) {
              pendingUserRef.current = u
              setPostSignInPhase('birth_year')
            } else if (profile.account_status === 'parental_consent_pending') {
              enterConsentPending(profile)
            } else if (profile.onboarding_done === false) {
              setNeedsOnboarding(true)
            }
          }
        } catch { /* non-critical */ }
      } else if (!initialAuthCheckDone.current) {
        // signIn() is in progress — it will handle all gate logic itself.
        initialAuthCheckDone.current = true
      }
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
      // Intercept to collect birth year before creating the backend user record.
      pendingUserRef.current = result.user
      setPostSignInPhase('birth_year')
      return
    }

    // Returning user — upsert backend profile, then check if age verification is still needed.
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
        if (profile.role) setRole(profile.role)
        if (profile.needs_birth_year === true) {
          pendingUserRef.current = result.user
          setPostSignInPhase('birth_year')
          return
        }
        if (profile.account_status === 'parental_consent_pending') {
          enterConsentPending(profile)
          return
        }
        if (profile.onboarding_done === false) {
          setNeedsOnboarding(true)
        }
      }
    } catch { /* non-critical */ }
  }

  // Kids login: managed children sign in with the email+password their parent
  // created. Same post-sign-in upsert flow as Google; managed children already
  // have birth_year set, so no gate appears.
  const signInWithEmail = async (email: string, password: string) => {
    const result = await signInWithEmailAndPassword(firebaseAuth, email, password)
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
        if (profile.role) setRole(profile.role)
        if (profile.account_status === 'parental_consent_pending') {
          enterConsentPending(profile)
          return
        }
        if (profile.onboarding_done === false) {
          setNeedsOnboarding(true)
        }
      }
    } catch { /* non-critical */ }
  }

  const completeBirthYear = async (birthYear: number, birthMonth?: number, country?: string) => {
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
          ...(birthMonth ? { birth_month: birthMonth } : {}),
          ...(country ? { country } : {}),
        }),
      })
      if (res.status === 403) {
        const data = await res.json().catch(() => ({}))
        // detail is an object {error: "under_13", message: "..."}
        const err = data.detail?.error || data.error || ''
        if (err === 'under_13') {
          await firebaseSignOut(firebaseAuth)
          pendingUserRef.current = null
          setPostSignInPhase('under_13')
          return
        }
      }
      if (res.status === 400) {
        const data = await res.json().catch(() => ({}))
        if (data.detail?.error === 'parent_email_required') {
          // Teen flow: store birth details and advance to parent email collection.
          setPendingBirthYear(birthYear)
          setPendingBirthMonth(birthMonth ?? null)
          setPendingCountry(country ?? null)
          setPostSignInPhase('consent_pending')
          return
        }
      }
      if (res.ok) {
        const profile = await res.json()
        if (profile.role) setRole(profile.role)
        pendingUserRef.current = null
        if (profile.account_status === 'parental_consent_pending') {
          setPendingBirthYear(birthYear)
          setPendingBirthMonth(birthMonth ?? null)
          setPendingCountry(country ?? null)
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

  const submitParentalConsent = async (email: string) => {
    const u = pendingUserRef.current ?? userRef.current
    if (!u || pendingBirthYear === null) throw new Error('Session expired. Please sign in again.')
    const token = await u.getIdToken()
    const res = await fetch('/api/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        email: u.email,
        display_name: u.displayName,
        photo_url: u.photoURL,
        birth_year: pendingBirthYear,
        ...(pendingBirthMonth ? { birth_month: pendingBirthMonth } : {}),
        ...(pendingCountry ? { country: pendingCountry } : {}),
        parent_email: email,
      }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Try again.')
    }
    pendingUserRef.current = null
    setPendingBirthYear(null)
    setPendingBirthMonth(null)
    setPendingCountry(null)
    setParentEmail(email)
    setPostSignInPhase('consent_sent')
  }

  const markConsentSent = (email: string) => {
    setParentEmail(email)
    setPostSignInPhase('consent_sent')
  }

  const dismissPostSignIn = () => {
    setPostSignInPhase('none')
    pendingUserRef.current = null
    setParentEmail(null)
    setPendingBirthYear(null)
    setPendingBirthMonth(null)
    setPendingCountry(null)
  }

  const signOut = async () => {
    await firebaseSignOut(firebaseAuth)
    setNeedsOnboarding(false)
    setPostSignInPhase('none')
    pendingUserRef.current = null
    setParentEmail(null)
    setRole(null)
    setPendingBirthYear(null)
    setPendingBirthMonth(null)
    setPendingCountry(null)
  }

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
      user, loading, needsOnboarding, postSignInPhase, parentEmail, role,
      signIn, signInWithEmail, signOut, getToken,
      dismissOnboarding, completeBirthYear, submitParentalConsent, markConsentSent, dismissPostSignIn,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
