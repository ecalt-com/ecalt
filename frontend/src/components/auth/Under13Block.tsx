import { useNavigate } from 'react-router-dom'

interface Props {
  onDismiss: () => void
}

export default function Under13Block({ onDismiss }: Props) {
  const navigate = useNavigate()

  const goHome = () => {
    onDismiss()
    navigate('/', { replace: true })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm">
      <div className="glass-card rounded-3xl p-8 max-w-sm w-full shadow-2xl text-center">
        <div className="text-4xl mb-4">🎓</div>
        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-3">
          ECALT is for learners aged 13 and over
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
          To protect younger learners, we can't create an account for you right now.
        </p>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
          Ask a parent or guardian to create an ECALT account — they can use it together with you!
        </p>
        <button onClick={goHome} className="w-full btn-primary">
          ← Back to Home
        </button>
      </div>
    </div>
  )
}
