import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, ChevronRight, Loader2 } from 'lucide-react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { isStudentUid, useAuth } from '../lib/AuthContext'
import { getUserProfile, request } from '../lib/api'
import type { Journey } from '../lib/types'

// GET /journeys also returns in-progress journeys with their step counts.
interface StudentJourneys {
  journeys: Journey[]
  in_progress: (Journey & { steps_done: number })[]
}

interface StudentProfile {
  display_name: string | null
  school?: { id: string; name: string } | null
  student?: { classes: { id: string; name: string }[] } | null
}

// /my-classes — a school student's home (frontend-changes.md §6.2). Lists the
// published courses assigned to their classes (GET /journeys is scoped to
// that for students). Due dates and per-class grouping arrive with the
// student home endpoint (SC-502).
export default function StudentHome() {
  const { user, loading, getToken } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [courses, setCourses] = useState<Journey[] | null>(null)
  const [progress, setProgress] = useState<Record<string, number>>({})
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!loading && (!user || !isStudentUid(user.uid))) navigate(user ? '/' : '/class', { replace: true })
  }, [loading, user, navigate])

  useEffect(() => {
    if (!user || !isStudentUid(user.uid)) return
    ;(async () => {
      try {
        const token = await getToken()
        if (!token) return
        const [me, list] = await Promise.all([
          getUserProfile(token),
          request<StudentJourneys>('/api/v1/journeys', undefined, token),
        ])
        setProfile(me as unknown as StudentProfile)
        setCourses(list.journeys)
        setProgress(Object.fromEntries(list.in_progress.map(j => [j.id, j.steps_done])))
      } catch {
        setError(true)
      }
    })()
  }, [user, getToken])

  if (loading || !user) {
    return <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center"><Loader2 className="animate-spin text-violet-500" /></div>
  }

  const firstName = profile?.display_name?.split(' ')[0]

  return (
    <>
      <PageMeta title="My classes" />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{firstName ? `Hi ${firstName}!` : 'My classes'}</h1>
          {profile?.school && (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {profile.school.name}{profile.student?.classes.length ? ` · ${profile.student.classes.map(c => c.name).join(', ')}` : ''}
            </p>
          )}

          {error && <p className="mt-6 text-sm text-rose-600 dark:text-rose-400" role="alert">Couldn't load your courses. Refresh the page to try again.</p>}
          {courses === null && !error && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>}

          {courses?.length === 0 && (
            <div className="glass-card rounded-2xl p-10 text-center mt-6">
              <BookOpen size={28} className="text-violet-500 mx-auto mb-3" />
              <p className="text-sm text-slate-600 dark:text-slate-300">Your teacher hasn't added any courses yet.</p>
            </div>
          )}

          {courses && courses.length > 0 && (
            <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {courses.map(c => {
                const done = progress[c.id] ?? 0
                const total = c.steps.length
                return (
                  <li key={c.id}>
                    <Link to={`/journey/${c.id}`} className="glass-card rounded-2xl p-4 flex items-center gap-3 hover:border-violet-300 transition-colors">
                      <span className="text-2xl" aria-hidden="true">{c.icon}</span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">{c.title}</span>
                        <span className="block text-xs text-slate-500 dark:text-slate-400">{done ? `${done} of ${total} steps done` : `${total} steps`}</span>
                        {total > 0 && (
                          <span className="block mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                            <span className="block h-full bg-violet-500" style={{ width: `${Math.round((done / total) * 100)}%` }} />
                          </span>
                        )}
                      </span>
                      <ChevronRight size={16} className="text-slate-400 shrink-0" />
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </>
  )
}
