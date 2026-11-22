// Turns a lesson or chat reply (our markdown subset) into plain sentences a
// speech engine can read. Pure functions: no DOM, so they're easy to test.

/** Markdown → readable text: diagrams, code and URLs are dropped, markup removed. */
export function markdownToSpeech(md: string): string {
  return (md || '')
    .replace(/```[\s\S]*?```/g, ' ')            // fenced code and ```mermaid blocks
    .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')       // inline diagrams
    .replace(/<[^>]+>/g, ' ')                    // any other tag
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')       // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')     // links keep their text
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/^\s{0,3}#{1,6}\s*(.+)$/gm, '$1.')  // headings read as their own sentence
    .replace(/^\s*[-*+]\s+/gm, '')               // bullets
    .replace(/^\s*\d+[.)]\s+/gm, '')             // numbered items
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/[>#|]/g, ' ')
    .replace(/\.{2,}\s*\./g, '.')                // "heading.." from headings that already end in a stop
    .replace(/\s+/g, ' ')
    .trim()
}

/** Sentences of at most `max` characters, so a long paragraph can be paused between them. */
export function splitSentences(text: string, max = 220): string[] {
  const parts = (text.match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g) ?? []).map(p => p.trim()).filter(Boolean)
  const out: string[] = []
  for (const part of parts) {
    if (part.length <= max) { out.push(part); continue }
    let rest = part
    while (rest.length > max) {
      const cut = Math.max(rest.lastIndexOf(',', max), rest.lastIndexOf(' ', max))
      const at = cut > 40 ? cut + 1 : max
      out.push(rest.slice(0, at).trim())
      rest = rest.slice(at).trim()
    }
    if (rest) out.push(rest)
  }
  return out
}
