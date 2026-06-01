import type { ReactNode } from 'react'
import { Sparkles, Target, Lightbulb } from 'lucide-react'

// ── Inline renderer ───────────────────────────────────────────────────────────

function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold text-slate-900 dark:text-white">{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

// Peels a leading emoji off a string. Emojis are non-ASCII; we grab
// everything before the first space if that prefix contains non-ASCII.
function peelEmoji(text: string): [emoji: string, rest: string] | null {
  const sp = text.indexOf(' ')
  if (sp <= 0) return null
  const head = text.slice(0, sp)
  return /[^\x00-\x7F]/.test(head) ? [head, text.slice(sp + 1)] : null
}

// Extracts bullet strings — prefers "\n- item" lines, falls back to " - " split.
function extractBullets(body: string): string[] {
  const lineItems = body
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.startsWith('- '))
    .map(l => l.slice(2).trim())
  if (lineItems.length > 0) return lineItems
  return body.split(/ - /).map(s => s.trim()).filter(Boolean)
}

// ── Block types ───────────────────────────────────────────────────────────────

type Block =
  | { t: 'hook';       text: string }
  | { t: 'section';    emoji: string; title: string; bullets: string[] }
  | { t: 'activity';   bullets: string[] }
  | { t: 'conclusion'; text: string }
  | { t: 'reflection'; text: string }
  | { t: 'list';       items: string[] }
  | { t: 'prose';      text: string }

// ── Block classifier ──────────────────────────────────────────────────────────

function classify(raw: string, idx: number, total: number): Block {
  const block = raw.trim()

  // ① Reflection CTA — 💡 prefix
  if (block.startsWith('💡')) {
    return {
      t: 'reflection',
      text: block.replace(/^💡\s*/, '').replace(/\s*>?\s*$/, '').trim(),
    }
  }

  // ② ## heading blocks
  if (block.startsWith('## ')) {
    const withoutHash = block.slice(3)
    const nlIdx       = withoutHash.indexOf('\n')
    const headLine    = nlIdx === -1 ? withoutHash : withoutHash.slice(0, nlIdx)
    const bodyAfter   = nlIdx === -1 ? '' : withoutHash.slice(nlIdx + 1).trim()

    const isTryThis = /try this/i.test(headLine) || headLine.includes('🎯')
    if (isTryThis) {
      const bullets = bodyAfter
        ? extractBullets(bodyAfter)
        : headLine.split(/ - /).slice(1).map(s => s.trim()).filter(Boolean)
      return { t: 'activity', bullets }
    }

    // Section — parse title + bullets from whichever format the AI used
    let emoji: string, title: string, bullets: string[]

    if (bodyAfter) {
      // Proper newline format: headLine = title only, bodyAfter = "- item" lines
      const peeled = peelEmoji(headLine)
      emoji   = peeled ? peeled[0] : '◈'
      title   = (peeled ? peeled[1] : headLine).replace(/[!.]+$/, '').trim()
      bullets = extractBullets(bodyAfter)
    } else {
      // Inline format: "## 📋 Title - bullet - bullet"
      const parts  = headLine.split(/ - /)
      const peeled = peelEmoji(parts[0])
      emoji   = peeled ? peeled[0] : '◈'
      title   = (peeled ? peeled[1] : parts[0]).replace(/[!.]+$/, '').trim()
      bullets = parts.slice(1).map(s => s.trim()).filter(Boolean)
    }

    return bullets.length > 0
      ? { t: 'section', emoji, title, bullets }
      : { t: 'prose', text: headLine }
  }

  // ③ Emoji-prefixed section WITHOUT ## (AI occasionally omits the prefix)
  const peeled = peelEmoji(block)
  if (peeled && block.includes(' - ')) {
    const [emoji, rest] = peeled
    const isTryThis     = /try this/i.test(rest) || emoji === '🎯'
    const parts         = rest.split(/ - /)
    const title         = parts[0].replace(/[!.]+$/, '').trim()
    const bullets       = parts.slice(1).map(s => s.trim()).filter(Boolean)
    if (bullets.length > 0) {
      return isTryThis ? { t: 'activity', bullets } : { t: 'section', emoji, title, bullets }
    }
  }

  // ④ Standard markdown list — every line starts with "- "
  const lines = block.split('\n').map(l => l.trim())
  if (lines.length > 1 && lines.every(l => l.startsWith('- '))) {
    return { t: 'list', items: lines.map(l => l.slice(2)) }
  }

  // ⑤ First block → opening hook
  if (idx === 0) return { t: 'hook', text: block }

  // ⑥ Near-end block with bold → conclusion pull-quote
  if (block.includes('**') && idx >= total - 2) {
    return { t: 'conclusion', text: block }
  }

  // ⑦ Fallthrough → prose
  return { t: 'prose', text: block }
}

// ── Renderer ──────────────────────────────────────────────────────────────────

export default function MarkdownContent({ content }: { content: string }) {
  const rawBlocks = content.split(/\n{2,}/).map(b => b.trim()).filter(Boolean)
  const blocks    = rawBlocks.map((b, i) => classify(b, i, rawBlocks.length))

  return (
    <div className="space-y-4 text-sm">
      {blocks.map((block, i) => {

        // ── Opening hook ────────────────────────────────────────────────────
        if (block.t === 'hook') return (
          <div key={i} className="rounded-2xl bg-gradient-to-br from-violet-50 to-white dark:from-violet-950/50 dark:via-slate-900/40 dark:to-slate-900/10 border border-violet-200 dark:border-violet-500/15 px-5 py-4">
            <div className="flex items-center gap-1.5 mb-2.5">
              <Sparkles size={10} className="text-violet-500 dark:text-violet-400" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-violet-500 dark:text-violet-400">
                Spotlight
              </span>
            </div>
            <p className="text-[15px] leading-7 text-slate-700 dark:text-slate-200">
              {renderInline(block.text)}
            </p>
          </div>
        )

        // ── Section card ────────────────────────────────────────────────────
        if (block.t === 'section') return (
          <div key={i} className="rounded-2xl border border-slate-200 dark:border-slate-700/40 bg-white/70 dark:bg-slate-800/25 overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700/30 bg-slate-50/80 dark:bg-slate-800/40">
              <span className="text-lg leading-none shrink-0">{block.emoji}</span>
              <h4 className="font-semibold text-slate-800 dark:text-slate-200 text-sm tracking-tight">
                {block.title}
              </h4>
            </div>
            <ul className="px-4 py-3 space-y-2.5">
              {block.bullets.map((bullet, j) => (
                <li key={j} className="flex gap-2.5 items-start">
                  <span className="text-violet-500 dark:text-violet-400 shrink-0 mt-[3px] text-[9px]">✦</span>
                  <span className="text-slate-600 dark:text-slate-300 leading-relaxed">
                    {renderInline(bullet)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )

        // ── Activity / Try This card ────────────────────────────────────────
        if (block.t === 'activity') return (
          <div key={i} className="rounded-2xl border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/5 overflow-hidden">
            <div className="flex items-center gap-2.5 px-4 py-3 border-b border-amber-100 dark:border-amber-500/15 bg-amber-100/60 dark:bg-amber-500/10">
              <Target size={13} className="text-amber-600 dark:text-amber-400 shrink-0" />
              <h4 className="font-semibold text-amber-700 dark:text-amber-300 text-sm">Try This</h4>
              <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-amber-500/60 dark:text-amber-400/50">
                ~5 min
              </span>
            </div>
            <div className="px-4 py-3 space-y-2.5">
              {block.bullets.map((bullet, j) => (
                <div key={j} className="flex gap-3 items-start">
                  <span className="shrink-0 w-[18px] h-[18px] rounded-full border border-amber-300 dark:border-amber-400/30 bg-amber-100 dark:bg-transparent flex items-center justify-center text-[9px] font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                    {j + 1}
                  </span>
                  <span className="text-slate-600 dark:text-slate-300 leading-relaxed">
                    {renderInline(bullet)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )

        // ── Conclusion / pull-quote ─────────────────────────────────────────
        if (block.t === 'conclusion') return (
          <div key={i} className="border-l-2 border-violet-400 dark:border-violet-500/50 pl-4 py-0.5 mt-2">
            <p className="text-[15px] leading-7 text-slate-700 dark:text-slate-200">
              {renderInline(block.text)}
            </p>
          </div>
        )

        // ── Reflection CTA ──────────────────────────────────────────────────
        if (block.t === 'reflection') return (
          <div key={i} className="flex items-center gap-2 text-violet-600 dark:text-violet-400 text-xs font-medium pt-1">
            <Lightbulb size={12} className="shrink-0" />
            <span>{block.text || 'Something to pause on'}</span>
            <span className="text-violet-400/50">›</span>
          </div>
        )

        // ── Standard bullet list ────────────────────────────────────────────
        if (block.t === 'list') return (
          <ul key={i} className="space-y-2 pl-1">
            {block.items.map((item, j) => (
              <li key={j} className="flex gap-2.5 items-start text-slate-600 dark:text-slate-300 leading-relaxed">
                <span className="text-violet-500 dark:text-violet-400 shrink-0 mt-[3px] text-[9px]">✦</span>
                <span>{renderInline(item)}</span>
              </li>
            ))}
          </ul>
        )

        // ── Prose paragraph ─────────────────────────────────────────────────
        return (
          <p key={i} className="text-slate-600 dark:text-slate-300 leading-7">
            {renderInline(block.text)}
          </p>
        )
      })}
    </div>
  )
}
