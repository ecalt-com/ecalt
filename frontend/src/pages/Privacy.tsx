import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, Trash2, Loader2, AlertTriangle, X } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import Navigation from '../components/Navigation'
import { useAuth } from '../lib/AuthContext'

interface UserProfile {
  consent_given_at?: string | null
  consent_status?: string | null
}

export default function Privacy() {
  const navigate = useNavigate()
  const { user, loading: authLoading, getToken, signOut } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [exporting, setExporting] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteInput, setDeleteInput] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return
    getToken().then(token => {
      if (!token) return
      fetch('/api/v1/users/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setProfile(data) })
        .catch(() => {})
    })
  }, [user, getToken])

  const handleExport = async () => {
    setExporting(true)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/users/me/export', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'ecalt-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* non-critical */ } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (deleteInput !== 'DELETE') return
    setDeleting(true)
    setDeleteError(null)
    try {
      const token = await getToken()
      const res = await fetch('/api/v1/users/me', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = typeof body.detail === 'string' ? body.detail : ''
        if (detail.includes('already_deleted')) {
          setDeleteError('This account has already been deleted.')
        } else {
          setDeleteError('Something went wrong. Please try again.')
        }
        return
      }
      await signOut()
      navigate('/', { replace: true, state: { message: 'Your account has been deleted.' } })
    } catch {
      setDeleteError('Something went wrong. Please try again.')
    } finally {
      setDeleting(false)
    }
  }

  if (authLoading || !user) return null

  const consentDate = profile?.consent_given_at
    ? new Date(profile.consent_given_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null

  const accountStatus = profile?.consent_status === 'pending'
    ? 'Under review (parental consent pending)'
    : 'Standard'

  return (
    <>
      <PageMeta title="Privacy & Data" description="Manage your ECALT data and privacy settings." />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 pt-24 pb-16">
        <div className="max-w-2xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 mb-8 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>

          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-8">Privacy &amp; Data</h1>

          {/* Your data */}
          <section className="mb-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
              Your data
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Download size={16} className="text-violet-500" />
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Download my data</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                  Get a copy of all your ECALT data as a JSON file.
                </p>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-60"
                >
                  {exporting
                    ? <><Loader2 size={12} className="animate-spin" /> Exporting…</>
                    : <><Download size={12} /> Download</>}
                </button>
              </div>

              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Trash2 size={16} className="text-rose-500" />
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Delete my account</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                  Permanently remove your account and all associated data.
                </p>
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all"
                >
                  <Trash2 size={12} /> Delete account
                </button>
              </div>
            </div>
          </section>

          {/* Consent */}
          <section className="mb-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
              Consent
            </h2>
            <div className="glass-card rounded-2xl p-5">
              {consentDate ? (
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  You agreed to our Terms of Service and Privacy Policy on{' '}
                  <span className="font-medium">{consentDate}</span>.
                </p>
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">Consent date not available.</p>
              )}
              <a
                href="/privacy-policy"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-3 text-xs text-violet-600 dark:text-violet-400 hover:underline"
              >
                Update consent preferences →
              </a>
            </div>
          </section>

          {/* Age & Account Status */}
          <section>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
              Age &amp; Account Status
            </h2>
            <div className="glass-card rounded-2xl p-5">
              <p className="text-sm text-slate-700 dark:text-slate-300">
                Account type:{' '}
                <span className={`font-medium ${profile?.consent_status === 'pending' ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                  {profile ? accountStatus : '—'}
                </span>
              </p>
            </div>
          </section>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} className="text-rose-500 shrink-0 mt-0.5" />
                <h2 id="delete-modal-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Delete your account?
                </h2>
              </div>
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteInput(''); setDeleteError(null) }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">This will permanently delete:</p>
            <ul className="text-xs text-slate-600 dark:text-slate-400 mb-4 space-y-1 list-none">
              {[
                'Your profile and learning history',
                'All journeys and progress',
                'All conversations',
                'Your Mind Signatures',
                'Your subscription (if active)',
              ].map(item => (
                <li key={item} className="flex items-center gap-1.5">
                  <span className="text-rose-400">•</span> {item}
                </li>
              ))}
            </ul>
            <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-4">This cannot be undone.</p>

            <div className="mb-4">
              <label htmlFor="delete-confirm-input" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                Type DELETE to confirm:
              </label>
              <input
                id="delete-confirm-input"
                type="text"
                value={deleteInput}
                onChange={e => { setDeleteInput(e.target.value); if (deleteError) setDeleteError(null) }}
                autoComplete="off"
                spellCheck={false}
                aria-describedby={deleteError ? 'delete-error' : undefined}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-rose-400"
              />
              {deleteError && (
                <p id="delete-error" className="mt-1.5 text-xs text-rose-600 dark:text-rose-400" role="alert">
                  {deleteError}
                </p>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteInput(''); setDeleteError(null) }}
                className="flex-1 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteInput !== 'DELETE' || deleting}
                className="flex-1 px-4 py-2 rounded-xl text-sm font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {deleting
                  ? <><Loader2 size={14} className="animate-spin" /> Deleting…</>
                  : 'Delete Account'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
