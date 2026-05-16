import type { ReactNode } from 'react'

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold text-slate-800 dark:text-slate-200">{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>
  )
}

export default function MarkdownContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).map(b => b.trim()).filter(Boolean)

  return (
    <div className="space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
      {blocks.map((block, i) => {
        // Heading: ## text
        if (block.startsWith('## ')) {
          return (
            <h4 key={i} className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mt-4 first:mt-0">
              {block.slice(3)}
            </h4>
          )
        }

        const lines = block.split('\n')

        // List: lines starting with -
        if (lines.length > 0 && lines.every(l => l.trim().startsWith('- '))) {
          return (
            <ul key={i} className="space-y-1.5">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2">
                  <span className="text-violet-400 shrink-0 mt-0.5">·</span>
                  <span>{renderInline(l.trim().slice(2))}</span>
                </li>
              ))}
            </ul>
          )
        }

        // Paragraph
        return <p key={i}>{renderInline(block)}</p>
      })}
    </div>
  )
}
