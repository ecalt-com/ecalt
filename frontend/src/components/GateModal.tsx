import { useState, useEffect } from 'react'
import { X, Zap, Lock, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { Mission } from '../lib/types'

interface GateModalProps {
  isOpen: boolean
  reason: 'mission' | 'limit'
  mission?: Mission
  question?: string
  onClose: () => void
}

export default function GateModal({ isOpen, reason, mission, question, onClose }: GateModalProps) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    // TODO: wire up real auth/waitlist API
    setSubmitted(true)
    setTimeout(() => {
      onClose()
      if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    }, 1800)
  }

  const handleGuest = () => {
    onClose()
    if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    else navigate('/explore')
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative glass rounded-3xl p-8 w-full max-w-md shadow-2xl animate-in">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-600 hover:text-slate-300 hover:bg-slate-800/50 transition-all"
        >
          <X size={16} />
        </button>

        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
            {reason === 'limit'
              ? <Lock size={24} className="text-violet-400" />
              : <Zap size={24} className="text-violet-400" fill="currentColor" />
            }
          </div>
        </div>

        {submitted ? (
          <div className="text-center py-4">
            <div className="text-4xl mb-3">✓</div>
            <h2 className="text-xl font-bold mb-2">You're on the list!</h2>
            <p className="text-slate-500 text-sm">Taking you to your mission…</p>
          </div>
        ) : (
          <>
            <h2 className="text-xl font-bold text-center mb-2">
              {reason === 'limit' ? 'Free sparks used up' : 'Your mission is ready'}
            </h2>

            <p className="text-slate-400 text-sm text-center mb-2 leading-relaxed">
              {reason === 'limit'
                ? 'Create a free account to unlock unlimited sparks, save your learning path, and earn capability badges.'
                : 'Save your progress, unlock the full mission, and get a Capability Passport as you level up.'}
            </p>

            {mission && (
              <div className="flex items-center gap-3 p-3 rounded-xl bg-violet-600/10 border border-violet-500/20 mb-6">
                <span className="text-2xl">{mission.icon}</span>
                <div>
                  <p className="text-xs text-violet-400 font-medium mb-0.5">Your mission</p>
                  <p className="text-sm text-slate-200 font-semibold leading-snug">{mission.title}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3 mb-4">
              <input
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="w-full glass rounded-xl px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-violet-500/50"
              />
              <button type="submit" className="w-full btn-primary py-3 flex items-center justify-center gap-2">
                Create free account
                <ArrowRight size={15} />
              </button>
            </form>

            <div className="relative flex items-center gap-3 mb-4">
              <div className="flex-1 h-px bg-slate-800" />
              <span className="text-xs text-slate-600">or</span>
              <div className="flex-1 h-px bg-slate-800" />
            </div>

            <button
              onClick={handleGuest}
              className="w-full text-sm text-slate-500 hover:text-slate-300 py-2 transition-colors"
            >
              Continue as guest (no save)
            </button>
          </>
        )}
      </div>
    </div>
  )
}
