import clsx from 'clsx'
import { Mic } from 'lucide-react'
import { useDictation } from '../lib/useSpeech'
import { useAuth, isStudentUid } from '../lib/AuthContext'
import { useProfiles } from '../lib/ProfileContext'

// Voice input for a text box. Hidden where the browser can't do it and for child
// profiles and school students: Chrome sends the audio to Google's speech service.
export default function MicButton({ onText, disabled }: { onText: (text: string) => void; disabled?: boolean }) {
  const { user } = useAuth()
  const { isKidMode } = useProfiles()
  const { listening, start, stop, supported } = useDictation(onText)
  if (!supported || isKidMode || isStudentUid(user?.uid)) return null
  return (
    <button
      type="button"
      onClick={listening ? stop : start}
      disabled={disabled}
      aria-label={listening ? 'Stop dictation' : 'Dictate your question'}
      aria-pressed={listening}
      title="Voice typing uses your browser's speech service (in Chrome, your audio is sent to Google to be turned into text)."
      className={clsx(
        'shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-50',
        listening ? 'bg-rose-500 text-white animate-pulse' : 'text-slate-400 hover:text-violet-500 hover:bg-violet-50 dark:hover:bg-violet-500/10',
      )}
    >
      <Mic size={14} />
    </button>
  )
}
