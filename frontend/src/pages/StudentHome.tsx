import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, CheckCircle2, ChevronRight, Loader2 } from 'lucide-react'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { isStudentUid, useAuth } from '../lib/AuthContext'
import { getUserProfile } from '../lib/api'
import { getStudentHome, type StudentClass } from '../lib/schoolApi'

interface StudentProfile {
  display_name: string | null
  school?: { id: string; name: string } | null
}

function dueLabel(iso: string | null): { text: string; overdue: boolean } | null {
  if (!iso) return null
  const due = new Date(iso)
  return { text: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), overdue: due.getTime() < Date.now() }
}

// /my-classes — a school student's home (frontend-changes.md §9). Groups the
// published courses assigned to each of the student's classes, with progress,
// a due date and the teacher's name (GET /school-student/home).
export default function StudentHome() {
  const { user, loading, getToken } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [classes, setClasses] = useState<StudentClass[] | null>(null)
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
        const [me, home] = await Promise.all([getUserProfile(token), getStudentHome(token)])
        setProfile(me as unknown as StudentProfile)
        setClasses(home.classes)
      } catch {
        setError(true)
      }
    })()
  }, [user, getToken])

  if (loading || !user) {
    return <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center"><Loader2 className="animate-spin text-violet-500" /></div>
  }

  const firstName = profile?.display_name?.split(' ')[0]
  const hasCourses = classes?.some(c => c.courses.length > 0)

  return (
    <>
      <PageMeta title="My classes" />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{firstName ? `Hi ${firstName}!` : 'My classes'}</h1>
          {profile?.school && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{profile.school.name}</p>}

          {error && <p className="mt-6 text-sm text-rose-600 dark:text-rose-400" role="alert">Couldn't load your courses. Refresh the page to try again.</p>}
          {classes === null && !error && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>}

          {classes && !hasCourses && !error && (
            <div className="glass-card rounded-2xl p-10 text-center mt-6">
              <BookOpen size={28} className="text-violet-500 mx-auto mb-3" />
              <p className="text-sm text-slate-600 dark:text-slate-300">Your teacher hasn't added any courses yet.</p>
            </div>
          )}

          {classes?.filter(c => c.courses.length > 0).map(cls => (
            <section key={cls.class_id} className="mt-8">
              <div className="flex items-baseline justify-between gap-2 mb-3">
                <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{cls.class_name}</h2>
                {cls.teacher_name && <span className="text-xs text-slate-400 dark:text-slate-500">{cls.teacher_name}</span>}
              </div>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {cls.courses.map(c => {
                  const due = dueLabel(c.due_at)
                  return (
                    <li key={c.assignment_id}>
                      <Link to={`/journey/${c.journey_id}`} className="glass-card rounded-2xl p-4 flex items-center gap-3 hover:border-violet-300 transition-colors h-full">
                        <span className="text-2xl shrink-0" aria-hidden="true">{c.icon}</span>
                        <span className="flex-1 min-w-0">
                          <span className="flex items-center gap-1.5">
                            <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">{c.title}</span>
                            {c.completed && <CheckCircle2 size={14} className="text-emerald-500 shrink-0" aria-label="Completed" />}
                          </span>
                          <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <span>{c.done_steps ? `${c.done_steps} of ${c.total_steps} steps` : `${c.total_steps} steps`}</span>
                            {due && <span className={due.overdue ? 'text-rose-600 dark:text-rose-400 font-medium' : ''}>· Due {due.text}</span>}
                          </span>
                          {c.total_steps > 0 && (
                            <span className="block mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                              <span className="block h-full bg-violet-500" style={{ width: `${c.percent}%` }} />
                            </span>
                          )}
                        </span>
                        <ChevronRight size={16} className="text-slate-400 shrink-0" />
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </>
  )
}
