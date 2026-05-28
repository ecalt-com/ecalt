# Prompt DB — Phase 5: Admin Frontend

## Context

The admin panel at `frontend/src/pages/Admin.tsx` uses a tab system with components
in `frontend/src/pages/admin/tabs/`.  The existing `AIProvidersTab` already handles
model/provider selection per interaction type.  The new Prompt Editor is a sibling tab.

---

## Files to create

```
frontend/src/pages/admin/tabs/PromptsTab.tsx
frontend/src/pages/admin/tabs/NotificationTemplatesTab.tsx
```

## Files to modify

```
frontend/src/pages/admin/constants.ts     — add new tab IDs
frontend/src/pages/admin/types.ts         — add new API types
frontend/src/pages/admin/hooks/useAdminData.ts  — add prompt/template fetchers
frontend/src/pages/Admin.tsx              — import and wire new tabs
```

---

## Step 1 — Add tab IDs to constants.ts

Open `frontend/src/pages/admin/constants.ts` and add two entries to `TABS`:

```ts
{ id: 'prompts',                label: 'AI Prompts' },
{ id: 'notification-templates', label: 'Notif Templates' },
```

Add the new string literals to the `TabId` union type.

---

## Step 2 — Add types to types.ts

```ts
export interface PromptRow {
  interaction_type:         string
  style_prompt:             string | null       // null = using hardcoded default
  style_prompt_is_default:  boolean
  default_style_prompt:     string
  output_contract_hint:     string
  style_prompt_updated_at:  string | null
  style_prompt_updated_by:  string | null
  provider:                 string
  model:                    string
}

export interface PromptHistoryEntry {
  id:                 number
  interaction_type:   string
  old_style_prompt:   string | null
  new_style_prompt:   string
  changed_by:         string
  changed_at:         string
  reset_to_default:   boolean
}

export interface NotificationTemplateRow {
  notification_type: string
  template:          string
  updated_at:        string | null
  updated_by:        string | null
}
```

---

## Step 3 — Add fetchers to useAdminData.ts

Add two new state variables and fetch calls:

```ts
const [prompts, setPrompts] = useState<PromptRow[]>([])
const [notificationTemplates, setNotificationTemplates] = useState<NotificationTemplateRow[]>([])
const [templateVariables, setTemplateVariables] = useState<Record<string, string[]>>({})

// In the fetch effect, alongside existing fetches:
fetch('/api/v1/admin/prompts', { headers })
  .then(r => r.json()).then(setPrompts).catch(() => {})

fetch('/api/v1/admin/notification-templates', { headers })
  .then(r => r.json()).then(setNotificationTemplates).catch(() => {})

fetch('/api/v1/admin/notification-templates/variables', { headers })
  .then(r => r.json()).then(setTemplateVariables).catch(() => {})
```

Expose `prompts`, `setPrompts`, `notificationTemplates`, `setNotificationTemplates`,
`templateVariables` from the hook.

---

## Step 4 — PromptsTab.tsx

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Prompts                                                     │
│  Edit the style and persona of each AI interaction.            │
│  The JSON output contract (what fields the AI must return) is  │
│  managed in code and shown here as read-only for reference.    │
├──────────────────────┬──────────────────────────────────────────┤
│  Interaction list    │  Editor pane                             │
│  ─────────────────   │  ──────────────────────────────────────  │
│  ○ daily_chat        │  daily_chat                              │
│  ● journey    ←sel   │  Model: gpt-4o-mini (openai)            │
│  ○ step_content      │                                          │
│  ○ spark             │  [Style Prompt]         [Contract ⓘ]    │
│  ○ daily_spark       │  ┌──────────────────────────────────┐   │
│  ○ knowledge_ext…    │  │  <textarea, autogrow>            │   │
│  ○ mind_signature    │  │                                  │   │
│  ○ nudge             │  └──────────────────────────────────┘   │
│                      │  1 234 chars  · Last edited 2 days ago  │
│                      │  by admin@ecalt.com                     │
│                      │                                          │
│                      │  [Reset to default]   [Save changes]    │
│                      │                                          │
│                      │  ── History ──────────────────────────  │
│                      │  3 days ago — admin@ecalt.com            │
│                      │  "You are ECALT's AI learning …" →      │
│                      │  "You are ECALT's passionate …"         │
└──────────────────────┴──────────────────────────────────────────┘
```

### Component structure

```tsx
export function PromptsTab({ prompts, setPrompts, getToken }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [history, setHistory] = useState<PromptHistoryEntry[]>([])
  const [showContract, setShowContract] = useState(false)
  const [dirty, setDirty] = useState(false)

  // When user selects a row: populate editText, fetch history
  function handleSelect(row: PromptRow) { ... }

  // Save handler: PUT /admin/prompts/{type}
  async function handleSave() { ... }

  // Reset handler: POST /admin/prompts/{type}/reset — confirm first
  async function handleReset() { ... }

  return (
    <div className="flex gap-4 h-full">
      {/* Left: list */}
      <PromptList prompts={prompts} selected={selected} onSelect={handleSelect} />
      {/* Right: editor */}
      {selected && (
        <PromptEditor
          row={prompts.find(p => p.interaction_type === selected)!}
          editText={editText}
          onChange={(v) => { setEditText(v); setDirty(true) }}
          dirty={dirty}
          saving={saving}
          resetting={resetting}
          showContract={showContract}
          onToggleContract={() => setShowContract(v => !v)}
          onSave={handleSave}
          onReset={handleReset}
          history={history}
        />
      )}
    </div>
  )
}
```

### PromptList sub-component

- Each row shows: interaction type name, a `DEFAULT` badge if `style_prompt_is_default`,
  a dot indicator (green = customised, grey = default), last-edited relative time.
- Selected row highlighted.

### PromptEditor sub-component

**Textarea:**
- `<textarea>` with `min-h-[200px]`, auto-grows with content.
- Monospace font (`font-mono text-sm`) so prompt structure is readable.
- Character counter below (`N chars`).
- Yellow warning if char count > 6000.

**Contract panel (collapsible):**
- Labelled "Output contract (read-only)" with an info icon tooltip:
  "This is the JSON schema the parser expects. It is not editable here — change it in code."
- `<pre className="bg-gray-100 p-3 rounded text-xs font-mono overflow-auto max-h-48">` showing `output_contract_hint`.
- Actually show the full contract hint text from the API — it's a label, not the full contract.
  The full contract stays in code and is never sent to the frontend.

**Buttons:**
- "Reset to default" — secondary/destructive style, disabled if already default.
  On click: show a confirm dialog ("This will replace your custom prompt with the
  hardcoded default. Continue?") before calling the API.
- "Save changes" — primary, disabled if not dirty or if saving.

**History section:**
- Collapsed by default, "Show history (N changes)" toggle.
- Each entry: relative timestamp, who changed it, a truncated diff view
  (first 60 chars of old → first 60 chars of new, with "→" between them).
- Entries where `reset_to_default=true` shown with a "↩ Reset to default" label instead.

---

## Step 5 — NotificationTemplatesTab.tsx

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Notification Copy Templates                                    │
│  These templates shape the user-message sent to the AI for     │
│  each notification type. Available variables are shown inline. │
├──────────────────────┬──────────────────────────────────────────┤
│  Template list       │  Editor pane                             │
│  ─────────────────   │  ──────────────────────────────────────  │
│  daily_spark         │  cliffhanger_return                      │
│  re_engagement       │                                          │
│  cliffhanger_return← │  Available variables:                   │
│  connection_alert    │  {name}  {topic}                         │
│  ...                 │                                          │
│                      │  ┌──────────────────────────────────┐   │
│                      │  │  <textarea>                      │   │
│                      │  └──────────────────────────────────┘   │
│                      │                                          │
│                      │  [Save changes]                          │
└──────────────────────┴──────────────────────────────────────────┘
```

### Component structure

```tsx
export function NotificationTemplatesTab({
  templates, setTemplates, templateVariables, getToken
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  function handleSelect(row: NotificationTemplateRow) {
    setSelected(row.notification_type)
    setEditText(row.template)
    setDirty(false)
  }

  async function handleSave() {
    if (!selected) return
    setSaving(true)
    const token = await getToken()
    await fetch(`/api/v1/admin/notification-templates/${selected}`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ template: editText }),
    })
    setTemplates(prev => prev.map(t =>
      t.notification_type === selected ? { ...t, template: editText } : t
    ))
    setDirty(false)
    setSaving(false)
  }
}
```

**Variable chips:**
- Above the textarea, show chips for each available variable from `templateVariables[selected]`.
- Each chip is clickable: clicking inserts `{variable_name}` at the current cursor position.
- Chips styled as `<span class="inline-block bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs font-mono cursor-pointer">`

**Validation:**
- Before save, check that all variables used in the template (`{name}`, `{topic}`, etc.)
  are in the known list for that type.  Warn (not block) if an unknown variable is found:
  "Unknown variable `{foo}` — it will be passed through literally if not in the context."

---

## Step 6 — Wire into Admin.tsx

```tsx
// Imports
import { PromptsTab } from './admin/tabs/PromptsTab'
import { NotificationTemplatesTab } from './admin/tabs/NotificationTemplatesTab'

// Destructure from useAdminData
const { ..., prompts, setPrompts, notificationTemplates, setNotificationTemplates, templateVariables } = useAdminData()

// In the tab render switch
case 'prompts':
  return <PromptsTab prompts={prompts} setPrompts={setPrompts} getToken={getToken} />
case 'notification-templates':
  return <NotificationTemplatesTab
    templates={notificationTemplates}
    setTemplates={setNotificationTemplates}
    templateVariables={templateVariables}
    getToken={getToken}
  />
```

---

## UX rules

| Rule | Reason |
|---|---|
| Never show the output contract in the textarea — only in a read-only panel | Prevent accidental edits to the schema |
| Always show character count | Long prompts cost more tokens |
| Require explicit confirm before reset | Destructive, irreversible without history lookup |
| Show `DEFAULT` badge clearly | Admins need to know if a prompt has ever been customised |
| Variable chips are clickable | Reduces typos in template variables |
| Monospace font in all textareas | Prompts have structure; proportional fonts obscure alignment |
| Dirty-state tracking with `[Save changes]` disabled when clean | Prevent accidental double-saves |

---

## Checklist

- [ ] `TABS` constant updated with two new entries
- [ ] `TabId` union updated
- [ ] `PromptRow`, `PromptHistoryEntry`, `NotificationTemplateRow` types added to types.ts
- [ ] `prompts`, `notificationTemplates`, `templateVariables` added to `useAdminData`
- [ ] `PromptsTab.tsx` created with list + editor + history
- [ ] `NotificationTemplatesTab.tsx` created with list + editor + variable chips
- [ ] Both tabs wired into `Admin.tsx` switch
- [ ] Contract panel is read-only (no `<textarea>`, use `<pre>`)
- [ ] Reset button requires confirm dialog
- [ ] Variable chips insert at cursor position
