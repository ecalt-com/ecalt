import { useEffect, useState } from 'react'
import { CheckCircle2, CloudOff, Download, Loader2 } from 'lucide-react'
import { apiErrorCode, getStepContent } from '../lib/api'
import { isSavedOffline, removeOffline, saveJourneyOffline } from '../lib/offline'
import { useToast } from '../lib/ToastContext'
import type { Journey, JourneyStep } from '../lib/types'

// "Save for offline" (F2.3): stores a journey's lessons in this browser so they stay
// readable without a connection. Lessons that haven't been generated yet are generated
// as they're saved, which counts toward the learner's usage like opening them would.
export default function OfflineButton({ journey, steps, getToken }: {
  journey: Journey
  steps: JourneyStep[]
  getToken: () => Promise<string | null>
}) {
  const { addToast } = useToast()
  const [saved, setSaved] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)

  useEffect(() => { isSavedOffline(journey.id).then(setSaved) }, [journey.id])

  const save = async () => {
    const token = await getToken()
    if (!token || steps.length === 0) return
    const contents: Record<string, string> = {}
    setProgress(0)
    try {
      for (const [i, step] of steps.entries()) {
        try {
          contents[step.id] = (await getStepContent(journey.id, step.id, token)).content
        } catch (e) {
          if (apiErrorCode(e) || (e as { status?: number })?.status === 402) break   // usage limit: save what we have
          throw e
        }
        setProgress(i + 1)
      }
      const count = Object.keys(contents).length
      if (count === 0 || !(await saveJourneyOffline(journey, contents))) {
        addToast("Couldn't save this journey for offline reading.", 'error')
        return
      }
      setSaved(true)
      addToast(count === steps.length ? 'Saved for offline reading ✓' : `Saved ${count} of ${steps.length} lessons for offline reading`, 'info')
    } catch {
      addToast("Couldn't save this journey for offline reading.", 'error')
    } finally {
      setProgress(null)
    }
  }

  const remove = async () => { await removeOffline(journey.id); setSaved(false); addToast('Removed from offline reading', 'info') }

  if (typeof indexedDB === 'undefined') return null
  return saved ? (
    <button onClick={remove} data-testid="offline-saved" title="Remove the saved lessons from this device"
      className="btn-ghost flex items-center justify-center gap-2 w-full sm:w-auto">
      <CheckCircle2 size={14} className="text-emerald-500" /> Saved offline
    </button>
  ) : (
    <button onClick={save} disabled={progress !== null} data-testid="offline-save"
      className="btn-ghost flex items-center justify-center gap-2 w-full sm:w-auto disabled:opacity-60">
      {progress !== null ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
      {progress !== null ? `Saving ${progress}/${steps.length}` : <span className="inline-flex items-center gap-1.5">Save for offline <CloudOff size={11} className="opacity-50" aria-hidden /></span>}
    </button>
  )
}
