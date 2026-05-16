import { createContext, useContext, useEffect, useState } from 'react'
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
  signIn: () => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  signIn: async () => {},
  signOut: async () => {},
  getToken: async () => null,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsub = onAuthStateChanged(firebaseAuth, u => {
      setUser(u)
      setLoading(false)
    })
    return unsub
  }, [])

  const signIn = async () => {
    await signInWithPopup(firebaseAuth, googleProvider)
  }

  const signOut = async () => {
    await firebaseSignOut(firebaseAuth)
  }

  const getToken = async (): Promise<string | null> => {
    if (!firebaseAuth.currentUser) return null
    return firebaseAuth.currentUser.getIdToken()
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut, getToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
