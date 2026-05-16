import { useEffect } from 'react'
import { X, Zap, Lock, Check } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import GoogleSignInButton from './GoogleSignInButton'
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
  const { user } = useAuth()

  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  // Auto-close and navigate when user signs in while modal is open
  useEffect(() => {
    if (isOpen && user) {
      onClose()
      if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    }
  }, [user, isOpen])

  if (!isOpen) return null

  const handleGuest = () => {
    onClose()
    if (question) navigate(`/explore?q=${encodeURIComponent(question)}`)
    else navigate('/explore')
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white dark:bg-slate-900 rounded-3xl shadow-2xl w-full max-w-md animate-in overflow-hidden">
        {/* Top accent bar */}
        <div className="h-1 bg-gradient-to-r from-violet-500 to-violet-600" />

        <div className="p-5 sm:p-8">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
          >
            <X size={16} />
          </button>

          {/* Icon */}
          <div className="flex justify-center mb-5">
            <div className="w-12 h-12 rounded-2xl bg-violet-50 dark:bg-violet-900/30 border border-violet-100 dark:border-violet-800/40 flex items-center justify-center">
              {reason === 'limit'
                ? <Lock size={22} className="text-violet-600 dark:text-violet-400" />
                : <Zap size={22} className="text-violet-600 dark:text-violet-400" fill="currentColor" />
              }
            </div>
          </div>

          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 text-center mb-2">
            {reason === 'limit' ? 'Free sparks used up' : 'Your mission is ready'}
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm text-center mb-5 leading-relaxed">
            {reason === 'limit'
              ? 'Create a free account to unlock unlimited sparks, save your progress, and earn capability badges.'
              : 'Save your path, unlock the full mission, and build your Capability Passport as you grow.'}
          </p>

          {/* Mission preview */}
          {mission && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-violet-50 dark:bg-violet-900/20 border border-violet-100 dark:border-violet-800/40 mb-5">
              <span className="text-2xl">{mission.icon}</span>
              <div>
                <p className="text-xs text-violet-600 dark:text-violet-400 font-medium mb-0.5">Your mission</p>
                <p className="text-sm text-slate-800 dark:text-slate-200 font-semibold leading-snug">{mission.title}</p>
              </div>
            </div>
          )}

          {/* What you get */}
          <ul className="space-y-2 mb-6">
            {['Unlimited sparks', 'Full mission access', 'Capability Passport'].map(item => (
              <li key={item} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                <Check size={14} className="text-emerald-500 shrink-0" />
                {item}
              </li>
            ))}
          </ul>

          <GoogleSignInButton label="Create free account with Google" />

          <div className="relative flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-slate-100 dark:bg-slate-800" />
            <span className="text-xs text-slate-400">or</span>
            <div className="flex-1 h-px bg-slate-100 dark:bg-slate-800" />
          </div>

          <button
            onClick={handleGuest}
            className="w-full text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 py-2 transition-colors"
          >
            Continue as guest (progress won't save)
          </button>
        </div>
      </div>
    </div>
  )
}
