import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Circle, GraduationCap, ShieldAlert, Users, Wallet, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import DpaModal from '../../components/school/DpaModal'
import { useSchool } from '../../lib/SchoolContext'
import { useToast } from '../../lib/ToastContext'
import { useSchoolPage } from './SchoolLayout'

function Stat({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string }) {
  return (
    <div className="glass-card rounded-2xl p-4">
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-1">
        <Icon size={13} /> {label}
      </div>
      <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
    </div>
  )
}

// /school — overview + first-run checklist (frontend-changes.md §2–3).
export default function SchoolDashboard() {
  const { school, setSchool } = useSchoolPage()
  const { can, refresh } = useSchool()
  const { addToast } = useToast()
  const [showDpa, setShowDpa] = useState(false)

  const checklist = [
    { done: school.dpa_accepted, label: 'Accept the data processing agreement', to: '/school/settings', owner: true },
    { done: school.staff_count > 1, label: 'Invite your teachers', to: '/school/staff', owner: false },
  ]

  return (
    <div className="space-y-5">
      {!school.dpa_accepted && (
        <div className="rounded-2xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-2.5 min-w-0">
            <ShieldAlert size={16} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800 dark:text-amber-300">
              {can('accept_dpa')
                ? 'Accept the data processing agreement before adding students.'
                : "Students can be added once the school's owner accepts the data processing agreement."}
            </p>
          </div>
          {can('accept_dpa') && (
            <button onClick={() => setShowDpa(true)} className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors">
              Review &amp; accept
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat icon={Users} label="Staff" value={String(school.staff_count)} />
        <Stat icon={GraduationCap} label="Students" value={`${school.student_count} / ${school.seat_limit}`} />
        {can('view_budget') && school.monthly_ai_budget_cents !== undefined && (
          <Stat icon={Wallet} label="Monthly AI budget" value={`$${(school.monthly_ai_budget_cents / 100).toFixed(2)}`} />
        )}
      </div>

      <div className="glass-card rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Getting started</h2>
        <ul className="space-y-1">
          {checklist.map(item => (
            <li key={item.label}>
              <Link
                to={item.to}
                className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-100/70 dark:hover:bg-slate-800/50 transition-colors"
              >
                <span className="flex items-center gap-2.5 text-sm">
                  {item.done
                    ? <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
                    : <Circle size={16} className="text-slate-300 dark:text-slate-600 shrink-0" />}
                  <span className={clsx(item.done ? 'text-slate-400 line-through' : 'text-slate-700 dark:text-slate-200')}>
                    {item.label}
                  </span>
                  {item.owner && !item.done && !can('accept_dpa') && <span className="text-xs text-slate-400">owner</span>}
                </span>
                <ChevronRight size={14} className="text-slate-400 shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-4 px-3 text-xs text-slate-500 dark:text-slate-400">
          Coming next: student accounts, classes, and courses built from your own PDF and Word documents.
        </p>
      </div>

      {showDpa && (
        <DpaModal
          school={school}
          onClose={() => setShowDpa(false)}
          onAccepted={updated => {
            setSchool({ ...school, ...updated })
            setShowDpa(false)
            refresh()
            addToast('Agreement accepted ✓')
          }}
        />
      )}
    </div>
  )
}
