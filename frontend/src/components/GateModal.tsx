import { useState, useEffect } from 'react'
import { X, Zap, Lock, ArrowRight, Check } from 'lucide-react'
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
    setSubmitted(true)
    setTimeout(() => {
      onClose()
      if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    }, 1600)
  }

  const handleGuest = () => {
    onClose()
    if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    else navigate('/explore')
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white rounded-3xl shadow-2xl w-full max-w-md animate-in overflow-hidden">
        {/* Top accent bar */}
        <div className="h-1 bg-gradient-to-r from-violet-500 to-violet-600" />

        <div className="p-8">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-all"
          >
            <X size={16} />
          </button>

          {/* Icon */}
          <div className="flex justify-center mb-5">
            <div className="w-12 h-12 rounded-2xl bg-violet-50 border border-violet-100 flex items-center justify-center">
              {reason === 'limit'
                ? <Lock size={22} className="text-violet-600" />
                : <Zap size={22} className="text-violet-600" fill="currentColor" />
              }
            </div>
          </div>

          {submitted ? (
            <div className="text-center py-4">
              <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center mx-auto mb-3">
                <Check size={22} className="text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-slate-900 mb-1">You're on the list!</h2>
              <p className="text-slate-500 text-sm">Taking you to your mission…</p>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-bold text-slate-900 text-center mb-2">
                {reason === 'limit' ? 'Free sparks used up' : 'Your mission is ready'}
              </h2>
              <p className="text-slate-500 text-sm text-center mb-5 leading-relaxed">
                {reason === 'limit'
                  ? 'Create a free account to unlock unlimited sparks, save your progress, and earn capability badges.'
                  : 'Save your path, unlock the full mission, and build your Capability Passport as you grow.'}
              </p>

              {/* Mission preview */}
              {mission && (
                <div className="flex items-center gap-3 p-3 rounded-xl bg-violet-50 border border-violet-100 mb-5">
                  <span className="text-2xl">{mission.icon}</span>
                  <div>
                    <p className="text-xs text-violet-600 font-medium mb-0.5">Your mission</p>
                    <p className="text-sm text-slate-800 font-semibold leading-snug">{mission.title}</p>
                  </div>
                </div>
              )}

              {/* What you get */}
              <ul className="space-y-2 mb-6">
                {['Unlimited sparks', 'Full mission access', 'Capability Passport'].map(item => (
                  <li key={item} className="flex items-center gap-2 text-sm text-slate-600">
                    <Check size={14} className="text-emerald-500 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>

              <form onSubmit={handleSubmit} className="space-y-3 mb-4">
                <input
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:border-violet-300 focus:ring-2 focus:ring-violet-500/10"
                />
                <button type="submit" className="w-full py-3 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2">
                  Create free account
                  <ArrowRight size={14} />
                </button>
              </form>

              <div className="relative flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-slate-100" />
                <span className="text-xs text-slate-400">or</span>
                <div className="flex-1 h-px bg-slate-100" />
              </div>

              <button
                onClick={handleGuest}
                className="w-full text-sm text-slate-400 hover:text-slate-600 py-2 transition-colors"
              >
                Continue as guest (progress won't save)
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
