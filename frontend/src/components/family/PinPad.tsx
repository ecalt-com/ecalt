import { useEffect, useRef } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  onSubmit?: () => void
  autoFocus?: boolean
  label?: string
  id?: string
}

// Masked 4–6 digit PIN entry. A single numeric input (numeric keypad on
// mobile, paste-friendly) with dot indicators underneath.
export default function PinPad({ value, onChange, onSubmit, autoFocus = true, label = 'Parent PIN', id = 'parent-pin' }: Props) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (autoFocus) ref.current?.focus() }, [autoFocus])

  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">{label}</label>
      <input
        ref={ref}
        id={id}
        type="password"
        inputMode="numeric"
        autoComplete="off"
        pattern="[0-9]*"
        maxLength={6}
        value={value}
        onChange={e => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))}
        onKeyDown={e => { if (e.key === 'Enter' && value.length >= 4) onSubmit?.() }}
        className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-lg tracking-[0.5em] text-center focus:outline-none focus:border-violet-400 dark:focus:border-violet-500"
      />
      <div className="flex justify-center gap-2 mt-2" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => (
          <span
            key={i}
            className={`w-2 h-2 rounded-full ${i < value.length ? 'bg-violet-500' : i < 4 ? 'bg-slate-300 dark:bg-slate-600' : 'bg-slate-200 dark:bg-slate-700'}`}
          />
        ))}
      </div>
    </div>
  )
}
