import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import { useImpersonation } from '../lib/ImpersonationContext'
import { useSubscription } from '../lib/SubscriptionContext'

function formatCountdown(ms: number): string {
  if (ms <= 0) return '0:00'
  const totalSecs = Math.floor(ms / 1000)
  const mins = Math.floor(totalSecs / 60)
  const secs = totalSecs % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default function ImpersonationBanner() {
  const { session, stopImpersonation } = useImpersonation()
  const { refresh: refreshSubscription } = useSubscription()
  const navigate = useNavigate()
  const [countdown, setCountdown] = useState('')

  useEffect(() => {
    if (!session) return
    const tick = () => setCountdown(formatCountdown(session.expiresAt.getTime() - Date.now()))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [session])

  if (!session) return null

  const handleExit = async () => {
    await stopImpersonation()
    refreshSubscription()
    navigate('/admin')
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] bg-amber-500 text-white flex items-center justify-between px-4 py-2 text-sm font-medium shadow-md">
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="shrink-0" />
        <span>
          Impersonating <span className="font-bold">{session.targetName}</span>
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs bg-amber-600/50 px-2 py-0.5 rounded">
          Expires in {countdown}
        </span>
        <button
          onClick={handleExit}
          className="flex items-center gap-1 text-xs bg-white/20 hover:bg-white/30 px-2.5 py-1 rounded-lg transition-colors"
        >
          <X size={11} /> Exit
        </button>
      </div>
    </div>
  )
}
