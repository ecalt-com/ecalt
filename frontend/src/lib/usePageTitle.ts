import { useEffect } from 'react'

const BASE = 'ECALT'
const DEFAULT_TITLE = `${BASE} — Turn Curiosity Into Capability`

export function usePageTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} — ${BASE}` : DEFAULT_TITLE
    return () => { document.title = DEFAULT_TITLE }
  }, [title])
}
