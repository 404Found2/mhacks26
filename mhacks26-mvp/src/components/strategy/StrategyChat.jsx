import { useEffect, useRef, useState } from 'react';

function showsStatement(message) {
  const statement = (message.statement || '').trim();
  if (!statement) return false;
  if (message.text === 'Saved. This strategy statement is now on your dashboard.') return false;
  return !message.text.includes(statement);
}

function StrategyChat({ sessionReady, sessionVersion = 0 }) {
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [historyReady, setHistoryReady] = useState(false);
  const threadRef = useRef(null);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    if (!sessionReady) return undefined;
    let ignore = false;

    const loadMessages = async () => {
      try {
        const response = await fetch('/api/messages', { credentials: 'include' });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Could not load messages');
        }
        if (ignore) return;
        setMessages((data || []).map((message) => ({
          role: message.role,
          kind: message.kind || undefined,
          text: message.content,
          chips: message.chips || [],
          statement: message.statement || '',
        })));
      } catch {
        if (!ignore) setMessages([]);
      } finally {
        if (!ignore) setHistoryReady(true);
      }
    };

    loadMessages();
    return () => {
      ignore = true;
    };
  }, [sessionReady, sessionVersion]);

  const submitText = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || sending || !sessionReady || !historyReady) return;

    const history = messages.map((message) => ({
      role: message.role,
      content: message.text,
      chips: message.chips || [],
      statement: message.statement || '',
      kind: message.kind || '',
    }));
    setDraft('');
    setMessages((current) => [...current, { role: 'user', text: trimmed }]);
    setSending(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, history }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Request failed');
      }
      setMessages((current) => [
        ...current,
        ...(data.accent ? [{ role: 'assistant', kind: 'accent', text: data.accent }] : []),
        {
          role: 'assistant',
          text: data.message,
          chips: data.chips || [],
          statement: data.statement || '',
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'assistant', text: error.message || 'Could not reach the strategy server.' },
      ]);
    } finally {
      setSending(false);
    }
  };

  const sendMessage = (event) => {
    event.preventDefault();
    submitText(draft);
  };

  const resetChat = async () => {
    if (sending || resetting || !sessionReady) return;
    setResetting(true);
    try {
      const response = await fetch('/api/messages', {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not reset the chat');
      setMessages([]);
      setDraft('');
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'assistant', text: error.message || 'Could not reset the chat.' },
      ]);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-head">
        <div className="agent-pill">
          <span className="agent-avatar">✦</span>
          Theo · Strategy Agent
        </div>
        <button
          type="button"
          className="completed-toggle"
          disabled={sending || resetting || !sessionReady}
          onClick={resetChat}
        >
          Reset chat
        </button>
      </div>

      <div className="strategy-messages" ref={threadRef}>
        <div className="live-thread">
          {messages.map((message, index) => (
            <div className="turn" key={`${message.role}-${index}`}>
              <div className={message.kind === 'accent' ? 'assistant-bubble accent' : message.role === 'user' ? 'user-bubble' : 'assistant-bubble'}>
                <div className="message-body">{message.text}</div>
                {message.chips?.length > 0 && (
                  <div className="chip-row">
                    {message.chips.map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        className="chip"
                        disabled={sending}
                        onClick={() => submitText(chip)}
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {showsStatement(message) && (
                <div className="generated-box">
                  <div className="generated-header">
                    <span>Generated strategy statement</span>
                  </div>
                  <div className="generated-body">{message.statement}</div>
                </div>
              )}
            </div>
          ))}
          {sending && (
            <div className="turn">
              <div className="assistant-bubble thinking" aria-live="polite">
                <span className="thinking-label">Theo is thinking</span>
                <span className="thinking-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <form className="composer" onSubmit={sendMessage}>
        <div className="composer-input-wrap">
          <span className="composer-icon">✦</span>
          <input
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Describe your customer or answer Theo's question..."
            disabled={sending || !sessionReady || !historyReady}
          />
        </div>
        <button type="submit" className="send-button" disabled={sending || !sessionReady || !historyReady || !draft.trim()}>↑</button>
      </form>
    </div>
  );
}

export default StrategyChat;
