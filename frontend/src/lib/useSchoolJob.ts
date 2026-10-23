import { useEffect, useRef, useState } from 'react'
import { useAuth } from './AuthContext'
import { getSchoolJob, type SchoolJob } from './schoolApi'

// Polls a school background job (outline / build / regenerate) until it reaches
// a terminal state, then calls onDone once. Reuse for every async course job.
export function useSchoolJob(schoolId: string, jobId: string | null, onDone?: (job: SchoolJob) => void) {
  const { getToken } = useAuth()
  const [job, setJob] = useState<SchoolJob | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) { setJob(null); return }
    let cancelled = false
    let timer: number | undefined

    const tick = async () => {
      try {
        const token = await getToken()
        if (!token || cancelled) return
        const j = await getSchoolJob(schoolId, jobId, token)
        if (cancelled) return
        setJob(j)
        if (j.status === 'succeeded' || j.status === 'failed' || j.status === 'cancelled') {
          onDoneRef.current?.(j)
          return
        }
      } catch { /* transient error — keep polling */ }
      timer = window.setTimeout(tick, 2500)
    }
    tick()

    return () => { cancelled = true; if (timer) window.clearTimeout(timer) }
  }, [schoolId, jobId, getToken])

  return job
}
