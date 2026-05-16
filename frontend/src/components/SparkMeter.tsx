import { Zap } from 'lucide-react'

interface SparkMeterProps {
  used: number
  total: number
  onUpgrade: () => void
}

export default function SparkMeter({ used, total, onUpgrade }: SparkMeterProps) {
  const remaining = total - used

  return (
    <div className="flex items-center gap-3 mt-5">
      <div className="flex items-center gap-1.5">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              i < used ? 'bg-slate-700' : 'bg-violet-500'
            }`}
          />
        ))}
      </div>
      <span className="text-xs text-slate-500">
        {remaining === 0 ? (
          <button onClick={onUpgrade} className="text-violet-400 hover:text-violet-300 transition-colors font-medium">
            Upgrade for unlimited sparks →
          </button>
        ) : (
          <>
            <Zap size={11} className="inline text-violet-400 mr-1" fill="currentColor" />
            {remaining} free spark{remaining !== 1 ? 's' : ''} left ·{' '}
            <button onClick={onUpgrade} className="text-slate-600 hover:text-slate-400 transition-colors underline-offset-2 hover:underline">
              unlock unlimited
            </button>
          </>
        )}
      </span>
    </div>
  )
}
