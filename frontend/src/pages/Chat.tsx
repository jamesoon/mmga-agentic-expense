import { useState, useRef, useEffect, useCallback } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { Send, Paperclip, Plus, X } from 'lucide-react'
import { getToken, BASE, apiFormFetch } from '../api/client'

interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp: Date
}

function renderContent(text: string) {
  return text.split('\n').map((line, i) => (
    <span key={i}>
      {line}
      {i < text.split('\n').length - 1 && <br />}
    </span>
  ))
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const appendAgentChunk = useCallback((chunk: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.role === 'agent') {
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + chunk },
        ]
      }
      return [
        ...prev,
        { id: crypto.randomUUID(), role: 'agent', content: chunk, timestamp: new Date() },
      ]
    })
  }, [])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text && !file) return
    setError(null)

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text || `[File: ${file!.name}]`,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    // If file, use FormData POST
    if (file) {
      const fd = new FormData()
      fd.append('message', text)
      fd.append('file', file)
      setFile(null)
      try {
        const res = await apiFormFetch<{ reply: string }>('/chat/message', fd)
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'agent', content: res.reply, timestamp: new Date() },
        ])
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setStreaming(false)
      }
      return
    }

    // SSE streaming
    const token = await getToken()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      await fetchEventSource(`${BASE}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text }),
        signal: ctrl.signal,
        onmessage(ev) {
          if (ev.event === 'delta' || !ev.event) {
            appendAgentChunk(ev.data)
          }
        },
        onerror(err) {
          setError(err.message ?? 'Stream error')
          setStreaming(false)
        },
        onclose() {
          setStreaming(false)
        },
      })
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setError((e as Error).message)
      }
      setStreaming(false)
    }
  }, [input, file, appendAgentChunk])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!streaming) sendMessage()
    }
  }

  const handleNewClaim = async () => {
    if (abortRef.current) abortRef.current.abort()
    const token = await getToken()
    await fetch(`${BASE}/chat/reset`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    setMessages([])
    setInput('')
    setFile(null)
    setError(null)
  }

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
          Submit a Claim
        </h1>
        <button
          onClick={handleNewClaim}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-opacity hover:opacity-80"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          <Plus size={15} />
          New claim
        </button>
      </div>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto rounded-xl border p-4 space-y-4 mb-4"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="text-4xl mb-3">🧾</div>
            <p className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>
              Start a new expense claim
            </p>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              Upload a receipt image or type a message to begin.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
                msg.role === 'user' ? 'rounded-br-sm' : 'rounded-bl-sm'
              }`}
              style={
                msg.role === 'user'
                  ? { background: 'var(--accent)', color: 'white' }
                  : { background: '#1e2540', color: 'var(--fg)' }
              }
            >
              {renderContent(msg.content)}
              <div
                className="text-[10px] mt-1 opacity-60 text-right"
              >
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {streaming && (
          <div className="flex justify-start">
            <div
              className="rounded-xl rounded-bl-sm px-4 py-2.5 text-sm"
              style={{ background: '#1e2540', color: 'var(--muted)' }}
            >
              <span className="animate-pulse">...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div
          className="mb-2 rounded-lg px-3 py-2 text-xs border flex items-center justify-between"
          style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
        >
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2 hover:opacity-80">
            <X size={12} />
          </button>
        </div>
      )}

      {/* File preview */}
      {file && (
        <div
          className="mb-2 flex items-center gap-2 px-3 py-2 rounded-lg border text-xs"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--card)' }}
        >
          <Paperclip size={12} />
          <span className="flex-1 truncate">{file.name}</span>
          <button onClick={() => setFile(null)} className="hover:opacity-80">
            <X size={12} />
          </button>
        </div>
      )}

      {/* Input bar */}
      <div
        className="flex items-end gap-2 rounded-xl border p-3"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 rounded-lg hover:opacity-80 shrink-0"
          style={{ color: 'var(--muted)' }}
          title="Attach receipt"
        >
          <Paperclip size={17} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your expense or upload a receipt..."
          rows={1}
          className="flex-1 resize-none rounded-lg px-3 py-2 text-sm outline-none bg-transparent leading-relaxed"
          style={{ color: 'var(--fg)' }}
        />

        <button
          onClick={() => { if (!streaming) sendMessage() }}
          disabled={streaming || (!input.trim() && !file)}
          className="p-2 rounded-lg text-white shrink-0 transition-opacity disabled:opacity-40"
          style={{ background: 'var(--accent)' }}
          title="Send"
        >
          <Send size={17} />
        </button>
      </div>
    </div>
  )
}
