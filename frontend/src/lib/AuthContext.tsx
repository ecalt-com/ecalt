import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  type User,
} from 'firebase/auth'
import { firebaseAuth, googleProvider } from './firebase'

interface AuthContextValue {
  user: User | null
  loading: boolean
  needsOnboarding: boolean
  signIn: () => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
  dismissOnboarding: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  needsOnboarding: false,
  signIn: async () => {},
  signOut: async () => {},
  getToken: async () => null,
  dismissOnboarding: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  // Keep a ref to the current user so getToken always sees the latest value
  // without needing to be recreated on every user change.
  const userRef = useRef<User | null>(null)

  useEffect(() => {
    const unsub = onAuthStateChanged(firebaseAuth, u => {
      userRef.current = u
      setUser(u)
      setLoading(false)
    })
    return unsub
  }, [])

  const signIn = async () => {
    const result = await signInWithPopup(firebaseAuth, googleProvider)
    try {
      const token = await result.user.getIdToken()
      const res = await fetch('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          email: result.user.email,
          display_name: result.user.displayName,
          photo_url: result.user.photoURL,
        }),
      })
      if (res.ok) {
        const profile = await res.json()
        if (profile.onboarding_done === false) {
          setNeedsOnboarding(true)
        }
      }
    } catch { /* non-critical */ }
  }

  const signOut = async () => {
    await firebaseSignOut(firebaseAuth)
    setNeedsOnboarding(false)
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
    <AuthContext.Provider value={{ user, loading, needsOnboarding, signIn, signOut, getToken, dismissOnboarding }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
