import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'

interface GoogleSignInButtonProps {
  onSuccess?: () => void
  label?: string
}

export default function GoogleSignInButton({
  onSuccess,
  label = 'Continue with Google',
}: GoogleSignInButtonProps) {
  const { signIn } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSignIn = async () => {
    setLoading(true)
    setError(null)
    try {
      await signIn()
      onSuccess?.()
    } catch (err: unknown) {
      const e = err as { code?: string }
      if (e.code !== 'auth/popup-closed-by-user') {
        setError('Sign-in failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleSignIn}
        disabled={loading}
        className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/70 text-slate-700 dark:text-slate-200 text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
      >
        {loading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
            <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
            <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
            <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
          </svg>
        )}
        {loading ? 'Signing in…' : label}
      </button>
      {error && <p className="text-xs text-rose-500 text-center">{error}</p>}
    </div>
  )
}
