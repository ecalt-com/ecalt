import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider, OAuthProvider } from 'firebase/auth'

const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
})

export const firebaseAuth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()
// Always show the account chooser: on shared family devices, silently reusing
// the child's Google session would sign the parent in as the child.
googleProvider.setCustomParameters({ prompt: 'select_account' })

// Microsoft (work/school) sign-in for school staff (D8). Off until the
// microsoft.com provider is enabled in the Firebase console (Azure app
// registration) and VITE_MICROSOFT_SIGNIN=true is set on Vercel.
export const microsoftProvider = new OAuthProvider('microsoft.com')
microsoftProvider.setCustomParameters({ prompt: 'select_account' })
export const MICROSOFT_SIGNIN_ENABLED = import.meta.env.VITE_MICROSOFT_SIGNIN === 'true'
