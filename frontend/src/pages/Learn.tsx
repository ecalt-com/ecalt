import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { useSubscription } from '../lib/SubscriptionContext'
import TodaysSpark from '../components/learn/TodaysSpark'
import ConversationInterface from '../components/learn/ConversationInterface'
import KnowledgeUniverse from '../components/learn/KnowledgeUniverse'
import PageMeta from '../components/PageMeta'

export default function Learn() {
  const { user, loading } = useAuth()
  const { isAdmin } = useSubscription()
  const navigate = useNavigate()
  const [sparkInput, setSparkInput] = useState<string | undefined>()
  const [knowledgeRefresh, setKnowledgeRefresh] = useState(0)

  if (!loading && !user) {
    navigate('/', { replace: true })
    return null
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const handleSparkSelect = useCallback((prompt: string) => {
    setSparkInput(prompt)
  }, [])

  const handleSparkConsumed = useCallback(() => {
    setSparkInput(undefined)
  }, [])

  const handleMessageComplete = useCallback(() => {
    setKnowledgeRefresh(n => n + 1)
  }, [])

  return (
    <>
      <PageMeta
        title="Learn"
        description="Your personal learning conversation. Ask anything."
      />
      <div className="h-screen bg-[var(--bg-primary)] flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-white/5">
          <button
            onClick={() => navigate('/')}
            className="text-sm font-bold gradient-text"
          >
            ECALT
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/pricing')}
              className="text-xs text-slate-400 hover:text-slate-300 transition-colors"
            >
              Pricing
            </button>
            {isAdmin && (
              <button
                onClick={() => navigate('/admin')}
                className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
              >
                Admin
              </button>
            )}
            <button
              onClick={() => navigate('/passport')}
              className="text-xs text-slate-400 hover:text-slate-300 transition-colors"
            >
              Passport
            </button>
            {user?.photoURL && (
              <img
                src={user.photoURL}
                alt={user.displayName ?? 'User'}
                className="w-7 h-7 rounded-full ring-1 ring-white/10"
              />
            )}
          </div>
        </header>

        {/* 3-panel layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel — Today's spark (hidden on mobile) */}
          <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-white/5 bg-[var(--bg-secondary)]">
            <TodaysSpark onSelect={handleSparkSelect} />
          </aside>

          {/* Center panel — Conversation */}
          <main className="flex-1 flex flex-col overflow-hidden">
            <ConversationInterface
              sparkInput={sparkInput}
              onSparkConsumed={handleSparkConsumed}
              onMessageComplete={handleMessageComplete}
            />
          </main>

          {/* Right panel — Knowledge Universe (hidden on mobile) */}
          <aside className="hidden lg:flex w-60 shrink-0 flex-col border-l border-white/5 bg-[var(--bg-secondary)]">
            <KnowledgeUniverse refreshTrigger={knowledgeRefresh} />
          </aside>
        </div>
      </div>
    </>
  )
}
