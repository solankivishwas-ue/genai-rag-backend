import { useState, useRef, useEffect } from 'react';
import {
  Send, Bot, User, Sparkles, BookOpen, Copy,
  CheckCheck, ChevronDown, Zap, AlertCircle
} from 'lucide-react';
import { documentsApi } from '../api/client';
import './ChatWindow.css';

function Message({ msg }) {
  const [copied, setCopied] = useState(false);
  const isBot = msg.role === 'assistant';

  const copy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`msg-row ${isBot ? 'bot' : 'user'}`}>
      <div className="msg-avatar">
        {isBot ? <Bot size={16} /> : <User size={16} />}
      </div>
      <div className="msg-body">
        <div className={`msg-bubble ${isBot ? 'bot' : 'user'} ${msg.streaming ? 'streaming' : ''}`}>
          {msg.content || <span className="typing-indicator"><span/><span/><span/></span>}
          {msg.streaming && msg.content && <span className="cursor-blink" />}
        </div>

        {/* Sources */}
        {isBot && !msg.streaming && msg.sources?.length > 0 && (
          <SourcesAccordion sources={msg.sources} />
        )}

        {/* Meta */}
        {isBot && !msg.streaming && msg.content && (
          <div className="msg-meta">
            {msg.model && <span className="meta-chip"><Zap size={10} />{msg.model}</span>}
            {msg.tokens && <span className="meta-chip">{msg.tokens} tokens</span>}
            <button className="copy-btn" onClick={copy}>
              {copied ? <><CheckCheck size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
            </button>
          </div>
        )}

        {/* Error */}
        {msg.error && (
          <div className="msg-error"><AlertCircle size={13} /> {msg.error}</div>
        )}
      </div>
    </div>
  );
}

function SourcesAccordion({ sources }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sources-accordion">
      <button className="sources-toggle" onClick={() => setOpen(!open)}>
        <BookOpen size={12} /> {sources.length} source{sources.length > 1 ? 's' : ''}
        <ChevronDown size={12} className={open ? 'rotated' : ''} />
      </button>
      {open && (
        <div className="sources-list">
          {sources.map((s, i) => (
            <div key={s.chunk_id} className="source-item">
              <div className="source-header">
                <span className="source-num">[{i + 1}]</span>
                <span className="source-title">{s.document_title}</span>
                <span className="source-score">{(s.similarity_score * 100).toFixed(0)}%</span>
              </div>
              <p className="source-content">{s.content.slice(0, 200)}{s.content.length > 200 ? '…' : ''}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatWindow({ selectedDoc }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setInput('');
    setBusy(true);

    const userMsg = { id: Date.now(), role: 'user', content: q };
    const botId = Date.now() + 1;
    const botMsg = { id: botId, role: 'assistant', content: '', streaming: true, sources: [] };
    setMessages((m) => [...m, userMsg, botMsg]);

    try {
      // Use similarity_threshold=0.0 so results always come back
      // (needed when docs were uploaded with mock embeddings)
      const res = await documentsApi.queryStream(q, 5, 0.0);
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errBody.detail || 'Stream request failed');
      }

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buffer = '';
      let sources = [];
      let answerText = '';
      let streamError = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('event: sources')) continue;
          if (!line.startsWith('data: ')) continue;

          const raw = line.slice(6).trim();
          if (raw === '[DONE]') continue;

          try {
            const parsed = JSON.parse(raw);
            if (parsed.error) {
              // Backend sent an error inside the stream
              streamError = parsed.error;
            } else if (parsed.delta !== undefined) {
              answerText += parsed.delta;
              setMessages((m) =>
                m.map((x) => x.id === botId ? { ...x, content: answerText } : x)
              );
            } else if (Array.isArray(parsed)) {
              sources = parsed;
            }
          } catch {}
        }
      }

      if (streamError) {
        setMessages((m) =>
          m.map((x) => x.id === botId
            ? { ...x, streaming: false, content: '', error: streamError }
            : x)
        );
      } else {
        setMessages((m) =>
          m.map((x) => x.id === botId
            ? { ...x, streaming: false, sources, content: answerText || '(No response from model)' }
            : x)
        );
      }
    } catch (err) {
      setMessages((m) =>
        m.map((x) => x.id === botId
          ? { ...x, streaming: false, content: '', error: err.message }
          : x)
      );
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const suggestions = [
    'Summarize the key points in my documents',
    'What are the main topics covered?',
    'Explain the most important findings',
  ];

  return (
    <div className="chat-window">
      {/* Top bar */}
      <div className="chat-topbar">
        <div className="chat-topbar-left">
          <div className="chat-topbar-icon"><Bot size={18} /></div>
          <div>
            <p className="chat-topbar-title">RAG Assistant</p>
            <p className="chat-topbar-sub">
              {selectedDoc ? `Context: ${selectedDoc.title}` : 'Querying all documents'}
            </p>
          </div>
        </div>
        <div className="chat-topbar-badge">
          <span className="badge-dot" /> Live
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="empty-icon">
              <Sparkles size={32} />
            </div>
            <h2>Ask anything about your documents</h2>
            <p>Upload a document from the sidebar, then ask questions. I'll retrieve relevant context and give you accurate answers.</p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} className="suggestion-chip" onClick={() => { setInput(s); inputRef.current?.focus(); }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <Message key={msg.id} msg={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-box">
          <textarea
            ref={inputRef}
            className="chat-textarea"
            placeholder="Ask a question about your documents…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            disabled={busy}
          />
          <button
            className="send-btn"
            onClick={send}
            disabled={!input.trim() || busy}
            title="Send (Enter)"
          >
            <Send size={17} />
          </button>
        </div>
        <p className="chat-hint">Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line</p>
      </div>
    </div>
  );
}
