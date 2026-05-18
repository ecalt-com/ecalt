import clsx from 'clsx'

interface WarmthIndicatorProps {
  messageCount: number
}

export default function WarmthIndicator({ messageCount }: WarmthIndicatorProps) {
  return (
    <div
      className={clsx(
        'h-0.5 w-full rounded-full transition-all duration-1000',
        messageCount === 0 && 'bg-slate-200/60 dark:bg-white/5',
        messageCount >= 1 && messageCount < 3 && 'bg-slate-400/40 dark:bg-slate-500/20',
        messageCount >= 3 && messageCount < 7 && 'bg-violet-500/40 shadow-[0_0_8px_rgba(139,92,246,0.3)]',
        messageCount >= 7 && 'bg-amber-400/50 shadow-[0_0_12px_rgba(251,191,36,0.35)]',
      )}
    />
  )
}
