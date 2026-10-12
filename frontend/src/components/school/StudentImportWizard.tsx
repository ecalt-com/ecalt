import { useState } from 'react'
import { AlertTriangle, CheckCircle2, FileText, Loader2, X } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { apiErrorCode, type ApiError } from '../../lib/api'
import { importStudents, schoolErrorMessage, type ImportReport } from '../../lib/schoolApi'
import { useSchoolPage } from '../../pages/school/SchoolLayout'

const TEMPLATE = 'name,grade,roll number,class,sign-in\nAsha R,5,101,5A,picture\nBen L,8,102,8B,pin\n'
const MAX_BYTES = 1_000_000

// CSV roster import: check (dry run) → fix → import (frontend-changes.md §4).
export default function StudentImportWizard({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const [csv, setCsv] = useState('')
  const [fileName, setFileName] = useState<string | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [done, setDone] = useState<ImportReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pickFile = async (file: File | undefined) => {
    setReport(null)
    setError(null)
    if (!file) return
    if (file.size > MAX_BYTES) { setError('That file is too large (1 MB max, about 2,000 students).'); return }
    setFileName(file.name)
    setCsv(await file.text())
  }

  const run = async (dryRun: boolean) => {
    if (!csv.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const token = await getToken()
      if (!token) throw new Error('Session expired — please sign in again.')
      const result = await importStudents(school.id, csv, dryRun, token)
      if (dryRun) setReport(result)
      else { setDone(result); onImported() }
    } catch (err) {
      const detail = (err as ApiError)?.detail as { report?: ImportReport } | undefined
      if (detail?.report) setReport(detail.report)
      setError(schoolErrorMessage(apiErrorCode(err), (err as Error)?.message))
    } finally {
      setBusy(false)
    }
  }

  const blocking = report ? report.errors.length > 0 || report.summary.rows_with_errors > 0 : true
  const problemRows = report?.rows.filter(r => r.errors.length || r.warnings.length) ?? []
  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE)}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Import students">
      <div className="glass-card rounded-3xl p-6 sm:p-7 max-w-2xl w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4 gap-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Import students from a CSV file</h2>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X size={16} /></button>
        </div>

        {done ? (
          <div className="text-center py-4">
            <CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-3" />
            <p className="text-sm text-slate-700 dark:text-slate-200 mb-1">
              Added {done.summary.create} and updated {done.summary.update} student{done.summary.create + done.summary.update === 1 ? '' : 's'}
              {done.summary.created_classes ? `, and created ${done.summary.created_classes} class${done.summary.created_classes === 1 ? '' : 'es'}` : ''}.
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
              New students can't sign in yet: open each class and print its login cards.
            </p>
            <button onClick={onClose} className="btn-primary">Done</button>
          </div>
        ) : (
          <>
            <ol className="text-sm text-slate-600 dark:text-slate-300 space-y-1 mb-4 list-decimal pl-5">
              <li>Export your class list as CSV with a <strong>name</strong> column. Optional: grade, roll number, class, sign-in (picture or pin).</li>
              <li>Check the file — nothing is saved until you import.</li>
              <li>Students with a roll number that's already here are updated instead of added twice.</li>
            </ol>
            <a href={templateHref} download="ecalt-students-template.csv" className="text-xs text-violet-600 dark:text-violet-400 underline">Download a template</a>

            <label className="mt-4 flex items-center gap-3 p-4 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-600 cursor-pointer hover:border-violet-400">
              <FileText size={20} className="text-slate-400" />
              <span className="text-sm text-slate-600 dark:text-slate-300">{fileName ?? 'Choose a .csv file'}</span>
              <input type="file" accept=".csv,text/csv" className="sr-only" onChange={e => pickFile(e.target.files?.[0])} />
            </label>

            {error && <p className="mt-3 text-xs text-rose-600 dark:text-rose-400" role="alert">{error}</p>}

            {report && (
              <div className="mt-5 space-y-3">
                <p className="text-sm text-slate-700 dark:text-slate-200">
                  {report.summary.rows} rows: <strong>{report.summary.create}</strong> new, <strong>{report.summary.update}</strong> updated
                  {report.summary.rows_with_errors > 0 && <>, <strong className="text-rose-600 dark:text-rose-400">{report.summary.rows_with_errors} with problems</strong></>}.
                  {report.summary.new_classes.length > 0 && <> New classes: {report.summary.new_classes.join(', ')}.</>}
                </p>
                {report.errors.map(e => (
                  <p key={e} className="text-xs text-rose-600 dark:text-rose-400 flex gap-1.5"><AlertTriangle size={13} className="shrink-0 mt-0.5" /> {e}</p>
                ))}
                {problemRows.length > 0 && (
                  <div className="max-h-56 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-700">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 sticky top-0">
                        <tr><th className="text-left px-3 py-2">Line</th><th className="text-left px-3 py-2">Name</th><th className="text-left px-3 py-2">Problem</th></tr>
                      </thead>
                      <tbody>
                        {problemRows.map(r => (
                          <tr key={r.line} className="border-t border-slate-200 dark:border-slate-700">
                            <td className="px-3 py-1.5 text-slate-500">{r.line}</td>
                            <td className="px-3 py-1.5 text-slate-700 dark:text-slate-200">{r.display_name || '—'}</td>
                            <td className="px-3 py-1.5">
                              {r.errors.map(e => <span key={e} className="block text-rose-600 dark:text-rose-400">{e}</span>)}
                              {r.warnings.map(w => <span key={w} className="block text-amber-600 dark:text-amber-400">{w}</span>)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            <div className="mt-5 flex gap-2 justify-end">
              <button onClick={() => run(true)} disabled={!csv.trim() || busy} className={clsx(report ? 'btn-ghost' : 'btn-primary', 'flex items-center gap-2')}>
                {busy && !report && <Loader2 size={14} className="animate-spin" />} {report ? 'Check again' : 'Check file'}
              </button>
              {report && (
                <button onClick={() => run(false)} disabled={blocking || busy} className="btn-primary flex items-center gap-2">
                  {busy && <Loader2 size={14} className="animate-spin" />} Import {report.summary.create + report.summary.update} students
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
