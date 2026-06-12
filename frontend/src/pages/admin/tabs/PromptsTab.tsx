import { useState } from 'react'
import { ChevronDown, ChevronUp, Info, RotateCcw, Save } from 'lucide-react'
import clsx from 'clsx'
import type { PromptRow, PromptHistoryEntry } from '../types'
import { INTERACTION_LABELS } from '../constants'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

function truncate(s: string | null, n: number) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

interface Props {
  prompts: PromptRow[]
  setPrompts: React.Dispatch<React.SetStateAction<PromptRow[]>>
  getToken: () => Promise<string | null>
}

export function PromptsTab({ prompts, setPrompts, getToken }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [history, setHistory] = useState<PromptHistoryEntry[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [showContract, setShowContract] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  const selectedRow = prompts.find(p => p.interaction_type === selected) ?? null

  async function handleSelect(row: PromptRow) {
    if (dirty && selected && !confirm('You have unsaved changes. Discard them?')) return
    setSelected(row.interaction_type)
    setEditText(row.style_prompt ?? row.default_style_prompt)
    setDirty(false)
    setShowHistory(false)
    setHistory([])
    setConfirmReset(false)
  }

  async function loadHistory(type: string) {
    setLoadingHistory(true)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/prompts/${type}/history?limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) setHistory(await res.json())
    } finally {
      setLoadingHistory(false)
    }
  }

  function handleToggleHistory() {
    if (!showHistory && selected) loadHistory(selected)
    setShowHistory(v => !v)
  }

  async function handleSave() {
    if (!selected || !dirty) return
    setSaving(true)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/prompts/${selected}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ style_prompt: editText }),
      })
      if (res.ok) {
        setPrompts(prev => prev.map(p =>
          p.interaction_type === selected
            ? { ...p, style_prompt: editText, style_prompt_is_default: false }
            : p
        ))
        setDirty(false)
        if (showHistory) loadHistory(selected)
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    if (!selected) return
    setResetting(true)
    try {
      const token = await getToken()
      const res = await fetch(`/api/v1/admin/prompts/${selected}/reset`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const row = prompts.find(p => p.interaction_type === selected)
        const fallback = row?.default_style_prompt ?? ''
        setPrompts(prev => prev.map(p =>
          p.interaction_type === selected
            ? { ...p, style_prompt: null, style_prompt_is_default: true }
            : p
        ))
        setEditText(fallback)
        setDirty(false)
        setConfirmReset(false)
        if (showHistory) loadHistory(selected)
      }
    } finally {
      setResetting(false)
    }
  }

  const charCount = editText.length

  return (
    <div className="flex flex-col md:flex-row gap-4 h-full min-h-0 md:min-h-[600px]">
      {/* Left: list */}
      <div className="w-full md:w-52 md:shrink-0 flex flex-col gap-1">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Interaction type
        </p>
        {prompts.map(row => (
          <button
            key={row.interaction_type}
            onClick={() => handleSelect(row)}
            className={clsx(
              'w-full text-left px-3 py-2 rounded-lg text-xs transition-all flex items-center gap-2',
              selected === row.interaction_type
                ? 'bg-violet-600 text-white'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
            )}
          >
            <span className={clsx(
              'w-2 h-2 rounded-full shrink-0',
              row.style_prompt_is_default ? 'bg-slate-300 dark:bg-slate-600' : 'bg-emerald-400'
            )} />
            <span className="truncate">{INTERACTION_LABELS[row.interaction_type] ?? row.interaction_type}</span>
            {row.style_prompt_is_default && (
              <span className={clsx(
                'ml-auto text-xs px-1.5 py-0.5 rounded font-medium shrink-0',
                selected === row.interaction_type
                  ? 'bg-violet-500 text-violet-100'
                  : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
              )}>
                DEFAULT
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Right: editor */}
      <div className="flex-1 min-w-0">
        {!selectedRow ? (
          <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
            Select an interaction type to edit its prompt
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Header */}
            <div>
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {INTERACTION_LABELS[selectedRow.interaction_type] ?? selectedRow.interaction_type}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {selectedRow.model} · {selectedRow.provider}
                {selectedRow.version && (
                  <span className="ml-1.5 text-xs font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                    v{selectedRow.version}
                  </span>
                )}
                {selectedRow.style_prompt_updated_at && (
                  <> · Last edited {relativeTime(selectedRow.style_prompt_updated_at)}
                    {selectedRow.style_prompt_updated_by && ` by ${selectedRow.style_prompt_updated_by}`}
                  </>
                )}
              </p>
            </div>

            {/* Textarea */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  Style Prompt
                </label>
                {selectedRow.style_prompt_is_default && (
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    Using hardcoded default — save to persist custom text
                  </span>
                )}
              </div>
              <textarea
                value={editText}
                onChange={e => { setEditText(e.target.value); setDirty(true) }}
                rows={12}
                className={clsx(
                  'w-full font-mono text-xs rounded-lg border px-3 py-2.5 resize-y',
                  'bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                  'border-slate-200 dark:border-slate-700',
                  'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                  'placeholder:text-slate-400',
                )}
              />
              <p className={clsx(
                'text-xs mt-1',
                charCount > 6000 ? 'text-amber-500' : 'text-slate-400 dark:text-slate-500'
              )}>
                {charCount.toLocaleString()} chars{charCount > 6000 && ' — long prompts cost more tokens'}
              </p>
            </div>

            {/* Contract panel */}
            <div>
              <button
                onClick={() => setShowContract(v => !v)}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 transition-colors"
              >
                <Info size={12} />
                Output contract (read-only)
                {showContract ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showContract && (
                <div className="mt-2">
                  <p className="text-xs text-slate-400 dark:text-slate-500 mb-1.5">
                    This is what the parser expects. It is not editable here — change it in code.
                  </p>
                  <pre className="bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-3 rounded-lg text-xs font-mono overflow-auto max-h-40 text-slate-600 dark:text-slate-300 whitespace-pre-wrap">
                    {selectedRow.output_contract_hint || '(no output contract — free-form response)'}
                  </pre>
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3">
              {confirmReset ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-amber-600 dark:text-amber-400">
                    Replace custom prompt with hardcoded default?
                  </span>
                  <button
                    onClick={handleReset}
                    disabled={resetting}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
                  >
                    {resetting ? 'Resetting…' : 'Yes, reset'}
                  </button>
                  <button
                    onClick={() => setConfirmReset(false)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmReset(true)}
                  disabled={selectedRow.style_prompt_is_default || resetting}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <RotateCcw size={12} />
                  Reset to default
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors ml-auto"
              >
                <Save size={12} />
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>

            {/* History */}
            <div className="border-t border-slate-100 dark:border-slate-800 pt-4">
              <button
                onClick={handleToggleHistory}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 transition-colors"
              >
                {showHistory ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {showHistory ? 'Hide history' : `Show history${history.length ? ` (${history.length} entries)` : ''}`}
              </button>

              {showHistory && (
                <div className="mt-3 flex flex-col gap-2">
                  {loadingHistory && (
                    <p className="text-xs text-slate-400">Loading…</p>
                  )}
                  {!loadingHistory && history.length === 0 && (
                    <p className="text-xs text-slate-400">No changes recorded yet.</p>
                  )}
                  {history.map(entry => (
                    <div key={entry.id} className="text-xs bg-slate-50 dark:bg-slate-800/50 rounded-lg px-3 py-2">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-slate-400 dark:text-slate-500">{relativeTime(entry.changed_at)}</span>
                        <span className="text-slate-500 dark:text-slate-400">by {entry.changed_by}</span>
                        {entry.reset_to_default && (
                          <span className="ml-auto text-amber-500 font-medium">↩ Reset to default</span>
                        )}
                      </div>
                      {!entry.reset_to_default && (
                        <div className="font-mono text-slate-500 dark:text-slate-400">
                          <span className="text-red-400">{truncate(entry.old_style_prompt, 60)}</span>
                          {' → '}
                          <span className="text-emerald-500">{truncate(entry.new_style_prompt, 60)}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
