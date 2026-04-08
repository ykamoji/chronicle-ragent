"use client";
import { useState, useRef, useEffect } from "react";
import { useSession } from "../context/SessionContext";

const API_URL = "";

export default function ChatPanel() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const chatWindowRef = useRef(null);
  const { sessionId, setSessionId, messages, setMessages } = useSession();

  // Auto-scroll chat
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const formatTime = (isoString) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return "";
    }
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;

    const userQuery = query.trim();
    setQuery("");
    setMessages((prev) => [...prev, { role: "user", content: userQuery, timestamp: new Date().toISOString() }]);
    setIsLoading(true);

    try {
      const payload = { query: userQuery };
      if (sessionId) payload.session_id = sessionId;

      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("API request failed");

      const data = await res.json();
      if (!sessionId) setSessionId(data.session_id);

      setMessages((prev) => [
        ...prev,
        { role: "agent", content: data.answer, timestamp: new Date().toISOString() },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Error connecting to backend API." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="chat-container glass-panel">
      <div style={{ padding: "24px", borderBottom: "1px solid var(--panel-glass-border)" }}>
        <h1>Chronicle <span style={{ color: "var(--accent-cyan)" }}>Chat</span></h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          Real-time RAG inference powered by ReAct
        </p>
      </div>

      <div className="chat-window" ref={chatWindowRef}>
        {messages.length === 0 && (
          <div style={{ margin: "auto", textAlign: "center", color: "var(--text-secondary)" }}>
            <h2>Start a conversation</h2>
            <p>Ask about characters, summaries, or specific text segments.</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} className={`chat-bubble ${msg.role}`}>
            <div className="chat-content">
              {msg.content.split("\n").map((line, i) => (
                <span key={i}>
                  {line}
                  <br />
                </span>
              ))}
            </div>
            {msg.timestamp && (
              <div className="chat-timestamp" style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                {formatTime(msg.timestamp)}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="chat-bubble agent">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="loader"></div> Thinking...
            </div>
          </div>
        )}
      </div>

      <form className="chat-input-area" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Ask the agent anything..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !query.trim()}>
          Ask
        </button>
      </form>
    </main>
  );
}
