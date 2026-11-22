import { expect, test } from '@playwright/test'
import { markdownToSpeech, splitSentences } from '../src/lib/speechText'

// F2.1: lessons and tutor replies are read aloud as plain sentences: no markup,
// diagrams, code or URLs. Pure functions, so this runs without a browser page.
test.describe('markdownToSpeech', () => {
  test('drops markup, diagrams, code and links but keeps the words', () => {
    const md = [
      '## Why the sky is blue', '',
      'Sunlight is **white** but made of *every* colour. See [the NASA page](https://nasa.gov/x) or https://example.com/y.', '',
      '```mermaid', 'graph TD; A-->B', '```', '',
      '<svg viewBox="0 0 1 1"><circle r="1"/></svg>', '',
      '- Blue scatters most', '- Red scatters least', '',
      '1. First', '2. Second', '',
      'Use `Rayleigh` scattering.',
    ].join('\n')
    const out = markdownToSpeech(md)
    expect(out).toContain('Why the sky is blue.')
    expect(out).toContain('Sunlight is white but made of every colour.')
    expect(out).toContain('See the NASA page or')
    expect(out).toContain('Blue scatters most Red scatters least First Second')
    expect(out).toContain('Use Rayleigh scattering.')
    for (const noise of ['**', '```', 'graph TD', '<svg', 'http', '##', '](']) expect(out).not.toContain(noise)
  })

  test('is safe on empty and markup-only input', () => {
    expect(markdownToSpeech('')).toBe('')
    expect(markdownToSpeech('```js\nx\n```')).toBe('')
  })
})

test.describe('splitSentences', () => {
  test('splits on sentence ends and keeps the punctuation', () => {
    expect(splitSentences('One. Two! Three? Four')).toEqual(['One.', 'Two!', 'Three?', 'Four'])
  })

  test('breaks an over-long sentence on a comma or space', () => {
    const long = `${'word '.repeat(30)}end, ${'more '.repeat(30)}done.`
    const parts = splitSentences(long, 100)
    expect(parts.length).toBeGreaterThan(2)
    for (const p of parts) expect(p.length).toBeLessThanOrEqual(100)
    expect(parts.join(' ').replace(/\s+/g, ' ')).toBe(long.replace(/\s+/g, ' ').trim())
  })
})
