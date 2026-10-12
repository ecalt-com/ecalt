import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, ShieldAlert } from 'lucide-react'
import clsx from 'clsx'
import DpaModal from '../../components/school/DpaModal'
import { useAuth } from '../../lib/AuthContext'
import { useSchool } from '../../lib/SchoolContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode, type ApiError } from '../../lib/api'
import { schoolErrorMessage, updateSchool, type SchoolSettings as Settings } from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const fieldCls = 'w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 disabled:opacity-60'

const TOGGLES: { key: 'teachers_can_create_students' | 'login_roster_visible' | 'teacher_transcript_access'; label: string; hint: string }[] = [
  { key: 'teachers_can_create_students', label: 'Teachers can add students', hint: 'Otherwise only school admins create student accounts.' },
  { key: 'login_roster_visible', label: 'Show class lists on the sign-in page', hint: 'Students pick their name after entering the class code. Turn off for older students, who type a username instead.' },
  { key: 'teacher_transcript_access', label: 'Teachers can read students’ tutor chats', hint: 'For their own classes only. Students are told when this is on.' },
]

const NUMBERS: { key: 'student_daily_tutor_messages' | 'student_daily_quiz_sets'; label: string }[] = [
  { key: 'student_daily_tutor_messages', label: 'Tutor messages per student per day' },
  { key: 'student_daily_quiz_sets', label: 'Quiz sets per student per day' },
]

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })

// /school/settings (frontend-changes.md §3).
export default function SchoolSettings() {
  const { school, setSchool } = useSchoolPage()
  const { getToken } = useAuth()
  const { can, refresh } = useSchool()
  const { addToast } = useToast()
  const editable = can('manage_settings')

  const [name, setName] = useState(school.name)
  const [settings, setSettings] = useState<Settings>(school.settings)
  const [retention, setRetention] = useState(school.settings.delete_originals_after_days?.toString() ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<{ message: string; fields: string[] } | null>(null)
  const [showDpa, setShowDpa] = useState(false)

  useEffect(() => {
    setName(school.name)
    setSettings(school.settings)
    setRetention(school.settings.delete_originals_after_days?.toString() ?? '')
  }, [school])

  const dirty = name.trim() !== school.name
    || JSON.stringify({ ...settings, delete_originals_after_days: retention ? Number(retention) : null })
      !== JSON.stringify(school.settings)

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editable || !dirty || saving || !name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const updated = await updateSchool(school.id, {
        ...(name.trim() !== school.name ? { name: name.trim() } : {}),
        settings: { ...settings, delete_originals_after_days: retention ? Number(retention) : null },
      }, token)
      setSchool({ ...school, ...updated })
      if (name.trim() !== school.name) refresh()
      addToast('Settings saved ✓')
    } catch (err) {
      const detail = (err as ApiError)?.detail as { fields?: string[] } | undefined
      setError({
        message: schoolErrorMessage(apiErrorCode(err), (err as Error)?.message),
        fields: detail?.fields ?? [],
      })
    } finally {
      setSaving(false)
    }
  }

  const invalid = (key: string) => error?.fields.some(f => f.endsWith(key)) ?? false

  return (
    <div className="space-y-5">
      <form onSubmit={save} className="glass-card rounded-2xl p-5 space-y-5">
        {!editable && (
          <p className="text-xs text-slate-500 dark:text-slate-400">Only school admins can change these settings.</p>
        )}

        <div>
          <label htmlFor="school-name" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">School name</label>
          <input id="school-name" value={name} onChange={e => setName(e.target.value)} maxLength={120} disabled={!editable} className={fieldCls} />
        </div>

        <fieldset className="space-y-3">
          <legend className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">Students and classes</legend>
          {TOGGLES.map(t => (
            <label key={t.key} className={clsx('flex items-start gap-3', editable && 'cursor-pointer')}>
              <input
                type="checkbox"
                checked={settings[t.key]}
                disabled={!editable}
                onChange={e => setSettings(s => ({ ...s, [t.key]: e.target.checked }))}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
              />
              <span>
                <span className="block text-sm text-slate-800 dark:text-slate-100">{t.label}</span>
                <span className="block text-xs text-slate-500 dark:text-slate-400">{t.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <fieldset className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <legend className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 col-span-full">Daily limits (protect the school's AI budget)</legend>
          {NUMBERS.map(n => (
            <div key={n.key}>
              <label htmlFor={n.key} className="block text-xs text-slate-600 dark:text-slate-400 mb-1.5">{n.label}</label>
              <input
                id={n.key}
                type="number"
                min={0}
                max={500}
                value={settings[n.key]}
                disabled={!editable}
                onChange={e => setSettings(s => ({ ...s, [n.key]: Number(e.target.value) }))}
                aria-invalid={invalid(n.key)}
                className={clsx(fieldCls, invalid(n.key) && '!border-rose-400')}
              />
            </div>
          ))}
        </fieldset>

        <div>
          <label htmlFor="retention" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
            Delete uploaded documents after (days)
          </label>
          <input
            id="retention"
            type="number"
            min={1}
            max={3650}
            placeholder="Keep while courses use them"
            value={retention}
            disabled={!editable}
            onChange={e => setRetention(e.target.value)}
            aria-invalid={invalid('delete_originals_after_days')}
            className={clsx(fieldCls, 'sm:max-w-xs', invalid('delete_originals_after_days') && '!border-rose-400')}
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Courses keep their content after the original file is deleted.</p>
        </div>

        {error && <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">{error.message}</p>}

        {editable && (
          <button type="submit" disabled={!dirty || saving || !name.trim()} className="btn-primary flex items-center gap-2">
            {saving && <Loader2 size={14} className="animate-spin" />} Save settings
          </button>
        )}
      </form>

      <div className="glass-card rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-2">Data processing agreement</h2>
        {school.dpa_accepted && school.dpa_accepted_at ? (
          <p className="text-sm text-slate-600 dark:text-slate-300 flex items-center gap-2">
            <CheckCircle2 size={15} className="text-emerald-500" />
            Version {school.dpa_version} accepted on {fmtDate(school.dpa_accepted_at)}.
          </p>
        ) : (
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm text-amber-700 dark:text-amber-300 flex items-center gap-2">
              <ShieldAlert size={15} />
              {school.dpa_version ? `Version ${school.dpa_current_version} needs accepting.` : 'Not accepted yet.'}
              {!can('accept_dpa') && ' Only the school owner can accept it.'}
            </p>
            {can('accept_dpa') && (
              <button onClick={() => setShowDpa(true)} className="btn-primary !py-2 !px-4">Review &amp; accept</button>
            )}
          </div>
        )}
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
