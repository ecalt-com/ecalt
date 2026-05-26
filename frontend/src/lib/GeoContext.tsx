import { createContext, useContext, useEffect, useState } from 'react'

interface GeoState {
  country: string
  loading: boolean
}

const GeoContext = createContext<GeoState>({ country: '', loading: true })

export function GeoProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GeoState>({ country: '', loading: true })

  useEffect(() => {
    fetch('/api/v1/geo/country')
      .then(r => r.json())
      .then(d => setState({ country: d.country ?? '', loading: false }))
      .catch(() => setState({ country: '', loading: false }))
  }, [])

  return <GeoContext.Provider value={state}>{children}</GeoContext.Provider>
}

export const useGeo = () => useContext(GeoContext)
export const isIndia = (country: string) => country === 'IN'
