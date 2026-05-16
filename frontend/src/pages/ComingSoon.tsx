import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Zap } from 'lucide-react'

interface ComingSoonProps {
  title: string
  description: string
}

export default function ComingSoon({ title, description }: ComingSoonProps) {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-violet-600/8 rounded-full blur-[120px] animate-glow-pulse" />
      </div>

      <div className="relative glass rounded-3xl p-12 max-w-md w-full">
        <div className="flex justify-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
            <Zap size={26} className="text-violet-400" fill="currentColor" />
          </div>
        </div>

        <h1 className="text-2xl font-bold mb-3">{title}</h1>
        <p className="text-slate-500 text-sm leading-relaxed mb-8">{description}</p>

        <div className="space-y-3">
          <input
            type="email"
            placeholder="Your email address"
            className="w-full glass rounded-xl px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-violet-500/40"
          />
          <button className="w-full btn-primary py-3">
            Notify me when it's ready
          </button>
        </div>

        <button
          onClick={() => navigate('/')}
          className="mt-6 flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-400 transition-colors mx-auto group"
        >
          <ArrowLeft size={13} className="group-hover:-translate-x-0.5 transition-transform" />
          Back home
        </button>
      </div>
    </div>
  )
}
