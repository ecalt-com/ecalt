import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Delete, Loader2, School as SchoolIcon } from 'lucide-react'
import clsx from 'clsx'
import PageMeta from '../components/PageMeta'
import ThemeToggle from '../components/ThemeToggle'
import PinPad from '../components/family/PinPad'
import ProfileAvatar from '../components/family/ProfileAvatar'
import { isStudentUid, useAuth } from '../lib/AuthContext'
import { apiErrorCode, type ApiError } from '../lib/api'
import { PICTURE_ICONS } from '../lib/pictureIcons'
import {
  classSignIn, formatJoinCode, lookupClass, schoolErrorMessage,
  type ClassLookup, type SecretKind, type StudentSecret,
} from '../lib/schoolApi'

const LAST_CODE_KEY = 'ecalt.lastClassCode'
const readLastCode = () => { try { return localStorage.getItem(LAST_CODE_KEY) ?? '' } catch { return '' } }
const saveLastCode = (code: string) => { try { localStorage.setItem(LAST_CODE_KEY, code) } catch { /* convenience only */ } }

type Who = { uid?: string; externalRef?: string; name: string; avatar: string | null; kind: SecretKind }

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageMeta title="Class sign-in" />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-8 flex flex-col items-center">
        <div className="w-full max-w-xl flex justify-between items-center mb-6">
          <img src="/logo.png" alt="ECALT" className="h-10 w-auto dark:brightness-0 dark:invert" />
          <ThemeToggle />
        </div>
        <div className="glass-card rounded-3xl p-6 sm:p-8 w-full max-w-xl">{children}</div>
      </div>
    </>
  )
}

// /class — student sign-in (frontend-changes.md §6.1): class code → pick your
// name (or type your roll number) → picture password or PIN.
export default function ClassSignIn() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { user, loading, signOut, signInWithClassToken } = useAuth()

  const [code, setCode] = useState(readLastCode)
  const [lookup, setLookup] = useState<ClassLookup | null>(null)
  const [who, setWho] = useState<Who | null>(null)
  const [roll, setRoll] = useState('')
  const [pictures, setPictures] = useState<number[]>([])
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(params.get('expired') ? 'school_session_expired' : null)
  const [shake, setShake] = useState(false)

  useEffect(() => {
    if (!shake) return
    const t = setTimeout(() => setShake(false), 400)
    return () => clearTimeout(t)
  }, [shake])

  if (!loading && user && isStudentUid(user.uid)) return <Navigate to="/my-classes" replace />

  if (!loading && user) {
    return (
      <Shell>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">Someone is signed in on this device</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
          {user.email ?? 'An ECALT account'} is signed in. Sign out first to use a class sign-in.
        </p>
        <button onClick={signOut} className="w-full btn-primary">Sign out</button>
      </Shell>
    )
  }

  const findClass = async (e: React.FormEvent) => {
    e.preventDefault()
    const clean = code.replace(/[\s-]/g, '').toUpperCase()
    if (clean.length !== 8 || busy) return
    setBusy(true)
    setError(null)
    try {
      setLookup(await lookupClass(clean))
      saveLastCode(clean)
    } catch (err) {
      setError(apiErrorCode(err) ?? 'unknown')
    } finally {
      setBusy(false)
    }
  }

  const submit = async (secret: StudentSecret) => {
    if (!who || busy) return
    setBusy(true)
    setError(null)
    try {
      const session = await classSignIn({
        class_code: code.replace(/[\s-]/g, '').toUpperCase(),
        ...(who.uid ? { student_uid: who.uid } : { external_ref: who.externalRef }),
        secret: { kind: who.kind, value: secret },
      })
      await signInWithClassToken(session.custom_token)
      navigate('/my-classes', { replace: true })
    } catch (err) {
      const errCode = apiErrorCode(err)
      setError(errCode ?? ((err as ApiError)?.status ? 'unknown' : 'network'))
      setPictures([])
      setPin('')
      setShake(true)
    } finally {
      setBusy(false)
    }
  }

  const pick = (index: number) => {
    if (busy || pictures.length >= 3) return
    const next = [...pictures, index]
    setPictures(next)
    if (next.length === 3) submit(next)
  }

  const message = error && (error === 'network'
    ? "Couldn't reach ECALT. Check the internet connection and try again."
    : schoolErrorMessage(error))

  // ── Step 1: class code ──
  if (!lookup) {
    return (
      <Shell>
        <div className="w-12 h-12 mb-4 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
          <SchoolIcon size={24} className="text-violet-600 dark:text-violet-400" />
        </div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">Sign in to your class</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">Type the class code from your card or the board.</p>
        <form onSubmit={findClass} className="space-y-4">
          <label className="block">
            <span className="sr-only">Class code</span>
            <input
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase().slice(0, 9))}
              placeholder="ABCD-EFGH"
              autoFocus
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              className="w-full px-4 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-2xl font-mono font-bold tracking-widest text-center text-slate-900 dark:text-slate-100 focus:outline-none focus:border-violet-400"
            />
          </label>
          {message && <p className="text-sm text-rose-600 dark:text-rose-400 text-center" role="alert">{message}</p>}
          <button type="submit" disabled={busy || code.replace(/[\s-]/g, '').length !== 8} className="w-full btn-primary !py-4 text-base flex items-center justify-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Next
          </button>
        </form>
      </Shell>
    )
  }

  // ── Step 2: who are you? ──
  if (!who) {
    return (
      <Shell>
        <button onClick={() => { setLookup(null); setError(null) }} className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-violet-600 mb-3">
          <ArrowLeft size={12} /> Different class
        </button>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">{lookup.class.name}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">{lookup.school.name} · class {formatJoinCode(code.replace(/[\s-]/g, '').toUpperCase())}</p>
        {lookup.roster_visible ? (
          lookup.students.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-400">Nobody in this class can sign in yet. Ask your teacher for your login card.</p>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">Tap your name</p>
              <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {lookup.students.map(s => (
                  <li key={s.uid}>
                    <button
                      onClick={() => { setWho({ uid: s.uid, name: s.display_name, avatar: s.avatar, kind: s.secret_kind }); setError(null) }}
                      className="w-full flex items-center gap-2 p-3 rounded-2xl border border-slate-200 dark:border-slate-700 hover:border-violet-400 hover:bg-violet-50 dark:hover:bg-violet-500/10 text-left transition-colors"
                    >
                      <ProfileAvatar name={s.display_name} avatar={s.avatar} />
                      <span className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{s.display_name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )
        ) : (
          <form
            onSubmit={e => { e.preventDefault(); if (roll.trim()) setWho({ externalRef: roll.trim(), name: `Roll ${roll.trim()}`, avatar: null, kind: 'pin' }) }}
            className="space-y-3"
          >
            <label className="block">
              <span className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">Your roll number</span>
              <input value={roll} onChange={e => setRoll(e.target.value)} maxLength={40} autoFocus className="w-full px-3 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-900 dark:text-slate-100 text-lg focus:outline-none focus:border-violet-400" />
            </label>
            <button type="submit" disabled={!roll.trim()} className="w-full btn-primary">Next</button>
          </form>
        )}
      </Shell>
    )
  }

  // ── Step 3: picture password or PIN ──
  return (
    <Shell>
      <button onClick={() => { setWho(null); setPictures([]); setPin(''); setError(null) }} className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-violet-600 mb-3">
        <ArrowLeft size={12} /> Not you?
      </button>
      <div className="flex items-center gap-3 mb-5">
        <ProfileAvatar name={who.name} avatar={who.avatar} />
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Hi {who.name.split(' ')[0]}!</h1>
      </div>

      {who.kind === 'picture' ? (
        <>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">Tap your 3 pictures in order</p>
          <div className={clsx('flex justify-center gap-3 mb-4', shake && 'motion-safe:animate-[shake_0.4s]')} aria-live="polite">
            {[0, 1, 2].map(slot => {
              const pic = pictures[slot] !== undefined ? PICTURE_ICONS[pictures[slot]] : null
              return (
                <span key={slot} className="w-14 h-14 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-600 flex items-center justify-center">
                  {pic ? <pic.Icon size={28} className={pic.color} aria-label={pic.name} /> : <span className="text-slate-300 text-sm">{slot + 1}</span>}
                </span>
              )
            })}
            <button
              onClick={() => setPictures(p => p.slice(0, -1))}
              disabled={!pictures.length || busy}
              aria-label="Undo last picture"
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-slate-400 hover:text-slate-700 disabled:opacity-30"
            ><Delete size={22} /></button>
          </div>
          <div className="grid grid-cols-4 gap-2 sm:gap-3">
            {PICTURE_ICONS.map(({ name, Icon, color }, index) => (
              <button
                key={name}
                onClick={() => pick(index)}
                disabled={busy || pictures.length >= 3}
                aria-label={name}
                className="aspect-square rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 flex items-center justify-center hover:border-violet-400 hover:scale-105 active:scale-95 transition-transform disabled:opacity-60"
              >
                <Icon size={34} className={color} aria-hidden="true" />
              </button>
            ))}
          </div>
        </>
      ) : (
        <form onSubmit={e => { e.preventDefault(); if (pin.length === 6) submit(pin) }} className={clsx('space-y-4', shake && 'motion-safe:animate-[shake_0.4s]')}>
          <PinPad value={pin} onChange={setPin} onSubmit={() => pin.length === 6 && submit(pin)} label="Your 6-digit PIN" id="student-pin" />
          <button type="submit" disabled={pin.length !== 6 || busy} className="w-full btn-primary !py-3 flex items-center justify-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Sign in
          </button>
        </form>
      )}

      {busy && who.kind === 'picture' && <Loader2 className="animate-spin text-violet-500 mx-auto mt-4" />}
      {message && <p className="mt-4 text-sm text-rose-600 dark:text-rose-400 text-center" role="alert">{message}</p>}
      {who.externalRef && (
        <button
          onClick={() => { setWho({ ...who, kind: who.kind === 'pin' ? 'picture' : 'pin' }); setPictures([]); setPin(''); setError(null) }}
          className="mt-4 block mx-auto text-xs text-slate-500 hover:text-violet-600"
        >
          {who.kind === 'pin' ? 'I use pictures instead' : 'I use a PIN instead'}
        </button>
      )}
    </Shell>
  )
}
