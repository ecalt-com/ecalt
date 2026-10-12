import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { useProfiles } from './ProfileContext'
import { canDo, getMySchools, type MySchool, type SchoolAction, type StaffRole } from './schoolApi'

// Schools the signed-in account is staff at (backend/plans/school-courses).
// The active school is remembered per device; the API stays the authority on
// what each role may do — `can()` only hides controls the API would reject.

const ACTIVE_KEY = 'ecalt.activeSchool'

const readActive = (): string | null => {
  try { return localStorage.getItem(ACTIVE_KEY) } catch { return null }
}
const writeActive = (id: string | null) => {
  try {
    if (id) localStorage.setItem(ACTIVE_KEY, id)
    else localStorage.removeItem(ACTIVE_KEY)
  } catch { /* storage unavailable — choice lasts for this page only */ }
}

interface SchoolContextValue {
  loaded: boolean
  schools: MySchool[]
  activeSchool: MySchool | null
  role: StaffRole | null
  setActiveSchool: (id: string) => void
  refresh: () => Promise<void>
  can: (action: SchoolAction) => boolean
}

const SchoolContext = createContext<SchoolContextValue>({
  loaded: false,
  schools: [],
  activeSchool: null,
  role: null,
  setActiveSchool: () => {},
  refresh: async () => {},
  can: () => false,
})

export function SchoolProvider({ children }: { children: React.ReactNode }) {
  const { user, getToken, postSignInPhase, accountKind } = useAuth()
  const { isKidMode, loaded: profilesLoaded } = useProfiles()
  const [loaded, setLoaded] = useState(false)
  const [schools, setSchools] = useState<MySchool[]>([])
  const [activeId, setActiveId] = useState<string | null>(readActive)

  // Staff act as their own account: never inside a child profile, never as a
  // school student, and not before the sign-up gates have finished.
  const eligible = !!user && postSignInPhase === 'none' && profilesLoaded && !isKidMode
    && accountKind !== 'school_student'

  const refresh = useCallback(async () => {
    if (!eligible) return
    try {
      const token = await getToken()
      if (!token) return
      const data = await getMySchools(token)
      setSchools(data.schools)
    } catch {
      // 404 while SCHOOLS_ENABLED is off, or a transient error: no school UI.
      setSchools([])
    } finally {
      setLoaded(true)
    }
  }, [eligible, getToken])

  useEffect(() => {
    if (!eligible) {
      setSchools([])
      setLoaded(!user || (profilesLoaded && postSignInPhase === 'none'))
      return
    }
    refresh()
  }, [eligible, user, profilesLoaded, postSignInPhase, refresh])

  const activeSchool = schools.find(s => s.id === activeId) ?? schools[0] ?? null
  const role = activeSchool?.role ?? null

  const setActiveSchool = useCallback((id: string) => {
    writeActive(id)
    setActiveId(id)
  }, [])

  const can = useCallback((action: SchoolAction) => canDo(role, action), [role])

  return (
    <SchoolContext.Provider value={{ loaded, schools, activeSchool, role, setActiveSchool, refresh, can }}>
      {children}
    </SchoolContext.Provider>
  )
}

export const useSchool = () => useContext(SchoolContext)
