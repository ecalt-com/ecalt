import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileText, Loader2, Trash2, Upload } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../lib/AuthContext'
import { useToast } from '../../lib/ToastContext'
import { apiErrorCode } from '../../lib/api'
import {
  completeDocument, deleteDocument, listDocuments, requestDocumentUpload, schoolErrorMessage, uploadToStorage,
  type DocumentStatus, type SchoolDocument,
} from '../../lib/schoolApi'
import { useSchoolPage } from './SchoolLayout'

const ACCEPT = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const PROCESSING: DocumentStatus[] = ['pending_upload', 'uploaded', 'extracting']

const STATUS: Record<DocumentStatus, { label: string; cls: string }> = {
  pending_upload: { label: 'Uploading…', cls: 'text-slate-500 dark:text-slate-400' },
  uploaded:       { label: 'Queued', cls: 'text-slate-500 dark:text-slate-400' },
  extracting:     { label: 'Reading…', cls: 'text-violet-600 dark:text-violet-400' },
  ready:          { label: 'Ready', cls: 'text-emerald-600 dark:text-emerald-400' },
  needs_ocr:      { label: 'Scanned — no text to read', cls: 'text-amber-600 dark:text-amber-400' },
  failed:         { label: 'Failed', cls: 'text-rose-600 dark:text-rose-400' },
  deleted:        { label: 'Deleted', cls: 'text-slate-400' },
}

const fmtSize = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)

export default function SchoolDocuments() {
  const { school } = useSchoolPage()
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [docs, setDocs] = useState<SchoolDocument[] | null>(null)
  const [uploading, setUploading] = useState<{ name: string; pct: number } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      setDocs((await listDocuments(school.id, token)).documents)
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    }
  }, [school.id, getToken, addToast])

  useEffect(() => { load() }, [load])

  // Poll while anything is still uploading/extracting so statuses update live.
  useEffect(() => {
    if (!docs?.some(d => PROCESSING.includes(d.status))) return
    const t = window.setInterval(load, 4000)
    return () => window.clearInterval(t)
  }, [docs, load])

  const onPick = async (file: File) => {
    const token = await getToken()
    if (!token) return
    setUploading({ name: file.name, pct: 0 })
    try {
      const ticket = await requestDocumentUpload(
        school.id, { filename: file.name, size_bytes: file.size, mime: file.type }, token,
      )
      await uploadToStorage(ticket.upload_url, file, f => setUploading({ name: file.name, pct: Math.round(f * 100) }))
      await completeDocument(school.id, ticket.document_id, token)
      addToast(`Uploaded ${file.name} ✓`)
      await load()
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    } finally {
      setUploading(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (d: SchoolDocument) => {
    const token = await getToken()
    if (!token) return
    if (!window.confirm(`Delete "${d.filename}"? Any published courses keep their content.`)) return
    try {
      await deleteDocument(school.id, d.id, token)
      addToast('Document deleted')
      await load()
    } catch (err) {
      addToast(schoolErrorMessage(apiErrorCode(err)), 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-lg">
          Upload the lesson material (PDF or Word) you want to build a course from. We read the text so the
          course builder can use it — your files stay private to your school.
        </p>
        <label className={clsx('btn-primary flex items-center gap-2 cursor-pointer shrink-0', uploading && 'opacity-60 pointer-events-none')}>
          <Upload size={16} /> Upload document
          <input
            ref={fileRef} type="file" accept={ACCEPT} className="hidden" disabled={!!uploading}
            onChange={e => { const f = e.target.files?.[0]; if (f) onPick(f) }}
          />
        </label>
      </div>

      {uploading && (
        <div className="glass-card rounded-2xl p-4">
          <div className="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-200">
            <Loader2 size={16} className="animate-spin text-violet-500 shrink-0" />
            <span className="truncate">Uploading {uploading.name}…</span>
            <span className="ml-auto tabular-nums text-slate-500">{uploading.pct}%</span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div className="h-full bg-violet-500 transition-all" style={{ width: `${uploading.pct}%` }} />
          </div>
        </div>
      )}

      {docs === null ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-violet-500" /></div>
      ) : docs.length === 0 ? (
        <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-500 dark:text-slate-400">
          No documents yet. Upload a PDF or Word file to get started.
        </div>
      ) : (
        <div className="glass-card rounded-2xl divide-y divide-slate-100 dark:divide-slate-800">
          {docs.map(d => {
            const s = STATUS[d.status]
            return (
              <div key={d.id} className="flex items-center gap-3 p-4">
                <FileText size={18} className="text-slate-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">{d.filename}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {fmtSize(d.size_bytes)}{d.page_count ? ` · ${d.page_count} pages` : ''}
                  </div>
                </div>
                <div className={clsx('flex items-center gap-1.5 text-xs font-medium shrink-0', s.cls)}>
                  {d.status === 'ready' && <CheckCircle2 size={14} />}
                  {PROCESSING.includes(d.status) && d.status !== 'uploaded' && <Loader2 size={13} className="animate-spin" />}
                  {(d.status === 'failed' || d.status === 'needs_ocr') && <AlertTriangle size={14} />}
                  <span title={d.error_code ?? undefined}>
                    {d.status === 'failed' && d.error_code ? schoolErrorMessage(d.error_code, 'Failed') : s.label}
                  </span>
                </div>
                <button
                  onClick={() => remove(d)} aria-label={`Delete ${d.filename}`}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 shrink-0"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
