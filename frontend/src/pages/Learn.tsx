import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import Navigation from '../components/Navigation'
import TodaysSpark from '../components/learn/TodaysSpark'
import ConversationInterface from '../components/learn/ConversationInterface'
import KnowledgeUniverse from '../components/learn/KnowledgeUniverse'
import WhatsAppNudgeBanner from '../components/learn/WhatsAppNudgeBanner'
import PageMeta from '../components/PageMeta'

export default function Learn() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [sparkInput, setSparkInput] = useState<string | undefined>()
  const [knowledgeRefresh, setKnowledgeRefresh] = useState(0)

  const handleSparkSelect = useCallback((prompt: string) => {
    setSparkInput(prompt)
  }, [])

  const handleSparkConsumed = useCallback(() => {
    setSparkInput(undefined)
  }, [])

  const handleMessageComplete = useCallback(() => {
    setKnowledgeRefresh(n => n + 1)
  }, [])

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

  return (
    <>
      <PageMeta
        title="Learn"
        description="Your personal learning conversation. Ask anything."
      />
      <Navigation />
      <div className="h-screen bg-[var(--bg-primary)] flex flex-col overflow-hidden pt-[68px]">
        {/* 3-panel layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel — Today's spark (hidden on mobile) */}
          <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-200 dark:border-white/5 bg-[var(--bg-secondary)]">
            <TodaysSpark onSelect={handleSparkSelect} />
          </aside>

          {/* Center panel — Conversation */}
          <main className="flex-1 flex flex-col overflow-hidden">
            <ConversationInterface
              sparkInput={sparkInput}
              onSparkConsumed={handleSparkConsumed}
              onMessageComplete={handleMessageComplete}
            />
            <WhatsAppNudgeBanner messageCount={knowledgeRefresh} />
          </main>

          {/* Right panel — Knowledge Universe (hidden on mobile) */}
          <aside className="hidden lg:flex w-60 shrink-0 flex-col border-l border-slate-200 dark:border-white/5 bg-[var(--bg-secondary)]">
            <KnowledgeUniverse refreshTrigger={knowledgeRefresh} />
          </aside>
        </div>
      </div>
    </>
  )
}
