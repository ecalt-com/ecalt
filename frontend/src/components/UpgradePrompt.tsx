import { useNavigate } from 'react-router-dom'
import { Zap, X } from 'lucide-react'
import { useSubscription } from '../lib/SubscriptionContext'

interface UpgradePromptProps {
  reason: 'free_trial_exhausted' | 'budget_exhausted' | string
  onDismiss?: () => void
}

const MESSAGES = {
  free_trial_exhausted: {
    title: "You've explored 6 ideas",
    body: "Your free trial has ended. Upgrade to keep the conversation going — unlimited questions, personalized learning, and your growing Knowledge Universe.",
  },
  budget_exhausted: {
    title: "Monthly learning budget reached",
    body: "You've used your plan's token budget for this month. Upgrade to a higher plan or wait for next month's reset.",
  },
  default: {
    title: "Upgrade to continue",
    body: "Unlock unlimited learning conversations, personalized sparks, and your Knowledge Universe.",
  },
}

export default function UpgradePrompt({ reason, onDismiss }: UpgradePromptProps) {
  const navigate = useNavigate()
  const { plan } = useSubscription()
  const msg = MESSAGES[reason as keyof typeof MESSAGES] ?? MESSAGES.default

  return (
    <div className="mx-4 mb-4 glass-card rounded-2xl p-5 border border-violet-500/20">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-500/20 flex items-center justify-center">
            <Zap size={14} className="text-violet-400" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">{msg.title}</h3>
        </div>
        {onDismiss && (
          <button onClick={onDismiss} className="text-slate-500 hover:text-slate-400 shrink-0">
            <X size={14} />
          </button>
        )}
      </div>

      <p className="text-xs text-slate-400 leading-relaxed mb-4">{msg.body}</p>

      <div className="flex gap-2">
        <button
          onClick={() => navigate('/pricing')}
          className="flex-1 btn-primary text-xs py-2"
        >
          View plans →
        </button>
        {plan?.plan_id === 'free_trial' && (
          <button
            onClick={() => navigate('/pricing?plan=individual')}
            className="flex-1 py-2 px-3 rounded-lg text-xs font-medium border border-violet-400/40 text-violet-300 hover:bg-violet-500/10 transition-colors"
          >
            Individual — $19/mo
          </button>
        )}
      </div>
    </div>
  )
}
