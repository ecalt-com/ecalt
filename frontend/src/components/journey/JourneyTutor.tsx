import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, Sparkles, ChevronDown } from 'lucide-react'
import clsx from 'clsx'
import MarkdownContent from '../MarkdownContent'
import UpgradePrompt from '../UpgradePrompt'
import { useSubscription } from '../../lib/SubscriptionContext'
import { getImpersonationSessionId } from '../../lib/impersonationStore'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

interface JourneyTutorProps {
  journeyId: string
  journeyTitle: string
  currentStepId: string | null
  currentStepTitle: string | null
  getToken: () => Promise<string | null>
  onClose?: () => void
}

const SUGGESTION_CHIPS = [
  'Explain this simply',
  'Give me an example',
  'Why does this matter?',
  'Test my understanding',
]

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1 px-1">
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:0ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:150ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:300ms]" />
    </div>
  )
}

export default function JourneyTutor({
  journeyId,
  journeyTitle,
  currentStepId,
  currentStepTitle,
  getToken,
  onClose,
}: JourneyTutorProps) {
  const { isLimited, refresh: refreshSubscription } = useSubscription()
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [limitReason, setLimitReason] = useState<string | null>(null)
  const [focused, setFocused] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setMessages([])
    setConversationId(null)
    setInput('')
    setLimitReason(null)
  }, [journeyId])

  // Scroll only within the messages container — never touches the page scroll
  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return
    if (isLimited) { setLimitReason('free_trial_exhausted'); return }
    const token = await getToken()
    if (!token) return

    setInput('')
    setIsStreaming(true)

    const userId = crypto.randomUUID()
    const aiId = crypto.randomUUID()

    setMessages(prev => [
      ...prev,
      { id: userId, role: 'user', content: text },
      { id: aiId, role: 'assistant', content: '', streaming: true },
    ])

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      }
      const impersonationId = getImpersonationSessionId()
      if (impersonationId) headers['X-Impersonate-Session'] = impersonationId

      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          interaction_type: 'journey_tutor',
          journey_id: journeyId,
          step_id: currentStepId,
        }),
      })

      if (response.status === 402) {
        const data = await response.json().catch(() => ({}))
        setLimitReason(data.detail?.error ?? 'free_trial_exhausted')
        setMessages(prev => prev.slice(0, -2))
        refreshSubscription()
        return
      }

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'start') {
              setConversationId(event.conversation_id)
            } else if (event.type === 'token') {
              setMessages(prev => {
                const msgs = [...prev]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  return [...msgs.slice(0, -1), { ...last, content: last.content + event.content }]
                }
                return msgs
              })
            } else if (event.type === 'done') {
              setMessages(prev => {
                const msgs = [...prev]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  return [...msgs.slice(0, -1), { ...last, streaming: false }]
                }
                return msgs
              })
            } else if (event.type === 'service_unavailable') {
              setMessages(prev => {
                const msgs = [...prev]
                const last = msgs[msgs.length - 1]
                if (last?.role === 'assistant') {
                  return [...msgs.slice(0, -1), { ...last, content: event.message, streaming: false }]
                }
                return msgs
              })
            }
          } catch { /* skip malformed SSE lines */ }
        }
      }
    } catch {
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant') {
          return [...msgs.slice(0, -1), { ...last, content: 'Something went wrong. Please try again.', streaming: false }]
        }
        return msgs
      })
    } finally {
      setIsStreaming(false)
    }
  }, [conversationId, currentStepId, getToken, isLimited, isStreaming, journeyId, refreshSubscription])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="flex flex-col h-full rounded-2xl overflow-hidden border border-violet-300/30 dark:border-violet-500/25 shadow-xl shadow-violet-500/5 bg-white dark:bg-slate-900">

      {/* ── Header ── */}
      <div className="relative shrink-0 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-violet-600 via-violet-700 to-indigo-700" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(167,139,250,0.3),transparent_70%)]" />
        <div className="relative flex items-center gap-3 px-4 py-3">
          <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center shrink-0 backdrop-blur-sm">
            <Sparkles size={15} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-white leading-tight">AI Tutor</p>
            {currentStepTitle ? (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-[10px] text-violet-200 font-medium uppercase tracking-wide">On step:</span>
                <span className="text-[11px] text-white/90 font-medium truncate max-w-[160px]">
                  {currentStepTitle}
                </span>
              </div>
            ) : (
              <p className="text-[11px] text-violet-200 truncate mt-0.5">{journeyTitle}</p>
            )}
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="shrink-0 w-7 h-7 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white/80 hover:text-white transition-colors"
              aria-label="Close tutor"
            >
              <ChevronDown size={15} />
            </button>
          )}
          {!onClose && (
            <div className="shrink-0 px-2 py-0.5 rounded-full bg-white/15 border border-white/20">
              <span className="text-[10px] text-white font-semibold uppercase tracking-wider">Live</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Messages ── */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center py-6">
            {/* Glowing orb */}
            <div className="relative mb-5">
              <div className="absolute inset-0 rounded-full bg-violet-500/20 blur-xl scale-150" />
              <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                <Sparkles size={22} className="text-white" />
              </div>
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1 text-center">
              Your personal tutor
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center mb-5 max-w-[200px] leading-relaxed">
              Ask anything about <span className="text-violet-600 dark:text-violet-400 font-medium">{journeyTitle}</span>
            </p>
            {/* Suggestion chips */}
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTION_CHIPS.map(chip => (
                <button
                  key={chip}
                  onClick={() => sendMessage(chip)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium border border-violet-200 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300 hover:bg-violet-100 dark:hover:bg-violet-500/20 hover:border-violet-300 dark:hover:border-violet-400/50 transition-all active:scale-95"
                >
                  {chip}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 mt-5">
              Scoped to this topic only
            </p>
          </div>
        ) : (
          messages.map(msg => (
            <div
              key={msg.id}
              className={clsx(
                'flex gap-2 animate-in',
                msg.role === 'user' ? 'justify-end' : 'justify-start items-end'
              )}
            >
              {msg.role === 'assistant' && (
                <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shrink-0 mb-0.5 shadow-sm shadow-violet-500/20">
                  <Sparkles size={11} className="text-white" />
                </div>
              )}

              {msg.role === 'user' ? (
                <div className="max-w-[82%] px-3.5 py-2.5 rounded-2xl rounded-tr-md bg-gradient-to-br from-violet-600 to-indigo-600 text-white text-sm leading-relaxed shadow-md shadow-violet-500/20">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-[88%] px-3.5 py-2.5 rounded-2xl rounded-bl-md bg-slate-100 dark:bg-slate-800/80 border border-slate-200/60 dark:border-slate-700/60">
                  {msg.streaming && !msg.content ? (
                    <TypingDots />
                  ) : (
                    <div className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed">
                      <MarkdownContent content={msg.content} />
                      {msg.streaming && (
                        <span className="inline-block w-0.5 h-3.5 bg-violet-400 animate-pulse ml-0.5 align-middle rounded-full" />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {limitReason && (
        <UpgradePrompt reason={limitReason} onDismiss={() => setLimitReason(null)} />
      )}

      {/* ── Input ── */}
      <div className="shrink-0 p-3 border-t border-slate-100 dark:border-white/5 bg-white/50 dark:bg-slate-900/50">
        <div className={clsx(
          'flex items-end gap-2 rounded-xl border px-3 py-2 transition-all duration-200',
          focused
            ? 'border-violet-400 dark:border-violet-500 bg-white dark:bg-slate-800 shadow-md shadow-violet-500/10 ring-2 ring-violet-400/20 dark:ring-violet-500/20'
            : 'border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/50'
        )}>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask a question…"
            disabled={isStreaming}
            className="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 resize-none outline-none py-0.5 max-h-28 leading-relaxed"
            style={{ overflowY: input.split('\n').length > 3 ? 'auto' : 'hidden' }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isStreaming}
            className={clsx(
              'shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200',
              input.trim() && !isStreaming
                ? 'bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-md shadow-violet-500/25 hover:shadow-lg hover:shadow-violet-500/30 hover:scale-105 active:scale-95'
                : 'bg-slate-200 dark:bg-slate-700 text-slate-400 cursor-not-allowed'
            )}
          >
            <Send size={13} />
          </button>
        </div>
        <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-1.5 px-1 text-center">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
