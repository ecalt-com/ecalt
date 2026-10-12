import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Printer } from 'lucide-react'
import PageMeta from '../../components/PageMeta'
import ProfileAvatar from '../../components/family/ProfileAvatar'
import SecretView from '../../components/school/SecretView'
import { useAuth } from '../../lib/AuthContext'
import { useSchool } from '../../lib/SchoolContext'
import { apiErrorCode } from '../../lib/api'
import { formatJoinCode, getLoginCards, schoolErrorMessage, type LoginCards } from '../../lib/schoolApi'

// /school/print/cards/:classId — printable sign-in cards (frontend-changes.md §5).
// Secrets are stored hashed, so printing cards issues new ones: "everyone"
// replaces every student's picture password / PIN; "missing only" gives one
// to students who have none and leaves the rest unchanged.
export default function LoginCardsPrint() {
  const { classId = '' } = useParams()
  const { user, loading: authLoading, getToken } = useAuth()
  const { activeSchool, loaded } = useSchool()
  const navigate = useNavigate()
  const [cards, setCards] = useState<LoginCards | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  const issue = async (reset: boolean) => {
    if (!activeSchool || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      setCards(await getLoginCards(activeSchool.id, classId, { reset }, token))
    } catch (err) {
      setError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setBusy(false)
    }
  }

  const host = window.location.host

  if (!loaded || authLoading) {
    return <div className="min-h-screen flex items-center justify-center"><Loader2 className="animate-spin text-violet-500" /></div>
  }

  return (
    <>
      <PageMeta title="Login cards" />
      <div className="min-h-screen bg-[var(--bg-primary)] print:bg-white px-4 py-8 print:p-0">
        <div className="max-w-4xl mx-auto">
          <div className="print:hidden mb-6 space-y-4">
            <Link to={`/school/classes/${classId}`} className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400">
              <ArrowLeft size={12} /> Back to the class
            </Link>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Login cards</h1>
            {!cards ? (
              <div className="glass-card rounded-2xl p-5 space-y-3">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  For safety, sign-ins are stored scrambled, so a card can only show a sign-in made just now.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => issue(false)} disabled={busy} className="btn-ghost border border-slate-200 dark:border-slate-700">
                    Cards for students without a sign-in
                  </button>
                  <button onClick={() => issue(true)} disabled={busy} className="btn-primary !py-2 flex items-center gap-2">
                    {busy && <Loader2 size={14} className="animate-spin" />} New sign-ins for the whole class
                  </button>
                </div>
                <p className="text-xs text-amber-700 dark:text-amber-300">"New sign-ins" replaces every student's current picture password or PIN — old cards stop working.</p>
                {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}
              </div>
            ) : (
              <div className="flex items-center gap-3 flex-wrap">
                <button onClick={() => window.print()} className="btn-primary !py-2 flex items-center gap-2"><Printer size={14} /> Print</button>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {cards.cards.length} cards. Hand them out in class; keep them out of sight like any password.
                </p>
              </div>
            )}
          </div>

          {cards && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 print:grid-cols-2 print:gap-3">
              {cards.cards.map(card => (
                <div key={card.uid} className="rounded-2xl border border-slate-300 bg-white p-4 text-slate-900 break-inside-avoid">
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mb-3">
                    <span>{cards.school_name} · {cards.class.name}</span>
                    <span>{host}/class</span>
                  </div>
                  <div className="flex items-center gap-3 mb-3">
                    <ProfileAvatar name={card.display_name} avatar={card.avatar} size="sm" />
                    <span className="text-base font-bold">{card.display_name}</span>
                  </div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">1. Class code</p>
                  <p className="font-mono text-lg font-bold mb-2">{formatJoinCode(cards.class.join_code)}</p>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
                    2. {card.secret_kind === 'picture' ? 'Your pictures, in order' : 'Your PIN'}
                  </p>
                  {card.secret !== null
                    ? <SecretView kind={card.secret_kind} secret={card.secret} size="sm" />
                    : <p className="text-sm text-slate-500">Use the sign-in you already have.</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
