import { useEffect, useRef, useState } from "react";
import { ApiError, chat, getChatHistory } from "../api";

interface Message {
  role: "user" | "assistant" | "error";
  content: string;
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatHistory()
      .then((turns) => {
        setMessages(
          turns
            .filter((t) => t.role === "user" || t.role === "assistant")
            .map((t) => ({ role: t.role as "user" | "assistant", content: t.content }))
        );
      })
      .catch(() => {
        // No history yet, or backend unreachable — start with an empty chat, same as before.
      })
      .finally(() => setLoadingHistory(false));
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    try {
      const { response } = await chat(text);
      setMessages((m) => [...m, { role: "assistant", content: response }]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Something went wrong.";
      setMessages((m) => [...m, { role: "error", content: msg }]);
    } finally {
      setSending(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="panel chat-panel">
      <div className="chat-messages">
        {loadingHistory && <p className="loading">Loading chat history…</p>}
        {!loadingHistory && messages.length === 0 && (
          <p className="empty-hint">
            Ask about your inbox, calendar, tasks, or journal — or just say hello.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-message chat-message--${m.role}`}>
            <span className="chat-message__role">
              {m.role === "user" ? "You" : m.role === "assistant" ? "Agent" : "Error"}
            </span>
            <p>{m.content}</p>
          </div>
        ))}
        {sending && <div className="chat-message chat-message--assistant chat-message--pending">Thinking…</div>}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Message your agent…"
          rows={2}
          disabled={sending}
        />
        <button onClick={send} disabled={sending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
