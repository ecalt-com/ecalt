import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import MarkdownContent from '../MarkdownContent'
import WarmthIndicator from './WarmthIndicator'
import { useAuth } from '../../lib/AuthContext'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

interface ConversationInterfaceProps {
  sparkInput?: string
  onSparkConsumed: () => void
  onMessageComplete: () => void
}

export default function ConversationInterface({
  sparkInput,
  onSparkConsumed,
  onMessageComplete,
}: ConversationInterfaceProps) {
  const { getToken } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [messageCount, setMessageCount] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Fill input when a spark is selected
  useEffect(() => {
    if (sparkInput) {
      setInput(sparkInput)
      onSparkConsumed()
      inputRef.current?.focus()
    }
  }, [sparkInput, onSparkConsumed])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return
    const token = await getToken()
    if (!token) return

    setInput('')
    setIsStreaming(true)
    setMessageCount(n => n + 1)

    const userId = crypto.randomUUID()
    const aiId = crypto.randomUUID()

    setMessages(prev => [
      ...prev,
      { id: userId, role: 'user', content: text },
      { id: aiId, role: 'assistant', content: '', streaming: true },
    ])

    try {
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      })

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
            }
          } catch { /* skip malformed SSE lines */ }
        }
      }
    } catch {
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant') {
          return [
            ...msgs.slice(0, -1),
            { ...last, content: 'Something went wrong. Please try again.', streaming: false },
          ]
        }
        return msgs
      })
    } finally {
      setIsStreaming(false)
      onMessageComplete()
    }
  }, [conversationId, getToken, isStreaming, onMessageComplete])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <WarmthIndicator messageCount={messageCount} />

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <p className="text-slate-500 text-sm mb-2">What are you curious about today?</p>
            <p className="text-slate-600 text-xs">Ask anything — science, history, math, philosophy, anything.</p>
          </div>
        ) : (
          messages.map(msg => (
            <div
              key={msg.id}
              className={clsx('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              {msg.role === 'user' ? (
                <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-violet-600 text-white text-sm leading-relaxed">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-[85%]">
                  {msg.streaming && !msg.content ? (
                    <div className="flex items-center gap-2 text-slate-500 text-sm py-1">
                      <Loader2 size={14} className="animate-spin" />
                      <span>Thinking…</span>
                    </div>
                  ) : (
                    <div className="text-slate-300">
                      <MarkdownContent content={msg.content} />
                      {msg.streaming && (
                        <span className="inline-block w-1 h-4 bg-violet-400 animate-pulse ml-0.5 align-middle" />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="px-4 pb-4 pt-2 border-t border-white/5">
        <div className="flex items-end gap-2 glass-card rounded-xl p-2">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything…"
            disabled={isStreaming}
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-500 resize-none outline-none py-1.5 px-2 max-h-32 leading-relaxed"
            style={{ overflowY: input.split('\n').length > 3 ? 'auto' : 'hidden' }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isStreaming}
            className={clsx(
              'shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all',
              input.trim() && !isStreaming
                ? 'bg-violet-600 text-white hover:bg-violet-500'
                : 'bg-slate-700/50 text-slate-500 cursor-not-allowed'
            )}
          >
            {isStreaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
        <p className="text-[10px] text-slate-600 mt-1.5 px-2">Shift+Enter for new line · Enter to send</p>
      </div>
    </div>
  )
}
