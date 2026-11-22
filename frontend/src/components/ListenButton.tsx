import clsx from 'clsx'
import { Pause, Square, Volume2 } from 'lucide-react'
import { useReadAloud } from '../lib/useSpeech'

// "Listen" for a lesson or a tutor reply: play/pause, stop, and a speed toggle.
// Renders nothing where the browser has no speech synthesis.
export default function ListenButton({ text, className, compact = false }: { text: string; className?: string; compact?: boolean }) {
  const { state, rate, play, pause, stop, cycleRate, supported } = useReadAloud(text)
  if (!supported || !text.trim()) return null
  const playing = state === 'playing'
  return (
    <div className={clsx('inline-flex items-center gap-1', className)} data-testid="listen-controls">
      <button
        type="button"
        onClick={playing ? pause : play}
        aria-label={playing ? 'Pause reading' : state === 'paused' ? 'Resume reading' : 'Listen to this'}
        aria-pressed={playing}
        className="inline-flex items-center gap-1.5 text-xs px-2.5 min-h-[36px] rounded-lg font-medium text-violet-600 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-500/10 transition-colors"
      >
        {playing ? <Pause size={13} /> : <Volume2 size={13} />}
        {!compact && (playing ? 'Pause' : state === 'paused' ? 'Resume' : 'Listen')}
      </button>
      {state !== 'idle' && (
        <>
          <button type="button" onClick={stop} aria-label="Stop reading"
            className="p-2 min-h-[36px] rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            <Square size={12} />
          </button>
          <button type="button" onClick={cycleRate} aria-label={`Reading speed ${rate} times`}
            className="px-2 min-h-[36px] rounded-lg text-xs tabular-nums text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            {rate}×
          </button>
        </>
      )}
    </div>
  )
}
