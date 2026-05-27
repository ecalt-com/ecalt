export const fmtCents = (c: number) => {
  const d = c / 100
  if (d === 0) return '$0.00'
  if (d < 0.01) return `$${d.toFixed(4)}`
  if (d < 1)   return `$${d.toFixed(3)}`
  return `$${d.toFixed(2)}`
}

export const fmtPct = (spent: number, budget: number) => {
  if (!budget) return '0%'
  const p = (spent / budget) * 100
  if (p < 0.1)  return `${p.toFixed(3)}%`
  if (p < 1)    return `${p.toFixed(2)}%`
  return `${p.toFixed(1)}%`
}

export const calcPct = (spent: number, budget: number) =>
  budget > 0 ? Math.min(100, (spent / budget) * 100) : 0

export const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
  : n >= 1_000   ? `${(n / 1_000).toFixed(1)}K`
  : String(n)

export const fmtMonth = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleString('default', { month: 'short', year: 'numeric' })
