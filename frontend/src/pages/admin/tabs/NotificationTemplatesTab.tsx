import { useState, useRef } from 'react'
import { Save, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import type { NotificationTemplateRow } from '../types'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

// Extract {variable} tokens from a template string
function extractVars(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1])
}

interface Props {
  templates: NotificationTemplateRow[]
  setTemplates: React.Dispatch<React.SetStateAction<NotificationTemplateRow[]>>
  templateVariables: Record<string, string[]>
  getToken: () => Promise<string | null>
}

export function NotificationTemplatesTab({ templates, setTemplates, templateVariables, getToken }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const selectedRow = templates.find(t => t.notification_type === selected) ?? null
  const knownVars = selected ? (templateVariables[selected] ?? []) : []
  const usedVars = extractVars(editText)
  const unknownVars = usedVars.filter(v => !knownVars.includes(v))

  function handleSelect(row: NotificationTemplateRow) {
    if (dirty && !confirm('You have unsaved changes. Discard them?')) return
    setSelected(row.notification_type)
    setEditText(row.template)
    setDirty(false)
  }

  function insertVariable(varName: string) {
    const el = textareaRef.current
    if (!el) return
    const start = el.selectionStart ?? editText.length
    const end = el.selectionEnd ?? editText.length
    const token = `{${varName}}`
    const next = editText.slice(0, start) + token + editText.slice(end)
    setEditText(next)
    setDirty(true)
    // Restore cursor after the inserted token
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + token.length, start + token.length)
    })
  }

  async function handleSave() {
    if (!selected || !dirty) return
    setSaving(true)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/notification-templates/${selected}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: editText }),
      })
      if (res.ok) {
        setTemplates(prev => prev.map(t =>
          t.notification_type === selected
            ? { ...t, template: editText, updated_at: new Date().toISOString() }
            : t
        ))
        setDirty(false)
      }
    } finally {
      setSaving(false)
    }
  }

  // Friendly display name: replace underscores, title-case
  function displayName(type: string) {
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }

  return (
    <div className="flex flex-col md:flex-row gap-4 h-full min-h-0 md:min-h-[600px]">
      {/* Left: list */}
      <div className="w-full md:w-52 md:shrink-0 flex flex-col gap-1">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Notification type
        </p>
        {templates.map(row => (
          <button
            key={row.notification_type}
            onClick={() => handleSelect(row)}
            className={clsx(
              'w-full text-left px-3 py-2 rounded-lg text-xs transition-all',
              selected === row.notification_type
                ? 'bg-violet-600 text-white'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
            )}
          >
            {displayName(row.notification_type)}
            {row.updated_at && (
              <div className={clsx(
                'text-xs mt-0.5',
                selected === row.notification_type ? 'text-violet-200' : 'text-slate-400 dark:text-slate-500'
              )}>
                {relativeTime(row.updated_at)}
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Right: editor */}
      <div className="flex-1 min-w-0">
        {!selectedRow ? (
          <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
            Select a notification type to edit its template
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Header */}
            <div>
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {displayName(selectedRow.notification_type)}
              </h2>
              {selectedRow.updated_at && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Last edited {relativeTime(selectedRow.updated_at)}
                  {selectedRow.updated_by && ` by ${selectedRow.updated_by}`}
                </p>
              )}
            </div>

            {/* Variable chips */}
            {knownVars.length > 0 && (
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
                  Available variables — click to insert at cursor:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {knownVars.map(v => (
                    <button
                      key={v}
                      onClick={() => insertVariable(v)}
                      className="inline-block bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded text-xs font-mono cursor-pointer hover:bg-blue-200 dark:hover:bg-blue-900/60 transition-colors"
                    >
                      {'{' + v + '}'}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Textarea */}
            <div>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300 block mb-1">
                Template
              </label>
              <textarea
                ref={textareaRef}
                value={editText}
                onChange={e => { setEditText(e.target.value); setDirty(true) }}
                rows={10}
                className={clsx(
                  'w-full font-mono text-xs rounded-lg border px-3 py-2.5 resize-y',
                  'bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                  'border-slate-200 dark:border-slate-700',
                  'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                )}
              />
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                {editText.length.toLocaleString()} chars
              </p>
            </div>

            {/* Unknown variable warning */}
            {unknownVars.length > 0 && (
              <div className="flex items-start gap-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
                <AlertTriangle size={14} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  Unknown variable{unknownVars.length > 1 ? 's' : ''}:{' '}
                  {unknownVars.map(v => `{${v}}`).join(', ')} — will be passed through literally if not in context.
                </p>
              </div>
            )}

            {/* Save button */}
            <div className="flex justify-end">
              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Save size={12} />
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
