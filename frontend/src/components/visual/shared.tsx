import type { ReactNode } from 'react'

// Same card chrome as StepDiagram.tsx's mermaid/svg diagrams, so native
// visuals sit visually consistent with the diagrams already embedded in
// step content.
export function VisualCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700/40 bg-white/70 dark:bg-slate-800/25 px-4 py-4 overflow-x-auto">
      {children}
    </div>
  )
}

export function VisualTitle({ children }: { children: ReactNode }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-widest text-violet-500 dark:text-violet-400 mb-3">
      {children}
    </h4>
  )
}

// Color by role — never the only signal (labels carry the meaning too), per
// spec section 24: "must not encode meaning using color alone."
export function roleColor(role: string): string {
  switch (role) {
    case 'input':
    case 'cause':
      return 'border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-500/25 dark:bg-cyan-500/10 dark:text-cyan-300'
    case 'output':
    case 'effect':
      return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-300'
    case 'process':
    case 'mechanism':
      return 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/25 dark:bg-violet-500/10 dark:text-violet-300'
    default:
      return 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700/40 dark:bg-slate-800/40 dark:text-slate-300'
  }
}
