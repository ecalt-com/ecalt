import type { ReactNode } from 'react'

function renderInline(text: string): ReactNode[] {
  // Handle **bold** and emoji pass-through
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold text-slate-900 dark:text-slate-100">{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>
  )
}

export default function MarkdownContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).map(b => b.trim()).filter(Boolean)

  return (
    <div className="space-y-4 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
      {blocks.map((block, i) => {
        // Heading: ## text
        if (block.startsWith('## ')) {
          return (
            <h4 key={i} className="text-sm font-bold text-violet-700 dark:text-violet-400 mt-5 first:mt-0 flex items-center gap-1.5">
              <span className="w-1 h-4 rounded-full bg-violet-400 dark:bg-violet-500 shrink-0" />
              {block.slice(3)}
            </h4>
          )
        }

        const lines = block.split('\n')

        // List: lines starting with -
        if (lines.length > 0 && lines.every(l => l.trim().startsWith('- '))) {
          return (
            <ul key={i} className="space-y-2 pl-1">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2.5 items-start">
                  <span className="text-violet-500 dark:text-violet-400 shrink-0 mt-0.5 text-base leading-none">✦</span>
                  <span>{renderInline(l.trim().slice(2))}</span>
                </li>
              ))}
            </ul>
          )
        }

        // "Try This" callout block
        if (block.toLowerCase().includes('try this') || block.toLowerCase().startsWith('## try')) {
          return (
            <div key={i} className="rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 px-4 py-3">
              <p>{renderInline(block)}</p>
            </div>
          )
        }

        // Paragraph
        return <p key={i}>{renderInline(block)}</p>
      })}
    </div>
  )
}
